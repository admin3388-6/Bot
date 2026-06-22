import asyncio
import os
import re
import time
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import edge_tts
import uvicorn
import requests

# ========== إعدادات Render ==========
PORT = int(os.environ.get("PORT", 8000))
AUDIO_DIR = "/tmp/audio_temp"

os.makedirs(AUDIO_DIR, exist_ok=True)

app = FastAPI(title="YouTube TTS Bot - Render")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== HTML الواجهات ==========
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎙️ بوت يوتيوب المباشر</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, sans-serif; padding: 15px; background: #121824; color: #e2e8f0; max-width: 500px; margin: auto; text-align: center; }
        .card { background: #1e293b; padding: 20px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); border: 1px solid #334155; }
        input { padding: 12px; margin: 15px 0; width: 90%; background: #0f172a; border: 1px solid #475569; border-radius: 8px; color: #fff; text-align: center; font-size: 16px; }
        button { padding: 14px; width: 94%; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; font-weight: bold; margin-bottom: 10px; transition: all 0.3s; }
        .start-btn { background: #10b981; color: white; }
        .start-btn:hover { background: #059669; }
        .stop-btn { background: #ef4444; color: white; }
        .stop-btn:hover { background: #dc2626; }
        .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 20px; }
        .stat-box { background: #0f172a; padding: 12px; border-radius: 8px; border: 1px solid #334155; }
        .stat-box span { display: block; font-size: 11px; color: #94a3b8; margin-bottom: 4px; }
        .stat-box strong { font-size: 20px; color: #f8fafc; }
        .audio-link { display: block; margin-top: 20px; padding: 14px; background: #38bdf8; color: #0f172a; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 16px; }
        .log-box { background: #0f172a; padding: 12px; border-radius: 8px; border: 1px solid #334155; margin-top: 15px; text-align: right; font-size: 12px; color: #94a3b8; max-height: 200px; overflow-y: auto; line-height: 1.6; }
        .status-indicator { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-left: 6px; }
        .status-online { background: #10b981; box-shadow: 0 0 8px #10b981; }
        .status-offline { background: #ef4444; }
    </style>
</head>
<body>
    <div class="card">
        <h2 style="color: #38bdf8; margin-top: 0;">🎙️ بوت يوتيوب المباشر</h2>
        <input type="text" id="videoId" placeholder="hYFO-LxZkWw" value="hYFO-LxZkWw">
        <button class="start-btn" onclick="startBot()">▶ تشغيل البوت</button>
        <button class="stop-btn" onclick="stopBot()">⏹ إيقاف البوت</button>
        <div class="stats-grid">
            <div class="stat-box">
                <span>حالة النظام</span>
                <strong id="status"><span class="status-indicator status-offline"></span>متوقف 🔴</strong>
            </div>
            <div class="stat-box"><span>تمت قراءتها</span><strong id="total_read" style="color: #10b981;">0</strong></div>
            <div class="stat-box"><span>التكرار</span><strong id="total_repeated" style="color: #a78bfa;">0</strong></div>
            <div class="stat-box"><span>آخر تحديث</span><strong id="last_ping" style="color: #38bdf8;">--</strong></div>
        </div>
        <div class="stat-box" style="margin-top: 10px;">
            <span>آخر تعليق:</span>
            <strong id="last_comment" style="font-size: 14px; color: #38bdf8; display: block; margin-top: 5px;">لا يوجد</strong>
        </div>
        <div class="log-box" id="logs"><div style="color: #64748b;">السجلات ستظهر هنا...</div></div>
        <a href="/audio" class="audio-link" target="_blank">🔊 فتح صفحة مكبر الصوت</a>
    </div>
    <script>
        let ws;
        async function startBot() {
            let vid = document.getElementById('videoId').value.trim();
            if(!vid) return alert("الرجاء إدخال معرف الفيديو");
            addLog("🚀 جاري التشغيل...");
            try {
                let res = await fetch(`/api/start?video_id=${vid}`, {method: 'POST'});
                let data = await res.json();
                addLog(data.status === "started" ? "✅ تم التشغيل!" : "⚠️ " + data.message, data.status === "started" ? "success" : "error");
            } catch(e) { addLog("❌ خطأ: " + e.message, "error"); }
        }
        async function stopBot() { addLog("⏹️ جاري الإيقاف..."); await fetch(`/api/stop`, {method: 'POST'}); }
        function addLog(msg, type="") {
            let logs = document.getElementById('logs');
            let div = document.createElement('div'); div.className = type; div.innerText = `[${new Date().toLocaleTimeString()}] ${msg}`;
            logs.insertBefore(div, logs.firstChild);
            if(logs.children.length > 50) logs.removeChild(logs.lastChild);
        }
        function connectWS() {
            let protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws/stats`);
            ws.onopen = () => addLog("📊 متصل بالسيرفر");
            ws.onmessage = (e) => {
                let data = JSON.parse(e.data);
                document.getElementById('status').innerHTML = data.status.includes("يعمل") 
                    ? `<span class="status-indicator status-online"></span>${data.status}`
                    : `<span class="status-indicator status-offline"></span>${data.status}`;
                document.getElementById('total_read').innerText = data.total_read;
                document.getElementById('total_repeated').innerText = data.total_repeated;
                document.getElementById('last_comment').innerText = data.last_comment || "لا يوجد";
                document.getElementById('last_ping').innerText = new Date().toLocaleTimeString();
                if(data.log) addLog(data.log);
            };
            ws.onclose = () => { addLog("⚠️ إعادة الاتصال...", "error"); setTimeout(connectWS, 5000); };
        }
        connectWS();
    </script>
</body>
</html>
"""

AUDIO_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>🔊 مكبر الصوت - YouTube TTS</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #0b0f19; color: #10b981; text-align: center; padding: 40px 20px; font-family: 'Segoe UI', sans-serif; min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; }
        #init { padding: 30px 50px; font-size: 24px; border-radius: 16px; background: #10b981; color: white; border: none; font-weight: bold; cursor: pointer; box-shadow: 0 4px 20px rgba(16,185,129,0.3); transition: all 0.3s; }
        #init:hover { background: #059669; transform: scale(1.05); }
        #display { font-size: 32px; margin-top: 40px; font-weight: bold; padding: 30px; background: #1e293b; border-radius: 12px; border: 1px solid #334155; min-height: 120px; display: flex; align-items: center; justify-content: center; max-width: 90%; word-wrap: break-word; line-height: 1.5; }
        .pulse { animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%,100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.7; transform: scale(1.02); } }
        .connected { color: #38bdf8; } .playing { color: #10b981; } .waiting { color: #94a3b8; } .error { color: #ef4444; }
        .info { position: fixed; bottom: 20px; color: #64748b; font-size: 12px; }
    </style>
</head>
<body>
    <button id="init" onclick="initAudio()">🔊 اضغط هنا لتفعيل مكبر الصوت</button>
    <div id="display" class="waiting">في انتظار التشغيل...</div>
    <div class="info">🔄 يعيد الاتصال تلقائياً</div>
    <script>
        let ws, display = document.getElementById('display'), btn = document.getElementById('init');
        function initAudio() {
            btn.style.display = 'none';
            display.innerText = "⏳ جاري الاتصال..."; display.className = "connected";
            if ('wakeLock' in navigator) navigator.wakeLock.request('screen').catch(() => {});
            document.addEventListener('click', () => { if ('wakeLock' in navigator) navigator.wakeLock.request('screen'); });
            connectWS();
        }
        function connectWS() {
            let protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws/audio`);
            ws.onopen = () => { display.innerText = "✅ متصل! بانتظار التعليقات..."; display.className = "waiting"; };
            ws.onmessage = (e) => {
                let data = JSON.parse(e.data);
                if (data.action === "play") {
                    display.className = "playing pulse";
                    display.innerText = `🎙️ ${data.text}`;
                    let audio = new Audio(data.url);
                    audio.play().catch(err => { console.error(err); ws.send(JSON.stringify({action: "audio_finished", filename: data.filename})); });
                    audio.onended = () => {
                        ws.send(JSON.stringify({action: "audio_finished", filename: data.filename}));
                        display.className = "waiting";
                        display.innerText = "✅ بانتظار التعليق التالي...";
                    };
                }
            };
            ws.onclose = () => { display.className = "error"; display.innerText = "⚠️ انقطع الاتصال... إعادة المحاولة"; setTimeout(connectWS, 3000); };
        }
    </script>
</body>
</html>
"""

# ========== محرك النظام ==========
class BotStats:
    total_read = 0
    total_repeated = 0
    last_comment = "لا يوجد"
    last_text = None
    last_comment_id = None
    log_messages = []

app.state.is_running = False
app.state.video_id = None
app.state.active_audio_ws = None
app.state.audio_busy = False
app.state.latest_comment = None
app.state.stats_ws_clients = set()

def add_log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")
    BotStats.log_messages.insert(0, msg)
    if len(BotStats.log_messages) > 30:
        BotStats.log_messages = BotStats.log_messages[:30]

def detect_voice(text: str) -> str:
    text_lower = text.lower()
    darija_keywords = ['شحال','بزاف','واخا','خاصني','عندي','هادي','هادا','هاد','هذي','بغيت','بغا','بغيتي','بغاو','دابا','هلا','هلاك','هلايا','هلاكم','زوين','زوينة','زوينين','خايب','خايبة','مزيان','مزيانة','بصح','صافي','واحد','جوج','ثلاثة','ربعة','خمسة','ستة','سبعة','تمنية','تسعة','عشرة','واش','علاش','كيفاش','فين','اش','اشنو','شنو','شكون','بشحال','عافاك','عفاك','برك','بركة','يسر','يسرا','الحمد','حمد','بارك','مبروك','رحمه','رحمة','سمح','سمحلي','عفو','عفوا','شكرا','شكراً']
    khaliji_keywords = ['شلونك','شلون','شخبارك','شسوي','ابشر','هلا والله','يا هلا','يا مرحبا','حياك','حياك الله','الله يحييك','الله يعافيك','الله يعطيك','عسى','عسى خير','ان شاء الله','انشالله','يالله','يلا','يلا بنا','طيب','طيبين','طيبة','الله يسلمك','الله يبارك','الله يحفظك','والله','والله يا','والله ان','والله لا','والله نعم','والله صدق']
    masri_keywords = ['ايه','ايوه','اه','اهو','اهي','ايوة','بجد','بصح','صح','صحيح','فعلاً','فعلا','طبعاً','طبعا','اكيد','ياسطا','ياسطى','ياسطي','يا عم','يا باشا','يا بيه','يا فندم']
    
    for word in darija_keywords + khaliji_keywords + masri_keywords:
        if word in text_lower:
            return "ar-SA-ZariyahNeural"
    
    arabic_chars = re.findall(r'[\u0600-\u06FF]', text)
    if len(arabic_chars) > 0:
        return "ar-SA-ZariyahNeural"
    
    english_chars = re.findall(r'[a-zA-Z]', text)
    if len(english_chars) > len(arabic_chars):
        return "en-US-AnaNeural"
    
    return "ar-SA-ZariyahNeural"

async def generate_audio(text: str, filename: str):
    voice = detect_voice(text)
    filepath = os.path.join(AUDIO_DIR, filename)
    await edge_tts.Communicate(text, voice).save(filepath)

def fetch_comments_pytchat(video_id: str, loop: asyncio.AbstractEventLoop):
    """جلب التعليقات باستخدام pytchat - لا يحتاج API Key ولا حدود يومية"""
    try:
        import pytchat
    except ImportError:
        add_log("❌ مكتبة pytchat غير مثبتة! جاري التثبيت...")
        import subprocess
        subprocess.run(["pip", "install", "pytchat"], check=True)
        import pytchat
    
    retry_count = 0
    max_retries = 9999
    
    while retry_count < max_retries and app.state.is_running:
        try:
            add_log(f"🔄 محاولة الاتصال بالبث... ({retry_count + 1})")
            chat = pytchat.create(video_id=video_id, interruptable=False)
            retry_count = 0
            add_log("✅ متصل بالبث المباشر!")
            
            empty_count = 0
            while chat.is_alive() and app.state.is_running:
                items = chat.get().sync_items()
                found_new = False
                
                for c in items:
                    found_new = True
                    app.state.latest_comment = {
                        "author": c.author.name,
                        "text": c.message,
                        "id": c.id,
                        "timestamp": time.time()
                    }
                
                if not found_new:
                    empty_count += 1
                    if empty_count > 30:
                        add_log("⚠️ لا توجد تعليقات...")
                        empty_count = 0
                else:
                    empty_count = 0
                
                time.sleep(0.5)
                
        except Exception as e:
            retry_count += 1
            add_log(f"❌ خطأ: {str(e)[:100]}")
            add_log(f"🔄 إعادة الاتصال بعد 5 ثواني...")
            time.sleep(5)
    
    add_log("⏹️ توقف جلب التعليقات")
    app.state.is_running = False

async def process_comments():
    """الحلقة الرئيسية"""
    while True:
        try:
            if app.state.is_running and app.state.active_audio_ws and not app.state.audio_busy:
                
                current_comment = None
                is_repeat = False
                
                if app.state.latest_comment:
                    new_id = app.state.latest_comment["id"]
                    if new_id != BotStats.last_comment_id:
                        current_comment = app.state.latest_comment
                        BotStats.last_comment_id = new_id
                        app.state.latest_comment = None
                    else:
                        current_comment = {
                            "author": app.state.latest_comment["author"],
                            "text": app.state.latest_comment["text"],
                            "id": app.state.latest_comment["id"] + "_repeat"
                        }
                        is_repeat = True
                else:
                    if BotStats.last_text:
                        current_comment = {
                            "author": "تكرار",
                            "text": BotStats.last_text,
                            "id": "repeat_" + str(int(time.time()))
                        }
                        is_repeat = True
                
                if current_comment:
                    app.state.audio_busy = True
                    text_to_read = current_comment["text"]
                    filename = f"{current_comment['id']}.mp3"
                    
                    if not is_repeat:
                        BotStats.total_read += 1
                        BotStats.last_text = current_comment["text"]
                        add_log(f"📝 جديد: {text_to_read[:60]}...")
                    else:
                        BotStats.total_repeated += 1
                        add_log(f"🔄 تكرار: {text_to_read[:60]}...")
                    
                    BotStats.last_comment = current_comment["text"]
                    await broadcast_stats()
                    
                    await generate_audio(text_to_read, filename)
                    
                    filepath = os.path.join(AUDIO_DIR, filename)
                    if os.path.exists(filepath):
                        await app.state.active_audio_ws.send_json({
                            "action": "play",
                            "url": f"/audio-files/{filename}",
                            "text": text_to_read,
                            "filename": filename
                        })
                    else:
                        add_log("❌ ملف الصوت غير موجود!")
                        app.state.audio_busy = False
                else:
                    await asyncio.sleep(0.5)
            else:
                await asyncio.sleep(0.2)
        except Exception as e:
            add_log(f"❌ خطأ: {str(e)[:80]}")
            app.state.audio_busy = False
            await asyncio.sleep(2)

async def broadcast_stats():
    data = {
        "status": "يعمل الآن 🟢" if app.state.is_running else "متوقف 🔴",
        "total_read": BotStats.total_read,
        "total_repeated": BotStats.total_repeated,
        "last_comment": BotStats.last_comment,
        "log": BotStats.log_messages[0] if BotStats.log_messages else ""
    }
    dead_clients = set()
    for ws in app.state.stats_ws_clients:
        try:
            await ws.send_json(data)
        except:
            dead_clients.add(ws)
    app.state.stats_ws_clients -= dead_clients

# ========== نقاط النهاية ==========
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(process_comments())
    add_log("🚀 السيرفر جاهز!")

@app.get("/")
async def get_dash():
    return HTMLResponse(content=DASHBOARD_HTML)

@app.get("/audio")
async def get_audio():
    return HTMLResponse(content=AUDIO_HTML)

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": time.time()}

# نقطة نهاية لملفات الصوت (لأن StaticFiles قد لا يعمل مع /tmp)
@app.get("/audio-files/{filename}")
async def get_audio_file(filename: str):
    filepath = os.path.join(AUDIO_DIR, filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="audio/mpeg")
    return {"error": "File not found"}

@app.get("/api/stats")
async def get_stats():
    return {
        "status": "يعمل الآن 🟢" if app.state.is_running else "متوقف 🔴",
        "total_read": BotStats.total_read,
        "total_repeated": BotStats.total_repeated,
        "last_comment": BotStats.last_comment
    }

@app.post("/api/start")
async def start_bot(video_id: str):
    if app.state.is_running:
        return {"status": "already_running", "message": "البوت يعمل بالفعل"}
    
    app.state.is_running = True
    app.state.video_id = video_id
    app.state.latest_comment = None
    BotStats.last_comment_id = None
    BotStats.last_text = None
    BotStats.log_messages = []
    
    add_log(f"🚀 تشغيل البوت للفيديو: {video_id}")
    
    loop = asyncio.get_running_loop()
    asyncio.create_task(asyncio.to_thread(fetch_comments_pytchat, video_id, loop))
    
    return {"status": "started"}

@app.post("/api/stop")
async def stop_bot():
    app.state.is_running = False
    app.state.video_id = None
    app.state.latest_comment = None
    app.state.audio_busy = False
    add_log("⏹️ تم الإيقاف")
    await broadcast_stats()
    return {"status": "stopped"}

@app.websocket("/ws/audio")
async def audio_endpoint(websocket: WebSocket):
    await websocket.accept()
    app.state.active_audio_ws = websocket
    add_log("🔊 متصفح الصوت متصل")
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("action") == "audio_finished":
                app.state.audio_busy = False
                await asyncio.sleep(2)
                try:
                    filepath = os.path.join(AUDIO_DIR, data.get('filename'))
                    if os.path.exists(filepath):
                        os.remove(filepath)
                except:
                    pass
    except WebSocketDisconnect:
        add_log("🔊 متصفح الصوت انفصل")
    except Exception as e:
        add_log(f"🔊 خطأ: {str(e)[:50]}")
    finally:
        app.state.active_audio_ws = None
        app.state.audio_busy = False

@app.websocket("/ws/stats")
async def stats_endpoint(websocket: WebSocket):
    await websocket.accept()
    app.state.stats_ws_clients.add(websocket)
    add_log("📊 لوحة تحكم متصلة")
    try:
        while True:
            await websocket.receive_text()
    except:
        pass
    finally:
        app.state.stats_ws_clients.discard(websocket)

# ========== التشغيل ==========
if __name__ == "__main__":
    print("🚀 جاري تشغيل الخادم...")
    print(f"🌐 الرابط: http://0.0.0.0:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")

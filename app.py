from flask import Flask, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)  # يسمح للعبة بالاتصال

THE_SECRET_NUMBER = 20

@app.route('/get-number', methods=['GET'])
def get_number():
    return jsonify({
        "number": THE_SECRET_NUMBER,
        "status": "success"
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

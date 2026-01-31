import os
import uuid
import requests
import smtplib
from email.mime.text import MIMEText
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from pymongo import MongoClient

app = Flask(__name__)

# IMPORTANT: Allow your Frontend URL here (or "*" to allow everything)
CORS(app)

# --- DATABASE SETUP ---
MONGO_URI = "mongodb+srv://sainicc01_db_user:3zvWMwfHJ4U5BIQK@cluster0.vimxrxt.mongodb.net/?appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client['irra_esign_db']
orders_col = db['orders']

# --- FOLDER SETUP ---
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = '8379666289:AAEiYiFzSf4rkkP6g_u_13vbrv0ILi9eh4o'
TELEGRAM_CHAT_ID = '5007619095'
GMAIL_USER = 'sainicc01@gmail.com' 
GMAIL_APP_PASS = 'rhyy tskl byiz mdtx' 

def send_gmail_logic(to_email, order_id, link):
    subject = f"Your iOS Certificate is Ready! - {order_id}"
    body = f"Hello,\n\nYour certificate has been issued.\nDownload Link: {link}\n\nThanks, Irra Esign."
    msg = MIMEText(body); msg['Subject'] = subject; msg['From'] = GMAIL_USER; msg['To'] = to_email
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASS)
            server.send_message(msg)
        return True
    except: return False

@app.route('/')
def status():
    return jsonify({"status": "Backend is Online", "version": "2.0"})

@app.route('/uploads/<filename>')
def serve_receipt(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/orders', methods=['GET'])
def get_orders():
    all_orders = list(orders_col.find({}, {'_id': 0}))
    return jsonify({o['order_id']: o for o in all_orders})

@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    try:
        email = request.form.get('email')
        udid = request.form.get('udid')
        file = request.files.get('receipt')
        order_id = str(uuid.uuid4())[:8].upper()
        filename = secure_filename(f"{order_id}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        order_data = {
            "order_id": order_id, "email": email, "udid": udid,
            "status": "pending", "download_link": None, "receipt_url": f"/uploads/{filename}"
        }
        orders_col.insert_one(order_data)

        # Telegram notification
        receipt_link = f"{request.host_url.rstrip('/')}/uploads/{filename}"
        msg = f"🔔 <b>NEW ORDER</b>\n\n🆔 ID: {order_id}\n📧 Email: {email}\n📱 UDID: {udid}\n🖼️ <a href='{receipt_link}'>View Receipt</a>"
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"})
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "msg": str(e)}), 500

@app.route('/api/send-link', methods=['POST'])
def send_link():
    data = request.json
    orders_col.update_one({"order_id": data.get('order_id')}, {"$set": {"download_link": data.get('link'), "status": "completed"}})
    return jsonify({"success": True})

@app.route('/api/send-email', methods=['POST'])
def api_send_email():
    oid = request.json.get('order_id')
    order = orders_col.find_one({"order_id": oid})
    if order and order.get('download_link'):
        if send_gmail_logic(order['email'], oid, order['download_link']):
            return jsonify({"success": True})
    return jsonify({"success": False}), 500

@app.route('/api/delete-order/<order_id>', methods=['DELETE'])
def delete_order(order_id):
    orders_col.delete_one({"order_id": order_id})
    return jsonify({"success": True})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
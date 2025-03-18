from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

from flask import Flask, send_from_directory
import os
from werkzeug.utils import secure_filename
import traceback

# MongoDB Connection URI
uri = "mongodb+srv://ByeByeExpired:VlbKjtFuYvgw0lAS@cluster0.rcivs.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

# Connect to MongoDB
client = MongoClient(uri)
db = client["ByeByeExpired"]
users_collection = db['users']
items_collection = db['items']

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# 📌 API อัปโหลดรูป
@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"message": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"message": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)
        file_url = f"https://bug-free-telegram-x5597wr5w69gc9qr9-5000.app.github.dev/uploads/{filename}"

        return jsonify({"message": "File uploaded successfully", "file_url": file_url}), 201

    return jsonify({"message": "Invalid file type"}), 400

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# ฟังก์ชันสำหรับสร้าง user_id โดยใช้จำนวนผู้ใช้ในระบบ
def get_next_user_id():
    user_count = users_collection.count_documents({})
    return user_count + 1  # user_id จะเริ่มต้นจาก 1 และเพิ่มขึ้นทุกครั้ง

# API สำหรับการลงทะเบียน
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    # ตรวจสอบอีเมลว่าอยู่ในระบบแล้วหรือยัง
    existing_user = users_collection.find_one({"email": data['email']})
    if existing_user:
        return jsonify({"message": "Email already exists"}), 400

    if data['password'] != data['confirmPassword']:
        return jsonify({"message": "Passwords do not match"}), 400

    # ใช้ฟังก์ชัน get_next_user_id ในการเพิ่ม user_id
    new_user_id = get_next_user_id()

    user = {
        "user_id": new_user_id,  # กำหนด user_id จากการคำนวณ
        "full_name": data['fullName'],
        "email": data['email'],
        "password": generate_password_hash(data['password']),
        "created_at": datetime.utcnow()
    }
    result = users_collection.insert_one(user)
    
    return jsonify({"message": "User registered successfully", "user_id": new_user_id}), 201

# API สำหรับการล็อคอิน
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()  # รับข้อมูลจาก request body (JSON)

    # ค้นหาผู้ใช้ในฐานข้อมูลด้วยอีเมล
    user = users_collection.find_one({"email": data['email']})
    
    # ตรวจสอบผู้ใช้และรหัสผ่าน
    if user and check_password_hash(user['password'], data['password']):
        # ส่งข้อมูล user_id และข้อมูลอื่น ๆ กลับไป
        return jsonify({
            "message": "Login successful",
            "user": {
                "user_id": user['user_id'],  # ใช้ user_id แทน _id
                "full_name": user['full_name'],
                "email": user['email']
            }
        }), 200
    
    # หากไม่พบผู้ใช้หรือรหัสผ่านไม่ถูกต้อง
    return jsonify({"message": "Invalid email or password"}), 400

# API สำหรับดึงข้อมูลสินค้าของผู้ใช้
@app.route('/get_items/<user_id>', methods=['GET'])
def get_items(user_id):
    items = list(items_collection.find({"user_id": int(user_id)}))  # เชื่อมโยง user_id โดยใช้ int()
    for item in items:
        item['_id'] = str(item['_id'])
        item['user_id'] = str(item['user_id'])
    return jsonify(items), 200

# API สำหรับการเพิ่มสินค้า
@app.route('/add_item', methods=['POST'])
def add_item():
    try:
        data = request.get_json()
        print("Received data:", data)  # เพิ่ม log เพื่อตรวจสอบข้อมูลที่รับมา

        required_fields = ['name', 'storage', 'storage_date', 'expiration_date', 'quantity', 'note']
        if not all(field in data for field in required_fields):
            return jsonify({"message": "Missing required fields"}), 400

        user_id = data.get('user_id')
        if not user_id:
            return jsonify({"message": "User ID is required"}), 400

        user = users_collection.find_one({"user_id": user_id})
        if not user:
            return jsonify({"message": "User not found"}), 400

        try:
            storage_date = datetime.strptime(data['storage_date'], "%Y-%m-%d")
            expiration_date = datetime.strptime(data['expiration_date'], "%Y-%m-%d")
        except ValueError:
            return jsonify({"message": "Invalid date format. Use YYYY-MM-DD."}), 400
        
        item = {
            "photo": data.get('photo'),
            "name": data.get('name'),
            "storage": data.get('storage'),
            "storage_date": storage_date,
            "expiration_date": expiration_date,
            "quantity": int(data.get('quantity')),
            "note": data.get('note'),
            "user_id": user_id
        }

        result = items_collection.insert_one(item)
        return jsonify({"message": "Item added successfully", "id": str(result.inserted_id)}), 201
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return jsonify({"message": "Internal server error"}), 500
    
# API สำหรับดึงข้อมูลผู้ใช้ทั้งหมด
@app.route('/get_users', methods=['GET'])
def get_users():
    users = list(users_collection.find())
    for user in users:
        user['_id'] = str(user['_id'])
        user['user_id'] = str(user['user_id'])
    return jsonify(users), 200

# API สำหรับการลบบัญชีผู้ใช้
@app.route('/delete_account', methods=['DELETE'])
def delete_account():
    data = request.get_json()
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({"message": "Missing user_id"}), 400

    # ลบข้อมูลใน users_collection
    result = users_collection.delete_one({"user_id": int(user_id)})
    
    if result.deleted_count > 0:
        # ลบข้อมูลใน items_collection ที่เชื่อมโยงกับ user_id
        items_collection.delete_many({"user_id": int(user_id)})
        return jsonify({"message": "Account deleted successfully"}), 200
    return jsonify({"message": "User not found"}), 404

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5001, debug=True)

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
        return jsonify({"message": "Email already exists"}), 400  # ส่งข้อความบอกว่าอีเมลนี้มีในระบบแล้ว

    if data['password'] != data['confirmPassword']:
        return jsonify({"message": "Passwords do not match"}), 400

    # ใช้ _id ของ MongoDB โดยไม่ต้องกำหนด user_id
    user = {
        "full_name": data['fullName'],
        "email": data['email'],
        "password": generate_password_hash(data['password']),
        "created_at": datetime.utcnow()
    }
    result = users_collection.insert_one(user)
    
    return jsonify({"message": "User registered successfully", "id": str(result.inserted_id)}), 201

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
                "_id": str(user['_id']),  # ส่ง _id เป็น string
                "full_name": user['full_name'],
                "email": user['email']
            }
        }), 200
    
    # หากไม่พบผู้ใช้หรือรหัสผ่านไม่ถูกต้อง
    return jsonify({"message": "Invalid email or password"}), 400

# API สำหรับดึงข้อมูลสินค้าของผู้ใช้
@app.route('/get_items/<user_id>', methods=['GET'])
def get_items(user_id):
    # ใช้ _id ของผู้ใช้ในการค้นหาข้อมูลสินค้าที่เชื่อมโยง
    items = list(items_collection.find({"user_id": user_id}))  # ใช้ _id โดยตรง
    for item in items:
        item['_id'] = str(item['_id'])
    return jsonify(items), 200

@app.route('/add_item', methods=['POST'])
def add_item():
    try:
        data = request.get_json()

        # ตรวจสอบว่ามีการส่ง user_id มาหรือไม่
        if not data.get('_id'):
            return jsonify({"message": "Missing user_id"}), 400  # แจ้งข้อผิดพลาดหากไม่มี _id

        # เช็คข้อมูลที่ได้รับจาก body ว่ามีข้อมูลครบถ้วนไหม
        required_fields = ['name', 'storage', 'storage_date', 'expiration_date', 'quantity', 'note', '_id']
        if not all(field in data for field in required_fields):
            return jsonify({"message": "Missing required fields"}), 400

        # แปลงวันที่ให้เป็น datetime object และจัดการข้อผิดพลาด
        try:
            storage_date = datetime.strptime(data['storage_date'], "%Y-%m-%d")
            expiration_date = datetime.strptime(data['expiration_date'], "%Y-%m-%d")
        except ValueError:
            return jsonify({"message": "Invalid date format. Use YYYY-MM-DD."}), 400
        
        # เตรียมข้อมูลที่จะบันทึกลงใน MongoDB
        item = {
            "photo": data.get('photo'),  # รูปภาพที่ผู้ใช้ส่งมา
            "name": data.get('name'),
            "storage": data.get('storage'),
            "storage_date": storage_date,
            "expiration_date": expiration_date,
            "quantity": int(data.get('quantity')),
            "note": data.get('note'),
            "user_id": data.get('_id')  # ใช้ _id เป็น primary key (ไม่ต้องแปลงเป็น string)
        }

        # บันทึกข้อมูลลงใน MongoDB
        result = items_collection.insert_one(item)

        return jsonify({"message": "Item added successfully", "id": str(result.inserted_id)}), 201
    except Exception as e:
        # แสดงข้อผิดพลาดในกรณีที่เกิดข้อผิดพลาดที่ไม่คาดคิด
        print(f"Error: {e}")
        traceback.print_exc()
        return jsonify({"message": "Internal server error"}), 500

# API สำหรับดึงข้อมูลผู้ใช้ทั้งหมด
@app.route('/get_users', methods=['GET'])
def get_users():
    users = list(users_collection.find())
    for user in users:
        user['_id'] = str(user['_id'])
    return jsonify(users), 200

# API สำหรับการลบบัญชีผู้ใช้
@app.route('/delete_account', methods=['DELETE'])
def delete_account():
    data = request.get_json()
    user_id = data.get('_id')  # ใช้ _id แทน user_id

    if not user_id:
        return jsonify({"message": "Missing _id"}), 400

    # ลบข้อมูลใน users_collection
    result = users_collection.delete_one({"_id": user_id})
    
    if result.deleted_count > 0:
        # ลบข้อมูลใน items_collection ที่เชื่อมโยงกับ _id
        items_collection.delete_many({"user_id": user_id})
        return jsonify({"message": "Account deleted successfully"}), 200
    return jsonify({"message": "User not found"}), 404

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5001, debug=True)

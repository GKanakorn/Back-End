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
counter_collection = db['counter']  # คอลเลกชันสำหรับเก็บ counter

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
        file_url = f"http://your-server-ip:5001/uploads/{filename}"

        return jsonify({"message": "File uploaded successfully", "file_url": file_url}), 201

    return jsonify({"message": "Invalid file type"}), 400


# ฟังก์ชันสำหรับเพิ่ม user_id
def get_next_user_id():
    counter_doc = counter_collection.find_one_and_update(
        {"_id": "user_id"},  # ค้นหาข้อมูลที่มี _id เป็น "user_id"
        {"$inc": {"seq": 1}},  # เพิ่มค่า seq ขึ้น 1
        upsert=True,  # ถ้าไม่พบให้สร้างใหม่
        return_document=True  # ส่งคืนข้อมูลที่ถูกอัปเดต
    )
    return counter_doc["seq"]

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

    # ใช้ฟังก์ชัน get_next_user_id ในการเพิ่ม user_id
    new_user_id = get_next_user_id()

    user = {
        "user_id": new_user_id,  # กำหนด user_id จาก counter
        "full_name": data['fullName'],
        "email": data['email'],
        "password": generate_password_hash(data['password']),
        "created_at": datetime.utcnow()
    }
    result = users_collection.insert_one(user)
    
    return jsonify({"message": "User registered successfully", "id": str(result.inserted_id)}), 201

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# API สำหรับการเข้าสู่ระบบ
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = users_collection.find_one({"email": data['email']})
    
    if user and check_password_hash(user['password'], data['password']):
        return jsonify({"message": "Login successful", "user": {"id": str(user['_id']), "full_name": user['full_name'], "email": user['email']}}), 200
    return jsonify({"message": "Invalid email or password"}), 400

# API สำหรับดึงข้อมูลสินค้าของผู้ใช้
@app.route('/get_items/<user_id>', methods=['GET'])
def get_items(user_id):
    items = list(items_collection.find({"user_id": user_id}))
    for item in items:
        item['_id'] = str(item['_id'])
        item['user_id'] = str(item['user_id'])
    return jsonify(items), 200

@app.route('/add_item', methods=['POST'])
def add_item():
    try:
        data = request.get_json()

        # เช็คข้อมูลที่ได้รับจาก body ว่ามีข้อมูลครบถ้วนไหม
        required_fields = ['name', 'storage', 'storage_date', 'expiration_date', 'quantity', 'note', 'user_id']
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
            "user_id": data.get('user_id')  # ใช้ user_id ที่ล็อกอินแล้ว
        }

        # บันทึกข้อมูลลงใน MongoDB
        result = items_collection.insert_one(item)

        return jsonify({"message": "Item added successfully", "id": str(result.inserted_id)}), 201
    except Exception as e:
        # แสดงข้อผิดพลาดในกรณีที่เกิดข้อผิดพลาดที่ไม่คาดคิด
        print(f"Error: {e}")
        traceback.print_exc()
        return jsonify({"message": "Internal server error"}), 500
# API สำหรับอัปเดตชื่อผู้ใช้
@app.route('/update_profile', methods=['PUT'])
def update_profile():
    data = request.get_json()
    user_id = data.get('user_id')
    new_name = data.get('full_name')
    
    if not user_id or not new_name:
        return jsonify({"message": "Missing user_id or full_name"}), 400
    
    result = users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"full_name": new_name}}
    )
    
    if result.modified_count > 0:
        return jsonify({"message": "Profile updated successfully"}), 200
    return jsonify({"message": "No changes made"}), 400

# สร้างคอลเลกชัน counter ถ้ายังไม่มี
def create_counter_if_not_exists():
    if counter_collection.count_documents({"_id": "user_id"}) == 0:
        counter_collection.insert_one({"_id": "user_id", "seq": 0})

create_counter_if_not_exists()

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
    result = users_collection.delete_one({"user_id": user_id})
    
    if result.deleted_count > 0:
        # ลบข้อมูลใน items_collection ที่เชื่อมโยงกับ user_id
        items_collection.delete_many({"user_id": user_id})
        return jsonify({"message": "Account deleted successfully"}), 200
    return jsonify({"message": "User not found"}), 404

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5001, debug=True)

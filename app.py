import os 
import uuid
import secrets
from flask import Flask, request, jsonify, render_template, session, redirect
from flask_session import Session
from flask_mail import Mail, Message
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# MongoDB setup
client = MongoClient("mongodb://localhost:27017/")
db = client["eoxs_chatbot"]
collection = db["complaints"]

# Flask-Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')

app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

mail = Mail(app)

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/ask', methods=['POST'])
def ask():
    data = request.get_json()
    raw_question = data.get("question", "").strip()
    question = raw_question.lower()
    employee_id = data.get("employee_id")
    employee_email = data.get("employee_email")

    if employee_id and employee_email:
        session["employee_id"] = employee_id
        session["employee_email"] = employee_email

    if question == "menu":
        session.clear()
        session["state"] = "menu"
        session["employee_id"] = employee_id
        session["employee_email"] = employee_email

    if "state" not in session:
        session["state"] = "menu"

    state = session["state"]

    if state == "menu":
        session["state"] = "waiting_for_option"
        return jsonify({"reply": "What would you like to do?\n1️⃣ Register a Complaint\n2️⃣ Check Complaint Status\n(Please type 1 or 2)"})

    elif state == "waiting_for_option":
        if question == "1":
            session["state"] = "waiting_for_category"
            return jsonify({"reply": "Please select the issue category:\n1. Manager behavior\n2. Harassment/Discrimination\n3. Mental health or emotional safety\n4. HR or company policy conflict\n5. Payroll/compensation issue\n6. Burnout or workload mismanagement\n7. Ethics or misconduct\n8. Infrastructure/tech problems\n9. Interpersonal/team conflict\n10. Posh\n11. General feedback"})
        elif question == "2":
            session["state"] = "checking_status"
            complaint = collection.find_one({"employee_id": session.get("employee_id")})
            if complaint and complaint.get("reply"):
                session["state"] = "menu"
                return jsonify({"reply": f"📩 Admin Reply: {complaint['reply']}\nWould you like to mark this issue as resolved?\nType 'yes' to continue."})
            else:
                session["state"] = "menu"
                return jsonify({"reply": "⏳ Your complaint is still being reviewed. Please check again later."})
        else:
            return jsonify({"reply": "Please enter a valid option: 1 or 2"})

    elif state == "waiting_for_category":
        categories = {
            "1": "Manager behavior",
            "2": "Harassment/Discrimination",
            "3": "Mental health or emotional safety",
            "4": "HR or company policy conflict",
            "5": "Payroll/compensation issue",
            "6": "Burnout or workload mismanagement",
            "7": "Ethics or misconduct",
            "8": "Infrastructure/tech problems",
            "9": "Interpersonal/team conflict",
            "10": "Posh",
            "11": "General feedback"
        }
        category_number = None
        for key, value in categories.items():
            if question == key or question == value.lower():
                category_number = key
                break

        if category_number:
            session["issue"] = categories[category_number]
            session["state"] = "waiting_for_target_department"
            return jsonify({"reply": "Who do you want to send this to?\n1️⃣ HR\n2️⃣ Management\n(Please type 1 or 2)"})
        else:
            return jsonify({"reply": "Please choose a valid option (1-11) for your complaint category."})

    elif state == "waiting_for_target_department":
        if question == "1":
            session["target_department"] = "HR"
        elif question == "2":
            session["target_department"] = "Management"
        else:
            return jsonify({"reply": "Please choose a valid option: 1 for HR or 2 for Management."})

        session["state"] = "waiting_for_complaint"
        return jsonify({"reply": f"Please describe your issue regarding: {session.get('issue')} (To: {session.get('target_department')})"})

    elif state == "waiting_for_complaint":
        issue = session.get("issue", "General")
        target_department = session.get("target_department", "HR")
        complaint_text = raw_question
        ticket_id = str(uuid.uuid4())[:8]
        collection.insert_one({
            "employee_id": session.get("employee_id"),
            "department": target_department,
            "issue": issue,
            "explanation": complaint_text,
            "status": "Pending",
            "employee_email": session.get("employee_email", ""),
            "ticket_id": ticket_id,
            "timestamp": datetime.now(),
            "timeline": [
                {
                    "action": "Complaint submitted",
                    "timestamp": datetime.now(),
                    "description": f"Complaint submitted under '{issue}' to {target_department}."
                }
            ]
                
        })
        session["last_complaint"] = {"department": target_department, "issue": issue, "text": complaint_text}
        session["state"] = "submitted"
        return jsonify({"reply": f"✅ Thank you! Your complaint (Ticket ID: {ticket_id}) has been submitted to {target_department} under '{issue}'.\nWould you like to register another complaint? (yes/no)"})

    elif state == "submitted":
        if "yes" in question:
            session["state"] = "waiting_for_category"
            return jsonify({"reply": "Please select the issue category:\n1. Manager behavior\n2. Harassment/Discrimination\n3. Mental health or emotional safety\n4. HR or company policy conflict\n5. Payroll/compensation issue\n6. Burnout or workload mismanagement\n7. Ethics or misconduct\n8. Infrastructure/tech problems\n9. Interpersonal/team conflict\n10. Posh\n11. General feedback"})
        else:
            session["state"] = "menu"
            return jsonify({"reply": "👍 Thank you for using the EOXS Chatbot. Have a nice day!"})

    return jsonify({"reply": "I'm not sure how to help with that. Please type 'menu' to begin again."})


@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "admin" and password == "admin123":
            complaints = list(collection.find())
            for c in complaints:
                c["is_sensitive"] = c.get("issue", "").lower() in [
                    "harassment/discrimination",
                    "mental health or emotional safety",
                    "ethics or misconduct",
                    "posh"
                ]

            replied_count = sum(1 for c in complaints if c.get("reply"))
            pending_count = sum(1 for c in complaints if not c.get("reply"))
            return render_template("admin_dashboard.html", complaints=complaints, replied_count=replied_count, pending_count=pending_count)
        else:
            return "❌ Invalid Credentials", 401
    return render_template("admin_login.html")

@app.route("/reply/<complaint_id>", methods=["POST"])
def reply_complaint(complaint_id):
    reply_text = request.form.get("reply")

    complaint = collection.find_one({"_id": ObjectId(complaint_id)})
    if not complaint:
        return "Complaint not found", 404

    collection.update_one(
        {"_id": ObjectId(complaint_id)},
        {
            "$set": {"reply": reply_text, "status": "Replied"},
            "$push": {
                "timeline": {
                    "action": "Admin replied",
                    "timestamp": datetime.now(),
                    "description": reply_text
                }
            }
        }
    )
    employee_email = complaint.get("employee_email")
    employee_id = complaint.get("employee_id")
    ticket_id = complaint.get("ticket_id", "N/A")
    issue = complaint.get("issue", "your complaint")

    if employee_email:
        try:
            msg = Message(
                subject=f"LC: Response to Your Complaint Regarding {issue}",
                sender=app.config['MAIL_USERNAME'],
                recipients=[employee_email]
            )
            msg.html = f"""
            <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <p style="font-size: 24px; color: #2e7d32; font-weight: bold; margin-bottom: 20px;">
                    🔔 Response to Your Complaint Regarding <strong>{issue}</strong>
                </p>

                <p><strong>Dear Employee,</strong></p>
                
                <p><strong>👤 Employee ID:</strong> {employee_id}<br>
                <strong>🎟️ Ticket ID:</strong> {ticket_id}</p>
                
                <p>We have received your complaint regarding <strong>{issue}</strong>, and we truly regret that you had to face this issue.<br>
                Your concern has been taken seriously, and we assure you of our commitment to creating a safe and respectful workplace.</p>

                <div style="background-color: #f1f1f1; padding: 12px; border-left: 4px solid #2e7d32; margin: 15px 0;">
                    <strong>📝 Admin's Response:</strong><br>
                    {reply_text}
                </div>

                <p>Thank you for bringing this to our attention.</p>

                <p>Warm regards,<br>
                <strong>Lokesh Team</strong></p>
            </div>
            """
            mail.send(msg)
        except Exception as e:
            print("Email send error:", e)

    complaints = list(collection.find())
    for c in complaints:
        c["is_sensitive"] = c.get("issue", "").lower() in [
            "harassment/discrimination",
            "mental health or emotional safety",
            "ethics or misconduct",
            "posh"
        ]

    replied_count = sum(1 for c in complaints if c.get("reply"))
    pending_count = sum(1 for c in complaints if not c.get("reply"))
    return render_template("admin_dashboard.html", complaints=complaints, replied_count=replied_count, pending_count=pending_count)

@app.route('/deleteComplaint/<complaint_id>', methods=['DELETE'])
def delete_complaint(complaint_id):
    try:
        result = collection.delete_one({'_id': ObjectId(complaint_id)})
        if result.deleted_count == 1:
            return jsonify({'message': 'Complaint deleted successfully'}), 200
        else:
            return jsonify({'error': 'Complaint not found'}), 404
    except Exception as e:
        print(f"Error deleting complaint: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/search', methods=['GET'])
def search_complaints():
    issue_filter = request.args.get('issue', '')
    search_id = request.args.get('searchId', '').strip()
    filter_days = request.args.get('filterDays', '')
    sensitive_only = request.args.get('sensitiveOnly') == 'true'

    query = {}

    # Filter by ID
    if search_id:
        try:
            query['_id'] = ObjectId(search_id)
        except Exception:
            return jsonify([])  # Invalid ID format

    # Filter by Issue
    if issue_filter:
        query['issue'] = issue_filter

    # Filter by Sensitive checkbox
    if sensitive_only:
        query['sensitive'] = True

    # Filter by Days
    if filter_days:
        now = datetime.now()
        if filter_days == 'today':
            start = datetime(now.year, now.month, now.day)
            end = start + timedelta(days=1)
            query['timestamp'] = {'$gte': start, '$lt': end}
        elif filter_days == 'last7':
            start = now - timedelta(days=7)
            query['timestamp'] = {'$gte': start}
        elif filter_days == 'last30':
            start = now - timedelta(days=30)
            query['timestamp'] = {'$gte': start}
        elif filter_days == 'all':
            pass  # No date filter applied

    complaints = list(complaints_collection.find(query).sort('timestamp', -1))

    for complaint in complaints:
        complaint['_id'] = str(complaint['_id'])
        complaint['timestamp'] = complaint['timestamp'].strftime('%Y-%m-%d %H:%M')

    return jsonify(complaints)


@app.route('/stats', methods=['GET'])
def complaint_stats():
    total = collection.count_documents({})
    replied = collection.count_documents({"reply": {"$exists": True}})
    pending = collection.count_documents({"reply": {"$exists": False}})
    return jsonify({
        "total": total,
        "replied": replied,
        "pending": pending
    })


if __name__ == '__main__':
    app.run(debug=True)




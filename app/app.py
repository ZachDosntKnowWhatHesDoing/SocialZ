from flask import Flask, request, jsonify
from models import db, User, Notification
import os

app = Flask(__name__)

# ---------------------
# Config
# ---------------------
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

# Create tables
with app.app_context():
    db.create_all()

# ---------------------
# Routes
# ---------------------

# Signup route
@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if User.query.filter_by(username=username).first():
        return jsonify({"status": "error", "message": "Username already exists"})

    new_user = User(username=username, password=password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"status": "ok", "user_id": new_user.id})

# Login route
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    user = User.query.filter_by(username=username, password=password).first()
    if user:
        return jsonify({"status": "ok", "user_id": user.id})
    else:
        return jsonify({"status": "error", "message": "Invalid login"})

# Add notification
@app.route("/notifications", methods=["POST"])
def add_notification():
    data = request.json
    recipient_id = data.get("recipient_id")
    sender_id = data.get("sender_id")
    message = data.get("message")

    notif = Notification(user_id=recipient_id, sender_id=sender_id, message=message)
    db.session.add(notif)
    db.session.commit()

    return jsonify({"status": "ok", "notification_id": notif.id})

# Get notifications for a user
@app.route("/notifications/<int:user_id>", methods=["GET"])
def get_notifications(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"status": "error", "message": "User not found"})

    result = []
    for n in user.notifications:
        result.append({
            "id": n.id,
            "message": n.message,
            "sender_id": n.sender_id,
            "timestamp": n.timestamp.isoformat()
        })

    return jsonify(result)

# ---------------------
# Run app
# ---------------------
if __name__ == "__main__":
    app.run(debug=True)

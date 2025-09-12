from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# ---------------------
# User model
# ---------------------
class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

    # Notifications received
    notifications = db.relationship(
        "Notification",
        backref="recipient",
        foreign_keys="Notification.user_id",
        lazy=True
    )

    # Notifications sent (optional)
    sent_notifications = db.relationship(
        "Notification",
        backref="sender",
        foreign_keys="Notification.sender_id",
        lazy=True
    )

# ---------------------
# Notification model
# ---------------------
class Notification(db.Model):
    __tablename__ = "notification"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)   # recipient
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)   # sender
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

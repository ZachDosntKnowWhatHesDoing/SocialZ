from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    # ... (User model code here)

class Notification(db.Model):
    # ... (Notification model code here)

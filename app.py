from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from PIL import Image
import os

# --- Role system helper ---
def role_required(role):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user" not in session:
                flash("You must be logged in.")
                return redirect(url_for("login"))

            username = session["user"]
            user_role = users.get(username, {}).get("role", "user")

            # Allow if role matches OR if admin (admins override)
            if user_role != role and user_role != "admin":
                flash("You don’t have permission to do that.")
                return redirect(url_for("index"))

            return f(*args, **kwargs)
        return decorated_function
    return wrapper


# --- Mod Panel ---
@app.route("/mod-panel")
@role_required("mod")
def mod_panel():
    return render_template("mod_panel.html", users=users, posts=posts)


# --- Admin Panel ---
@app.route("/admin-panel")
@role_required("admin")
def admin_panel():
    return render_template("admin_panel.html", users=users, posts=posts)


# --- Promote/Demote users (Admin only) ---
@app.route("/set-role/<username>/<role>")
@role_required("admin")
def set_role(username, role):
    if username in users:
        users[username]["role"] = role
        save_users()  # make sure you have a save_users() that writes to users.json
        flash(f"{username} is now {role}.")
    else:
        flash("User not found.")
    return redirect(url_for("admin_panel"))

# ---------------- App Setup -----------------
app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['UPLOAD_FOLDER'] = 'static/profile_pics'
app.config['POST_IMAGE_FOLDER'] = 'static/post_images'
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///local.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['POST_IMAGE_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# ---------------- Database Models -----------------
followers_table = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

likes_table = db.Table('likes',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'))
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    bio = db.Column(db.Text, default="")
    profile_pic = db.Column(db.String(120), nullable=True)
    
    posts = db.relationship('Post', backref='author', lazy=True)
    following = db.relationship('User',
                                secondary=followers_table,
                                primaryjoin=id==followers_table.c.follower_id,
                                secondaryjoin=id==followers_table.c.followed_id,
                                backref='followers')

    messages_sent = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy=True)
    messages_received = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True)
    
    def is_mod(self):
        return self.username in ['terminator', 'Admin']

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=True)
    image = db.Column(db.String(120), nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    comments = db.relationship('Comment', backref='post', lazy=True)
    likes = db.relationship('User', secondary=likes_table, backref='liked_posts')

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    author = db.relationship('User', backref='comments')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50))
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    read = db.Column(db.Boolean, default=False)

# ---------------- Jinja Utils -----------------
@app.context_processor
def utility_processor():
    def get_profile_pic(user):
        if user.profile_pic:
            return url_for('static', filename='profile_pics/' + user.profile_pic)
        return url_for('static', filename='profile_pics/default.png')

    def display_name(user):
        if user.is_mod():
            return f"{user.username} [MOD]"
        return user.username

    return dict(get_profile_pic=get_profile_pic, display_name=display_name)

# ---------------- Routes -----------------
@app.route('/')
def index():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        feed = Post.query.order_by(Post.id.desc()).limit(20).all()
        return render_template('index.html', user=user, feed=feed)
    return redirect(url_for('login'))

# ---------------- Signup/Login/Logout -----------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash("Username already exists")
        elif username.lower() in ["zach", "creator", "owner", "admin123", "administrator", "root", "god", "mod"]:
            flash("This username is not allowed")
        else:
            new_user = User(username=username, password=password)
            db.session.add(new_user)
            db.session.commit()
            session['user_id'] = new_user.id
            return redirect(url_for('index'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method=='POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            return redirect(url_for('index'))
        flash("Invalid username or password")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

# ---------------- Profile -----------------
@app.route('/profile/<username>')
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    feed = Post.query.order_by(Post.id.desc()).all()
    return render_template('profile.html', user=user, feed=feed, followers=user.followers, data=user)

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if request.method=='POST':
        user.bio = request.form['bio']
        if 'profile_pic' in request.files:
            pic = request.files['profile_pic']
            if pic.filename != '':
                filename = secure_filename(user.username + "_" + pic.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                pic.save(filepath)
                img = Image.open(filepath)
                img = img.resize((40, 40), Image.Resampling.LANCZOS)
                img.save(filepath)
                user.profile_pic = filename
        db.session.commit()
        return redirect(url_for('profile', username=user.username))
    return render_template('edit_profile.html', data=user)

# ---------------- Posts -----------------
@app.route('/post', methods=['POST'])
def create_post():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    content = request.form['content'].strip()
    image_file = None
    if 'post_image' in request.files:
        pic = request.files['post_image']
        if pic.filename != '':
            filename = secure_filename(user.username + "_" + pic.filename)
            filepath = os.path.join(app.config['POST_IMAGE_FOLDER'], filename)
            pic.save(filepath)
            img = Image.open(filepath)
            img.thumbnail((600,600), Image.Resampling.LANCZOS)
            img.save(filepath)
            image_file = filename
    new_post = Post(content=content, image=image_file, author=user)
    db.session.add(new_post)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/like/<int:post_id>')
def like_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    post = Post.query.get_or_404(post_id)
    if user in post.likes:
        post.likes.remove(user)
    else:
        post.likes.append(user)
        if user != post.author:
            notif = Notification(type="like", from_user_id=user.id, user_id=post.author.id, post_id=post.id)
            db.session.add(notif)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/comment/<int:post_id>', methods=['POST'])
def comment_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    post = Post.query.get_or_404(post_id)
    comment_text = request.form['comment'].strip()
    if comment_text:
        comment = Comment(content=comment_text, author=user, post=post)
        db.session.add(comment)
        if user != post.author:
            notif = Notification(type="comment", from_user_id=user.id, user_id=post.author.id, post_id=post.id)
            db.session.add(notif)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete_post/<int:post_id>')
def delete_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    post = Post.query.get_or_404(post_id)
    if user.is_mod() or post.author==user:
        db.session.delete(post)
        db.session.commit()
    return redirect(url_for('index'))

# ---------------- Follow -----------------
@app.route('/follow/<username>')
def follow(username):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    target = User.query.filter_by(username=username).first_or_404()
    if target != user and target not in user.following:
        user.following.append(target)
        notif = Notification(type="follow", from_user_id=user.id, user_id=target.id)
        db.session.add(notif)
        db.session.commit()
    return redirect(url_for('profile', username=username))

# ---------------- DM -----------------
@app.route('/dm/<username>', methods=['GET','POST'])
def dm(username):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    target = User.query.filter_by(username=username).first_or_404()
    if request.method=='POST':
        msg_text = request.form['message'].strip()
        if msg_text:
            message = Message(sender=user, receiver=target, content=msg_text)
            db.session.add(message)
            notif = Notification(type="dm", from_user_id=user.id, user_id=target.id)
            db.session.add(notif)
            db.session.commit()
        return redirect(url_for('dm', username=username))
    msgs = Message.query.filter(
        ((Message.sender==user) & (Message.receiver==target)) |
        ((Message.sender==target) & (Message.receiver==user))
    ).all()
    return render_template('dm.html', messages=msgs, chat_with=target.username)

# ---------------- Notifications -----------------
@app.route('/notifications')
def notifications_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    notifs = Notification.query.filter_by(user=user).all()
    for n in notifs:
        n.read = True
    db.session.commit()
    return render_template('notifications.html', notifications=notifs)

# ---------------- Run -----------------
if __name__=="__main__":
    db.create_all()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

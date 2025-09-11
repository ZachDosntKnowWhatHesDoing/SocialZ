import os
import json
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename
from PIL import Image

app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = 'static/profile_pics'
app.config['POST_IMAGE_FOLDER'] = 'static/post_images'
DATA_FOLDER = 'data'

os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['POST_IMAGE_FOLDER'], exist_ok=True)

USERS_FILE = os.path.join(DATA_FOLDER, 'users.json')
POSTS_FILE = os.path.join(DATA_FOLDER, 'posts.json')
FOLLOWERS_FILE = os.path.join(DATA_FOLDER, 'followers.json')
MESSAGES_FILE = os.path.join(DATA_FOLDER, 'messages.json')
NOTIFICATIONS_FILE = os.path.join(DATA_FOLDER, 'notifications.json')

BLACKLIST = ["Zach", "Creator", "Owner", "Admin123", "Administrator", "Root", "God", "Mod"]
MODS = ['terminator', 'Admin']

# ---------------- JSON helpers -----------------
def load_json(path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, 'r') as f:
            return json.load(f)
    return {}

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)

# ---------------- Load all data -----------------
users = load_json(USERS_FILE)
posts_data = load_json(POSTS_FILE)
posts = posts_data.get('posts', [])
followers = load_json(FOLLOWERS_FILE)
messages = load_json(MESSAGES_FILE)
notifications = load_json(NOTIFICATIONS_FILE)

# Ensure posts have IDs, likes, comments
next_id = 1
for p in posts:
    if 'id' not in p:
        p['id'] = next_id
        next_id += 1
    else:
        next_id = max(next_id, p['id'] + 1)
    if 'likes' not in p:
        p['likes'] = []
    if 'comments' not in p:
        p['comments'] = []

# ---------------- Save notifications -----------------
def save_notifications():
    save_json(NOTIFICATIONS_FILE, notifications)

# ---------------- Jinja utils -----------------
@app.context_processor
def utility_processor():
    def get_profile_pic(username):
        if users.get(username) and users[username].get('profile_pic'):
            return url_for('static', filename='profile_pics/' + users[username]['profile_pic'])
        return url_for('static', filename='profile_pics/default.png')

    def display_name(username):
        if username in MODS:
            return f"{username} [MOD]"
        return username

    return dict(get_profile_pic=get_profile_pic, display_name=display_name, notifications=notifications)

# ---------------- Routes -----------------
@app.route('/')
def index():
    if 'user' in session:
        username = session['user']
        feed = sorted(posts[-20:], key=lambda x: x['id'], reverse=True)
        return render_template('index.html', user=username, feed=feed)
    return redirect(url_for('login'))

@app.route('/posts')
def fetch_posts():
    return jsonify(posts)

# ---------------- Signup/Login/Logout -----------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if username in users:
            flash('Username already exists')
        elif username in BLACKLIST or username.lower() in [u.lower() for u in users.keys() if u != "Admin"]:
            flash('This username is not allowed')
        else:
            users[username] = {'password': password, 'profile_pic': None, 'bio': ''}
            followers[username] = []
            messages[username] = []
            notifications[username] = []
            save_json(USERS_FILE, users)
            save_json(FOLLOWERS_FILE, followers)
            save_json(MESSAGES_FILE, messages)
            save_notifications()
            session['user'] = username
            return redirect(url_for('index'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and users[username]['password'] == password:
            session['user'] = username
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# ---------------- Profile -----------------
@app.route('/profile/<username>')
def profile(username):
    if username not in users:
        return "User not found"
    user_data = users[username]
    user_followers = [u for u, f in followers.items() if username in f]
    feed = sorted(posts, key=lambda x: x['id'], reverse=True)
    return render_template('profile.html', user=username, data=user_data, followers=user_followers, feed=feed)

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user' not in session:
        return redirect(url_for('login'))
    username = session['user']
    if request.method == 'POST':
        bio = request.form['bio']
        users[username]['bio'] = bio
        if 'profile_pic' in request.files:
            pic = request.files['profile_pic']
            if pic.filename != '':
                filename = secure_filename(username + "_" + pic.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                pic.save(filepath)
                img = Image.open(filepath)
                img = img.resize((40, 40), Image.Resampling.LANCZOS)
                img.save(filepath)
                users[username]['profile_pic'] = filename
        save_json(USERS_FILE, users)
        return redirect(url_for('profile', username=username))
    return render_template('edit_profile.html', data=users[username])

# ---------------- Follow/DM -----------------
@app.route('/follow/<username>')
def follow(username):
    if 'user' not in session:
        return redirect(url_for('login'))
    follower = session['user']
    if username in users and username != follower:
        if username not in followers[follower]:
            followers[follower].append(username)
            save_json(FOLLOWERS_FILE, followers)

            # Notify user
            notifications.setdefault(username, []).append({
                "type": "follow",
                "from": follower,
                "read": False
            })
            save_notifications()

    return redirect(url_for('profile', username=username))

@app.route('/dm/<username>', methods=['GET', 'POST'])
def dm(username):
    if 'user' not in session:
        return redirect(url_for('login'))
    sender = session['user']
    if username not in users:
        return "User not found"
    if request.method == 'POST':
        message = request.form['message']
        messages[username].append({'from': sender, 'message': message})
        messages[sender].append({'from': sender, 'message': message})
        save_json(MESSAGES_FILE, messages)

        # Notify receiver
        if username != sender:
            notifications.setdefault(username, []).append({
                "type": "dm",
                "from": sender,
                "read": False
            })
            save_notifications()

        return redirect(url_for('dm', username=username))
    dm_list = [m for m in messages[username] if m['from'] == username or m['from'] == sender]
    return render_template('dm.html', chat_with=username, messages=dm_list)

# ---------------- Posts -----------------
def get_post(post_id):
    for p in posts:
        if p['id'] == post_id:
            return p
    return None

@app.route('/post', methods=['POST'])
def create_post():
    if 'user' not in session:
        return redirect(url_for('login'))

    content = request.form['content'].strip()
    image_file = None

    if 'post_image' in request.files:
        pic = request.files['post_image']
        if pic.filename != '':
            filename = secure_filename(session['user'] + "_" + pic.filename)
            filepath = os.path.join(app.config['POST_IMAGE_FOLDER'], filename)
            pic.save(filepath)
            img = Image.open(filepath)
            img.thumbnail((600, 600), Image.Resampling.LANCZOS)
            img.save(filepath)
            image_file = filename

    if content or image_file:
        post_id = (posts[-1]['id'] + 1) if posts else 1
        posts.append({
            'id': post_id,
            'author': session['user'],
            'content': content,
            'image': image_file,
            'likes': [],
            'comments': []
        })
        save_json(POSTS_FILE, {'posts': posts})

    return redirect(url_for('index'))

@app.route('/like/<int:post_id>')
def like_post(post_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    post = get_post(post_id)
    if post:
        user = session['user']
        if user in post['likes']:
            post['likes'].remove(user)
        else:
            post['likes'].append(user)

            # Notify author
            if post['author'] != user:
                notifications.setdefault(post['author'], []).append({
                    "type": "like",
                    "from": user,
                    "post_id": post_id,
                    "read": False
                })
                save_notifications()

        save_json(POSTS_FILE, {'posts': posts})
    return redirect(url_for('index'))

@app.route('/comment/<int:post_id>', methods=['POST'])
def comment_post(post_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    post = get_post(post_id)
    if post:
        comment_text = request.form['comment'].strip()
        if comment_text:
            post['comments'].append({'author': session['user'], 'comment': comment_text})

            # Notify author
            if post['author'] != session['user']:
                notifications.setdefault(post['author'], []).append({
                    "type": "comment",
                    "from": session['user'],
                    "post_id": post_id,
                    "read": False
                })
                save_notifications()

            save_json(POSTS_FILE, {'posts': posts})
    return redirect(url_for('index'))

@app.route('/delete_post/<int:post_id>')
def delete_post(post_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    post = get_post(post_id)
    current_user = session['user']

    if post:
        if current_user == 'Admin':
            posts.remove(post)
        elif current_user == 'terminator' and post['author'] != 'Admin':
            posts.remove(post)
        elif post['author'] == current_user:
            posts.remove(post)

        if post not in posts:
            save_json(POSTS_FILE, {'posts': posts})

    return redirect(url_for('index'))

# ---------------- Notifications page -----------------
@app.route('/notifications')
def view_notifications():
    if 'user' not in session:
        return redirect(url_for('login'))
    user = session['user']
    user_notifications = notifications.get(user, [])

    # Mark all as read
    for n in user_notifications:
        n['read'] = True
    save_notifications()

    return render_template('notifications.html', notifications=user_notifications)

# ---------------- Run -----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

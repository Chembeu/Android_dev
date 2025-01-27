from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import datetime

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat_api.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Friend(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # pending, accepted, declined

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class GroupMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role = db.Column(db.String(20), default='member')  # admin, member

class GroupMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# Initialize the database
with app.app_context():
    db.create_all()

# Routes

## User Management
@app.route('/register', methods=['POST'])
def register_user():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify({'error': 'All fields are required'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already exists'}), 400

    new_user = User(username=username, email=email, password=password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'id': new_user.id, 'username': new_user.username, 'email': new_user.email}), 201

@app.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([{'id': user.id, 'username': user.username, 'email': user.email} for user in users])

## Friend Management
@app.route('/friends/request', methods=['POST'])
def send_friend_request():
    data = request.json
    sender_id = data.get('sender_id')
    receiver_id = data.get('receiver_id')

    if not sender_id or not receiver_id:
        return jsonify({'error': 'Both sender_id and receiver_id are required'}), 400

    friend_request = Friend(sender_id=sender_id, receiver_id=receiver_id, status='pending')
    db.session.add(friend_request)
    db.session.commit()

    return jsonify({'message': 'Friend request sent'}), 201

@app.route('/friends/pending', methods=['GET'])
def get_pending_requests():
    pending_requests = Friend.query.filter_by(status='pending').all()
    return jsonify([{'id': req.id, 'sender_id': req.sender_id, 'receiver_id': req.receiver_id} for req in pending_requests])

@app.route('/friends/accept/<int:request_id>', methods=['PUT'])
def accept_friend_request(request_id):
    friend_request = Friend.query.get(request_id)

    if not friend_request:
        return jsonify({'error': 'Friend request not found'}), 404

    friend_request.status = 'accepted'
    db.session.commit()

    return jsonify({'message': 'Friend request accepted'}), 200

## Messaging
@app.route('/messages/send', methods=['POST'])
def send_message():
    data = request.json
    sender_id = data.get('sender_id')
    receiver_id = data.get('receiver_id')
    content = data.get('content')

    if not sender_id or not receiver_id or not content:
        return jsonify({'error': 'All fields are required'}), 400

    new_message = Message(sender_id=sender_id, receiver_id=receiver_id, content=content)
    db.session.add(new_message)
    db.session.commit()

    socketio.emit('new_message', {
        'sender_id': sender_id,
        'receiver_id': receiver_id,
        'content': content,
        'timestamp': new_message.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    })

    return jsonify({'message': 'Message sent'}), 201

@app.route('/messages/<int:sender_id>/<int:receiver_id>', methods=['GET'])
def get_messages(sender_id, receiver_id):
    messages = Message.query.filter(
        ((Message.sender_id == sender_id) & (Message.receiver_id == receiver_id)) |
        ((Message.sender_id == receiver_id) & (Message.receiver_id == sender_id))
    ).order_by(Message.timestamp).all()

    return jsonify([
        {'id': msg.id, 'sender_id': msg.sender_id, 'receiver_id': msg.receiver_id, 'content': msg.content,
         'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M:%S')} for msg in messages
    ])

# SocketIO Events
@socketio.on('connect')
def handle_connect():
    print('A user connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('A user disconnected')

if __name__ == '__main__':
    socketio.run(app, debug=True)

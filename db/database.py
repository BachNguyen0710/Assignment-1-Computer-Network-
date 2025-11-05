import os
import json
import threading

USER_DATABASE = {}

SESSION_STORE = {}
SESSION_LOCK = threading.Lock()

ACTIVE_PEERS = {}
PEERS_LOCK = threading.Lock()

def load_json():
    global USER_DATABASE
    try:
        dir_path = os.path.dirname(os.path.realpath(__file__))
        json_path = os.path.join(dir_path, 'data.json')
        with open(json_path, 'r') as f:
            data = json.load(f)
            USER_DATABASE = data.get("users", {})
            print(f"[Database] Loaded users: {list(USER_DATABASE.keys())}")
    except Exception as e:
        print(f"[DB] Can't load data.json: {e}")
        print("[DB] Server run with no users.")
        USER_DATABASE = {}

#USER: 
def get_user_database(username):
    return USER_DATABASE.get(username)

#Session:
def create_session(session_id, username):
    with SESSION_LOCK:
        SESSION_STORE[session_id] = username
def get_username_by_session(session_id):
    if not session_id:
        return None
    with SESSION_LOCK:
        return SESSION_STORE.get(session_id)
#Peer:
def register_peer(username, ip, port):
    with PEERS_LOCK:
        ACTIVE_PEERS[username] = {"ip": ip, "port": port}
def get_peers():
    with PEERS_LOCK:
        return ACTIVE_PEERS.copy()
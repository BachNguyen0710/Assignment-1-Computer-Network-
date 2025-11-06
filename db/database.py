import os
import json

DIR_PATH = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(DIR_PATH, "data.json")

def read_json():
    try:
        with open(JSON_PATH, "r") as file:
            return json.load(file)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        return {}
def write_json(data):
    try:
        with open(JSON_PATH, "w") as file:
            json.dump(data, file, indent=4)
    except Exception as e:
        print(f"Error writing JSON file: {e}")
#USER: 
def get_user_database(username):
    data = read_json()
    return data.get("users", {}).get(username)

#Session:
def create_session(session_id, username):
    data = read_json()
    if "session_store" not in data:
        data["session_store"] = {}
    data["session_store"][session_id] = username
    write_json(data)
def get_username_by_session(session_id):
    if not session_id:
        return None
    data = read_json()
    return data.get("session_store", {}).get(session_id)
#Peer:
def register_peer(username, ip, port):
    data = read_json()
    if "active_peer" not in data:
        data["active_peer"] = {}
    data["active_peer"][username] = {"ip": ip, "port": port}
    write_json(data)
def get_peers():
    data = read_json()
    return data.get("active_peer", {})
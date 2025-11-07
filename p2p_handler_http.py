import socket
import threading
import requests
import json
import sys
import time
from queue import Queue

from daemon.weaprous import WeApRous
from daemon.backend import create_backend

HEARTBEAT_INTERVAL = 5


class P2PHandler:
    def __init__(self, message_queue, api_url="http://localhost:8080"):
        self.message_queue = message_queue
        self.API_URL = api_url

        self.session = requests.Session()
        self.peer_list_cache = {}
        self.my_username = ""
        self.my_port = 0
        self.current_channel = "global"

        self.p2p_app = WeApRous()

        self.heartbeat_thread = None
        self.heartbeat_stop_event = threading.Event()

    def _put_message(self, msg):
        self.message_queue.put(msg)

    def login_and_register(self, username, password, port):
        try:
            self._put_message(f"[System] Logging in as {username}...")
            login_data = {"username": username, "password": password}
            response = self.session.post(f"{self.API_URL}/login", data=login_data)

            if response.json().get("login") != "success":
                raise Exception(f"Login Failed: {response.json().get('reason')}")

            self._put_message("[System] Login successful.")
            self.my_username = username
            self.my_port = port
            time.sleep(0.5)

            self.start_p2p_server()

            self._put_message("[System] Registering P2P listener...")
            reg_data = {"port": self.my_port, "client_type": "peer"}
            response = self.session.post(f"{self.API_URL}/register", json=reg_data)

            if response.json().get("status") != "registered":
                raise Exception(f"Register Failed: {response.json().get('reason')}")

            self._put_message(
                f"[System] Successfully registered as '{self.my_username}'."
            )

        except Exception as e:
            self._put_message(f"[Error] {e}")
            raise e

    def get_channel_peers(self):
        self._put_message("[System] Fetching peer list from server...")
        try:
            resp = self.session.post(
                f"{self.API_URL}/channels/peers",
                json={"channel_name": self.current_channel},
            )
            if resp.status_code != 200:
                self._put_message(f"[Error] {resp.json().get('reason')}")
                return

            self.peer_list_cache = resp.json()
            self._put_message(
                f"""[System] Peer list updated. Found {
                    len(self.peer_list_cache)
                } peer(s)."""
            )
        except Exception as e:
            self._put_message(f"[Error] Could not get peer list: {e}")

    def join_channel(self, new_channel):
        try:
            resp = self.session.post(
                f"{self.API_URL}/channels/join", json={"channel_name": new_channel}
            )
            if resp.status_code == 200:
                self.current_channel = new_channel
                self._put_message(f"[System] Joined channel '{new_channel}'.")

            else:
                self._put_message(f"[Error] {resp.json().get('reason')}")
        except Exception as e:
            self._put_message(f"[Error] {e}")

    def _heartbeat_loop(self):
        while not self.heartbeat_stop_event.is_set():
            try:
                self.session.get(f"{self.API_URL}/heartbeat")
            except Exception as e:
                self._put_message(f"[Heartbeat error] {e}")
            self.heartbeat_stop_event.wait(HEARTBEAT_INTERVAL)
        self._put_message("[System] Heartbeat thread stopped.")

    def start_p2p_server(self):
        @self.p2p_app.route("/send-peer", methods=["POST"])
        def receive_peer_message(headers, body):
            try:
                data = json.loads(body)
                message = data.get("message", "Empty Message")
                display_msg = f"--- New Message ---\n{message}\n---------------------"
                self._put_message(display_msg)

                return {"status": "ok", "delivered": True}
            except Exception as e:
                self._put_message(f"[P2P Server Error] {e}")
                return {"status": "error", "reason": str(e)}

        try:
            self.p2p_app.prepare_address("0.0.0.0", self.my_port)
            threading.Thread(
                target=create_backend,
                args=(self.p2p_app.ip, self.p2p_app.port, self.p2p_app.routes),
                daemon=True,
            ).start()

            self._put_message(
                f"[System] P2P HTTP server started on port {self.my_port}."
            )

            self.heartbeat_stop_event.clear()
            self.heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop, daemon=True
            )
            self.heartbeat_thread.start()
            self._put_message("[System] Heartbeat thread started.")

            threading.Thread(target=self.get_channel_peers, daemon=True).start()

        except Exception as e:
            self._put_message(
                f"""[CRITICAL ERROR] Could not start P2P server: {
                    e
                }. Port may be in use. Please restart."""
            )
            raise e

    def send_p2p_message(self, target_ip, target_port, message):
        try:
            payload = {"message": message, "sender": self.my_username}
            requests.post(
                f"http://{target_ip}:{target_port}/send-peer", json=payload, timeout=3
            )
            self._put_message(f"[System] Message sent to {target_ip}:{target_port}")
        except Exception as e:
            self._put_message(
                f"[Error] Could not send to {target_ip}:{target_port}: {e}"
            )

    def broadcast_message(self, message, refresh):
        if refresh:
            t = threading.Thread(target=self.get_channel_peers)
            t.start()
            t.join()
        if not self.peer_list_cache:
            self._put_message(
                "[Error] No peers in this channel. Refresh list or join a channel."
            )
            return

        formatted_message = f"[{self.my_username} @ {self.current_channel}]: {message}"
        self._put_message(f"[Broadcasting...] {message}")

        for user, info in self.peer_list_cache.items():
            if user == self.my_username:
                continue
            threading.Thread(
                target=self.send_p2p_message,
                args=(info["ip"], info["port"], formatted_message),
                daemon=True,
            ).start()
            time.sleep(0.01)

    def shutdown(self):
        if self.heartbeat_stop_event:
            self.heartbeat_stop_event.set()

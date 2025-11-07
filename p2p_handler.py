import socket
import threading
import requests
import json
import sys
import time
from queue import Queue

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

        self.listen_socket = None

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
                self.get_channel_peers()
            else:
                self._put_message(f"[Error] {resp.json().get('reason')}")
        except Exception as e:
            self._put_message(f"[Error] {e}")

    def start_listener(self):
        try:
            self.listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.listen_socket.bind(("0.0.0.0", self.my_port))
            self.listen_socket.listen(5)

            threading.Thread(target=self._listen_for_messages, daemon=True).start()
            self._put_message(f"[System] P2P listener started on port {self.my_port}.")

            self.heartbeat_stop_event.clear()
            self.heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop, daemon=True
            )
            self.heartbeat_thread.start()
            self._put_message("[System] Heartbeat thread started.")

            threading.Thread(target=self.get_channel_peers, daemon=True).start()

        except Exception as e:
            self._put_message(
                f"""[CRITICAL ERROR] Could not start listener: {
                    e
                }. Port may be in use. Please restart."""
            )

    def _heartbeat_loop(self):
        while not self.heartbeat_stop_event.is_set():
            try:
                self.session.get(f"{self.API_URL}/heartbeat")
            except Exception as e:
                self._put_message(f"[Heartbeat error] {e}")
            self.heartbeat_stop_event.wait(HEARTBEAT_INTERVAL)
        self._put_message("[System] Heartbeat thread stopped.")

    def _listen_for_messages(self):
        while True:
            try:
                conn, addr = self.listen_socket.accept()
                threading.Thread(
                    target=self._handle_peer_connection, args=(conn, addr), daemon=True
                ).start()
            except Exception:
                self._put_message("[System] P2P listener shutting down.")
                break

    def _handle_peer_connection(self, conn, addr):
        try:
            data = conn.recv(4096)
            if data:
                message = (
                    f"--- New Message from {addr[0]}:{addr[1]} ---\n"
                    f"{data.decode('utf-8')}\n"
                    f"----------------------------------------"
                )
                self._put_message(message)
        except Exception as e:
            self._put_message(f"\r[Peer Error] {e}")
        finally:
            conn.close()

    def send_p2p_message(self, target_ip, target_port, message):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3)
                s.connect((target_ip, int(target_port)))
                s.sendall(message.encode("utf-8"))
            self._put_message(f"[System] Message sent to {target_ip}:{target_port}")
        except socket.timeout:
            self._put_message(
                f"[Error] Connection to {target_ip}:{target_port} timed out."
            )
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
        if self.listen_socket:
            self.listen_socket.close()
        if self.heartbeat_stop_event:
            self.heartbeat_stop_event.set()

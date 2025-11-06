#
# Copyright (C) 2025 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course,
# and is released under the "MIT License Agreement". Please see the LICENSE
# file that should have been included as part of this package.
#
# WeApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#


"""
start_sampleapp
~~~~~~~~~~~~~~~~~

This module provides a sample RESTful web application using the WeApRous framework.

It defines basic route handlers and launches a TCP-based backend server to serve
HTTP requests. The application includes a login endpoint and a greeting endpoint,
and can be configured via command-line arguments.
"""

import argparse
import json
import random
import string
import threading
import urllib.parse

from daemon.utils import extract_cookies
from daemon.weaprous import WeApRous
from db import database

PORT = 8000  # Default port

app = WeApRous()


def check_registered_status(username):
    if username in database.get_peers():
        return True
    return False


def get_user_from_session(headers):
    cookies = extract_cookies(headers)
    if not cookies or not cookies.get("session_id"):
        return None

    username = database.get_username_by_session(cookies.get("session_id"))
    return username


@app.route("/login", methods=["POST"])
def login(headers, body):
    print(f"[SampleApp] Raw login body: {body}")

    credentials = {}
    try:
        parsed_body = urllib.parse.parse_qs(body)
        credentials["username"] = parsed_body.get("username", [""])[0]
        credentials["password"] = parsed_body.get("password", [""])[0]
    except Exception as e:
        print(f"Error parsing body: {e}")
        return {"login": "failed", "reason": "Bad request"}

    username = credentials.get("username")
    password = credentials.get("password")
    user_password = database.get_user_database(username)

    if user_password and user_password == password:
        print(f"[SampleApp] Login successful for '{username}'")
        session_id = "".join(random.choices(string.ascii_letters + string.digits, k=32))
        database.create_session(session_id, username)
        return {"login": "success", "session_id": session_id}

    else:
        print("[SampleApp] Login failed")
        return {"login": "failed", "reason": "Invalid credentials"}


@app.route("/register", methods=["POST"])
def register_peer(headers, body):
    try:
        username = get_user_from_session(headers)
        if not username:
            return {"status": "failed", "reason": "unauthorized"}

        data = json.loads(body)
        # ip = data.get("ip")
        conn_addr = headers.get("_conn_addr")
        ip = conn_addr[0]
        print(type(ip))
        port = int(data.get("port"))

        if not (username and ip and port):
            return {"status": "failed", "reason": "unauthorized"}

        database.register_peer(username, ip, port)
        database.join_channel(username, "global")
        print(f"[SampleApp] Registered peer: {username} at {ip}:{port}")
        return {"status": "registered", "peer": username}
    except Exception as e:
        print(f"[SampleApp] Peer registration failed: {e}")
        return {"status": "failed", "reason": str(e)}


@app.route("/get-peers", methods=["GET"])
def get_peers(headers, body):
    print("[SampleApp] Request for peer list")
    return database.get_peers()


@app.route("/channels/create", methods=["POST"])
def create_channel(headers, body):
    username = get_user_from_session(headers)
    if not username:
        return {"status": "failed", "reason": "unauthorized"}
    if not check_registered_status(username):
        return {"status": "failed", "reason": "haven't register to the system"}
    try:
        data = json.loads(body)
        channel_name = data.get("channel_name")
        if not channel_name:
            return {"status": "failed", "reason": "channel_name required"}
        if channel_name in database.get_channels():
            return {"status": "failed", "reason": "Channel already exists"}
        database.quit_channel(username)
        database.register_channel(username, channel_name)
        database.join_channel(username, channel_name)
        print(f"[SampleApp] User {username} created channel: {channel_name}")
        return {"status": "created", "channel": channel_name}
    except Exception as e:
        return {"status": "failed", "reason": str(e)}


@app.route("/channels/join", methods=["POST"])
def join_channel(headers, body):
    username = get_user_from_session(headers)
    if not username:
        return {"status": "failed", "reason": "unauthorized"}
    if not check_registered_status(username):
        return {"status": "failed", "reason": "haven't register to the system"}
    try:
        data = json.loads(body)
        channel_name = data.get("channel_name")
        if not channel_name:
            return {"status": "failed", "reason": "channel_name required"}
        if channel_name not in database.get_channels():
            return {"status": "failed", "reason": "Channel does not exist"}

        database.quit_channel(username)
        database.join_channel(username, channel_name)
        print(f"[SampleApp] User {username} joined channel: {channel_name}")
        return {"status": "joined", "channel": channel_name}
    except Exception as e:
        return {"status": "failed", "reason": str(e)}


@app.route("/channels/quit", methods=["GET"])
def quit_channel(headers, body):
    username = get_user_from_session(headers)
    if not username:
        return {"status": "failed", "reason": "unauthorized"}
    if not check_registered_status(username):
        return {"status": "failed", "reason": "haven't register to the system"}

    try:
        database.quit_channel(username)
        print(f"[SampleApp] User {username} left, joined global")
        database.join_channel(username, "global")
        return {"status": "quited", "channel": "global"}
    except Exception as e:
        return {"status": "failed", "reason": str(e)}


@app.route("/channels/peers", methods=["POST"])
def get_channel_peers(headers, body):
    username = get_user_from_session(headers)
    if not username:
        return {"status": "failed", "reason": "unauthorized"}
    if not check_registered_status(username):
        return {"status": "failed", "reason": "haven't register to the system"}
    try:
        data = json.loads(body)
        channel_name = data.get("channel_name")
        peers_in_channel = {}
        if channel_name not in database.get_channels():
            return {"status": "failed", "reason": "channel not found"}
        username_in_channel = database.get_channel(channel_name)
        peers = database.get_peers()
        for user in username_in_channel:
            peers_in_channel[user["username"]] = peers.get(user["username"])

        return peers_in_channel
    except Exception as e:
        return {"status": "failed", "reason": str(e)}


@app.route("/me", methods=["GET"])
def get_my_status(headers, body):
    username = get_user_from_session(headers)
    if not username:
        return {"status": "unauthorized"}

    is_registered = check_registered_status(username)
    current_channel = None

    if is_registered:
        all_channels = database.get_channels()
        for channel_name, users in all_channels.items():
            for user in users:
                if user["username"] == username:
                    current_channel = channel_name
                    break
            if current_channel:
                break

    return {
        "status": "ok",
        "username": username,
        "is_registered": is_registered,
        "current_channel": current_channel,
    }


@app.route("/channels/list", methods=["GET"])
def get_channel_list(headers, body):
    username = get_user_from_session(headers)
    if not username:
        return {"status": "failed", "reason": "unauthorized"}
    try:
        channel_names = list(database.get_channels().keys())
        return {"status": "ok", "channels": channel_names}
    except Exception as e:
        return {"status": "failed", "reason": str(e)}


@app.route("/hello", methods=["PUT"])
def hello(headers, body):
    """
    Handle greeting via PUT request.

    This route prints a greeting message to the console using the provided headers
    and body.

    :param headers (str): The request headers or user identifier.
    :param body (str): The request body or message payload.
    """
    print("[SampleApp] ['PUT'] Hello in {} to {}".format(headers, body))


if __name__ == "__main__":
    # Parse command-line arguments to configure server IP and port
    parser = argparse.ArgumentParser(
        prog="Backend", description="", epilog="Beckend daemon"
    )
    parser.add_argument("--server-ip", default="0.0.0.0")
    parser.add_argument("--server-port", type=int, default=PORT)

    args = parser.parse_args()
    ip = args.server_ip
    port = args.server_port

    # Prepare and launch the RESTful application
    app.prepare_address(ip, port)
    app.run()

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

import json
import socket
import argparse
import urllib.parse
import random
import string

from daemon.weaprous import WeApRous

PORT = 8000  # Default port

app = WeApRous()

# Cái DB nèe
session_store = {}

user_database = {"baodang": "123", "nguyenbao": "456", "tienbach": "789"}


@app.route("/login", methods=["POST"])
def login(headers, body, authenticated_user=None):
    print(f"[SampleApp] Raw login body: {body}")

    credentials = {}
    try:
        # Phân tích chuỗi query (ví dụ: "username=admin&password=password")
        parsed_body = urllib.parse.parse_qs(body)
        credentials["username"] = parsed_body.get("username", [""])[0]
        credentials["password"] = parsed_body.get("password", [""])[0]
    except Exception as e:
        print(f"Error parsing body: {e}")
        return {"login": "failed", "reason": "Bad request"}

    username = credentials.get("username")
    password = credentials.get("password")
    # Kiểm tra credentials
    if username in user_database and user_database[username] == password:
        print(f"[SampleApp] Login successful for '{username}'")
        # Tạo 1 cookie/session_id ngẫu nhiên
        session_id = "".join(random.choices(string.ascii_letters + string.digits, k=32))
        session_store[session_id] = username
        return {"login": "success", "session_id": session_id}

    else:
        print("[SampleApp] Login failed")
        return {"login": "failed", "reason": "Invalid credentials"}


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
    app.run(session_store=session_store)

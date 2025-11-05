#
# Copyright (C) 2025 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# WeApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#

"""
daemon.httpadapter
~~~~~~~~~~~~~~~~~

This module provides a http adapter object to manage and persist 
http settings (headers, bodies). The adapter supports both
raw URL paths and RESTful route definitions, and integrates with
Request and Response objects to handle client-server communication.
"""
import json
from .request import Request
from .response import Response
from .dictionary import CaseInsensitiveDict

class HttpAdapter:
    """
    A mutable :class:`HTTP adapter <HTTP adapter>` for managing client connections
    and routing requests.

    The `HttpAdapter` class encapsulates the logic for receiving HTTP requests,
    dispatching them to appropriate route handlers, and constructing responses.
    It supports RESTful routing via hooks and integrates with :class:`Request <Request>` 
    and :class:`Response <Response>` objects for full request lifecycle management.

    Attributes:
        ip (str): IP address of the client.
        port (int): Port number of the client.
        conn (socket): Active socket connection.
        connaddr (tuple): Address of the connected client.
        routes (dict): Mapping of route paths to handler functions.
        request (Request): Request object for parsing incoming data.
        response (Response): Response object for building and sending replies.
    """

    __attrs__ = [
        "ip",
        "port",
        "conn",
        "connaddr",
        "routes",
        "request",
        "response",
    ]

    def __init__(self, ip, port, conn, connaddr, routes, session_store):
        """
        Initialize a new HttpAdapter instance.

        :param ip (str): IP address of the client.
        :param port (int): Port number of the client.
        :param conn (socket): Active socket connection.
        :param connaddr (tuple): Address of the connected client.
        :param routes (dict): Mapping of route paths to handler functions.
        """

        #: IP address.
        self.ip = ip
        #: Port.
        self.port = port
        #: Connection
        self.conn = conn
        #: Conndection address
        self.connaddr = connaddr
        #: Routes
        self.routes = routes
        #: Request
        self.request = Request()
        #: Response
        self.response = Response()
        self.session_store = session_store
    def handle_client(self, conn, addr, routes, session_store):
        """
        Handle an incoming client connection.

        This method reads the request from the socket, prepares the request object,
        invokes the appropriate route handler if available, builds the response,
        and sends it back to the client.

        :param conn (socket): The client socket connection.
        :param addr (tuple): The client's address.
        :param routes (dict): The route mapping for dispatching requests.
        """

        # Connection handler.
        self.conn = conn        
        # Connection address.
        self.connaddr = addr
        # Request handler
        req = self.request
        # Response handler
        resp = self.response

        # Handle the request
        msg = conn.recv(1024).decode()
        if not msg:
            print("[HttpAdapter] Received an empty request. Closing connection.")
            conn.close()
            return
        #req.prepare(msg, routes)
        # --- TÁCH HEADER VÀ BODY ---
        header_text = msg
        body_text = ""
        if '\r\n\r\n' in msg:
            parts = msg.split('\r\n\r\n', 1)
            header_text = parts[0]
            if len(parts) > 1:
                body_text = parts[1]
        
        req.prepare(header_text, routes) # Chỉ parse header
        req.body = body_text # Gán body thủ công

        session_id_from_cookie = req.cookies.get('session_id')

        username = None
        if session_id_from_cookie:
            username = self.session_store.get(session_id_from_cookie)
        is_authenticated = bool(username)
        req.authenticated_user = username
        allowed_paths = ['/login.html', '/login']

        if not is_authenticated and req.path not in allowed_paths:
            print(f"[HttpAdapter] Access denied for {req.path}. No auth cookie.")
            # Trả về lỗi 401 Unauthorized
            resp.status_code = 401
            resp.reason = "Unauthorized"
            resp.headers['Content-Type'] = 'text/html'
            resp._content = b'<h1>401 Unauthorized</h1><p>You must log in to access this page.</p><a href="/login.html">Login</a>'

            response = resp.build_response_header(req) + resp._content

            conn.sendall(response)
            conn.close()
            return
        response = b"" # Khởi tạo response
        # Handle request hook
        if req.hook:
            # 1. Gọi hàm hook (ví dụ: login, get-list)
            # Truyền user đã được xác thực vào hook
            app_response_data = req.hook(
                headers=req.headers, 
                body=req.body, 
                authenticated_user=req.authenticated_user
            )
            
            # 2. Xử lý logic đặc biệt CHỈ DÀNH CHO /login ("Quầy vé")
            if req.path == '/login':
                if app_response_data.get("login") == "success":
                    # ĐĂNG NHẬP THÀNH CÔNG
                    session_id = app_response_data.get("session_id")
                    resp.status_code = 200
                    resp.reason = "OK"
                    resp.headers['Set-Cookie'] = f'session_id={session_id}; Path=/; HttpOnly'
                    resp.headers['Content-Type'] = 'application/json'
                    resp._content = b'{"status": "Login successful, cookie set"}'
                else:
                    # ĐĂNG NHẬP THẤT BẠI
                    resp.status_code = 401 
                    resp.reason = "Unauthorized"
                    resp.headers['Content-Type'] = 'application/json'
                    resp._content = b'{"status": "Login failed"}'
            
            else:
                try:
                    response_body_str = json.dumps(app_response_data)
                    resp._content = response_body_str.encode('utf-8')
                    resp.headers['Content-Type'] = 'application/json'
                    resp.status_code = 200
                    resp.reason = "OK"
                except Exception as e:
                    print(f"[HttpAdapter] Error processing hook response: {e}")
                    resp._content = b'{"error": "Internal Server Error"}'
                    resp.headers['Content-Type'] = 'application/json'
                    resp.status_code = 500
                    resp.reason = "Internal Server Error"
            
            response = resp.build_response_header(req) + resp._content

        else:
            # --- KHÔNG PHẢI HOOK (logic phục vụ file tĩnh) ---
            response = resp.build_response(req)

        #print(response)
        conn.sendall(response)
        conn.close()


    @property
    def extract_cookies(self, req, resp):
        """
        Build cookies from the :class:`Request <Request>` headers.

        :param req:(Request) The :class:`Request <Request>` object.
        :param resp: (Response) The res:class:`Response <Response>` object.
        :rtype: cookies - A dictionary of cookie key-value pairs.
        """
        cookies = {}
        for header in headers:
            if header.startswith("Cookie:"):
                cookie_str = header.split(":", 1)[1].strip()
                for pair in cookie_str.split(";"):
                    key, value = pair.strip().split("=")
                    cookies[key] = value
        return cookies

    def build_response(self, req, resp):
        """Builds a :class:`Response <Response>` object 

        :param req: The :class:`Request <Request>` used to generate the response.
        :param resp: The  response object.
        :rtype: Response
        """
        response = Response()

        # Set encoding.
        response.encoding = get_encoding_from_headers(response.headers)
        response.raw = resp
        response.reason = response.raw.reason

        if isinstance(req.url, bytes):
            response.url = req.url.decode("utf-8")
        else:
            response.url = req.url

        # Add new cookies from the server.
        response.cookies = extract_cookies(req)

        # Give the Response some context.
        response.request = req
        response.connection = self

        return response

    # def get_connection(self, url, proxies=None):
        # """Returns a url connection for the given URL. 

        # :param url: The URL to connect to.
        # :param proxies: (optional) A Requests-style dictionary of proxies used on this request.
        # :rtype: int
        # """

        # proxy = select_proxy(url, proxies)

        # if proxy:
            # proxy = prepend_scheme_if_needed(proxy, "http")
            # proxy_url = parse_url(proxy)
            # if not proxy_url.host:
                # raise InvalidProxyURL(
                    # "Please check proxy URL. It is malformed "
                    # "and could be missing the host."
                # )
            # proxy_manager = self.proxy_manager_for(proxy)
            # conn = proxy_manager.connection_from_url(url)
        # else:
            # # Only scheme should be lower case
            # parsed = urlparse(url)
            # url = parsed.geturl()
            # conn = self.poolmanager.connection_from_url(url)

        # return conn


    def add_headers(self, request):
        """
        Add headers to the request.

        This method is intended to be overridden by subclasses to inject
        custom headers. It does nothing by default.

        
        :param request: :class:`Request <Request>` to add headers to.
        """
        pass

    def build_proxy_headers(self, proxy):
        """Returns a dictionary of the headers to add to any request sent
        through a proxy. 

        :class:`HttpAdapter <HttpAdapter>`.

        :param proxy: The url of the proxy being used for this request.
        :rtype: dict
        """
        headers = {}
        #
        # TODO: build your authentication here
        #       username, password =...
        # we provide dummy auth here
        #
        username, password = ("user1", "password")

        if username:
            headers["Proxy-Authorization"] = (username, password)

        return headers
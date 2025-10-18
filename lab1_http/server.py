#!/usr/bin/env python3
import os
import sys
import socket
import mimetypes
import urllib.parse
from datetime import datetime
from html import escape
import time

DELAY_MS = int(os.environ.get("DELAY_MS", "0"))
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))

ALLOWED_EXTS = {".html", ".png", ".pdf"}

def http_date(dt: datetime) -> str:
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")

def build_response(status_code: int, reason: str, headers: dict, body: bytes) -> bytes:
    lines = [f"HTTP/1.1 {status_code} {reason}"]
    base_headers = {
        "Server": "PR-Lab1-PythonSocket/1.1",
        "Date": http_date(datetime.now()),
        "Content-Length": str(len(body)),
        "Connection": "close",
    }
    base_headers.update(headers or {})
    for k, v in base_headers.items():
        lines.append(f"{k}: {v}")
    lines.append("")
    head = ("\r\n".join(lines) + "\r\n").encode("utf-8", "replace")
    return head + body

def safe_join(base: str, path: str) -> str:
    full = os.path.normpath(os.path.join(base, path.lstrip("/")))
    base_abs = os.path.abspath(base)
    full_abs = os.path.abspath(full)
    if os.path.commonpath([full_abs, base_abs]) != base_abs:
        raise PermissionError("Path traversal attempt")
    return full

def rel_href(name: str, is_dir: bool) -> str:
    from urllib.parse import quote
    return quote(name) + ("/" if is_dir else "")

def list_directory(absdir: str, url_path: str) -> bytes:
    items_html = []
    if url_path not in ("/", ""):
        parent = url_path.rstrip("/")
        cut = parent.rfind("/")
        parent = "/" if cut <= 0 else parent[:cut] + "/"
        items_html.append(
            f'<li class="up"><a href="{escape(parent)}">⬆ Parent directory</a></li>'
        )

    for name in sorted(os.listdir(absdir), key=str.lower):
        if name == ".DS_Store" or name == "404.html":
            continue
        p = os.path.join(absdir, name)
        is_dir = os.path.isdir(p)
        disp = name + ("/" if is_dir else "")
        href = rel_href(name, is_dir)
        items_html.append(
            f'<li><a href="{href}">{escape(disp)}</a></li>'
        )

    page = f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width,initial-scale=1"/>
    <title>Index of {escape(url_path)}</title>
    <style>
      :root {{
        --bg: #0b1020;
        --card: #141a2b;
        --text: #e7ecf3;
        --muted: #9fb0c3;
        --accent: #5aa9ff;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
        background: radial-gradient(1200px 600px at 20% -10%, #1b2340 0%, #0b1020 60%);
        color: var(--text);
        min-height: 100vh;
        padding: 2rem;
      }}
      .wrap {{
        max-width: 960px;
        margin: 0 auto;
      }}
      header {{
        margin-bottom: 1rem;
      }}
      h1 {{
        font-size: 1.2rem;
        color: var(--muted);
        font-weight: 600;
        letter-spacing: .3px;
      }}
      .card {{
        background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.01));
        border: 1px solid rgba(255,255,255,.06);
        border-radius: 16px;
        padding: 1rem;
        backdrop-filter: blur(8px);
        box-shadow: 0 10px 30px rgba(0,0,0,.35);
      }}
      ul {{
        list-style: none;
        margin: 0;
        padding: 0;
      }}
      li {{
        display: flex;
        align-items: center;
        padding: .6rem .8rem;
        border-radius: 12px;
        transition: background .15s ease;
        font-size: 1.2rem;
      }}
      li.up {{ color: var(--muted); }}
      li:hover {{ background: rgba(255,255,255,.05); }}
      a {{
        color: var(--accent);
        text-decoration: none;
        font-weight: 600;
        word-break: break-all;
      }}
      .legend {{
        color: var(--muted);
        font-size: .9rem;
        margin: .5rem .3rem 1rem;
      }}
      footer {{
        margin-top: 1rem;
        color: var(--muted);
        font-size: .85rem;
      }}
      code {{
        background: rgba(255,255,255,.08);
        padding: .15rem .35rem;
        border-radius: 6px;
      }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <header>
        <h1>Index of <code>{escape(url_path if url_path else "/")}</code></h1>
        <div class="legend">Click to open files or browse subdirectories.</div>
      </header>
      <section class="card">
        <ul>
          {"".join(items_html) if items_html else '<li><em>(empty)</em></li>'}
        </ul>
      </section>
      <footer>PR Lab 1 – HTTP file server with TCP sockets. Made by Aliosa Pavlovschii. FAF-231</footer>
    </div>
  </body>
</html>"""
    return page.encode("utf-8")

def allowed_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in ALLOWED_EXTS

def content_type_for(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".html":
        return "text/html; charset=utf-8"
    if ext == ".png":
        return "image/png"
    if ext == ".pdf":
        return "application/pdf"
    return mimetypes.guess_type(path)[0] or "application/octet-stream"

def handle_request(conn, base_dir: str):
    data = b""
    conn.settimeout(2.0)
    try:
        while b"\r\n\r\n" not in data and len(data) < 65536:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
    except socket.timeout:
        return

    if not data:
        return

    try:
        header_text = data.split(b"\r\n\r\n", 1)[0].decode("iso-8859-1")
    except UnicodeDecodeError:
        header_text = data.split(b"\r\n\r\n", 1)[0].decode("utf-8", "replace")

    request_line = header_text.split("\r\n")[0]
    parts = request_line.split(" ")
    if len(parts) != 3:
        resp = build_response(400, "Bad Request",
                              {"Content-Type": "text/plain; charset=utf-8"},
                              b"Bad Request")
        conn.sendall(resp)
        return

    method, target, _ = parts
    if method != "GET":
        resp = build_response(405, "Method Not Allowed",
                              {"Content-Type": "text/plain; charset=utf-8"},
                              b"Only GET is supported")
        conn.sendall(resp)
        return

    path = urllib.parse.urlparse(target).path
    path = urllib.parse.unquote(path)

    try:
        abs_path = safe_join(base_dir, "." + path)
    except PermissionError:
        resp = build_response(403, "Forbidden",
                              {"Content-Type": "text/plain; charset=utf-8"},
                              b"Forbidden")
        conn.sendall(resp)
        return

    if DELAY_MS > 0:
        time.sleep(DELAY_MS / 1000.0)

    if os.path.isdir(abs_path):
        body = list_directory(abs_path, path if path.endswith("/") else path + "/")
        resp = build_response(200, "OK",
                              {"Content-Type": "text/html; charset=utf-8"},
                              body)
        conn.sendall(resp)
        return

    if not os.path.exists(abs_path) or not allowed_file(abs_path):
        error_path = os.path.join(base_dir, "404.html")
        with open(error_path, "rb") as f:
            body = f.read()
        resp = build_response(404, "Not Found",
                              {"Content-Type": "text/html; charset=utf-8"},
                              body)
        conn.sendall(resp)
        return

    try:
        with open(abs_path, "rb") as f:
            body = f.read()
    except OSError:
        resp = build_response(500, "Internal Server Error",
                              {"Content-Type": "text/plain; charset=utf-8"},
                              b"Failed to read file")
        conn.sendall(resp)
        return

    ctype = content_type_for(abs_path)
    resp = build_response(200, "OK", {"Content-Type": ctype}, body)
    conn.sendall(resp)

def main():
    if len(sys.argv) != 2:
        print("Usage: python server.py <directory_to_serve>", file=sys.stderr)
        sys.exit(2)

    base_dir = os.path.abspath(sys.argv[1])
    if not os.path.isdir(base_dir):
        print(f"Error: '{base_dir}' is not a directory", file=sys.stderr)
        sys.exit(2)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(5)
        print(f"Serving {base_dir} on http://{HOST}:{PORT} ...")
        while True:
            conn, addr = s.accept()
            with conn:
                handle_request(conn, base_dir)

if __name__ == "__main__":
    main()
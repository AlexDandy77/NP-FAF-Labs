#!/usr/bin/env python3
import os
import sys
import socket
import threading
import time
import urllib.parse
from html import escape
from collections import defaultdict, deque

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from lab1_http.server import build_response, safe_join, allowed_file, content_type_for

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))

DELAY_MS = int(os.environ.get("DELAY_MS", "0"))
USE_LOCK = int(os.environ.get("USE_LOCK", "1")) == 1     # 0 = naive (racey), 1 = fixed
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "5"))      # ~5 req/sec per client IP
WINDOW_SEC = float(os.environ.get("WINDOW_SEC", "1.0"))  # sliding window in seconds

class ServerState:
    def __init__(self):
        self.hits = defaultdict(int)
        self.ip_buckets = defaultdict(deque)
        self.lock = threading.Lock()

STATE = ServerState()

def parent_href(url_path: str) -> str:
    if url_path in ("/", ""):
        return ""
    parent = url_path.rstrip("/")
    cut = parent.rfind("/")
    return "/" if cut <= 0 else parent[:cut] + "/"

def inc_hit(url_path: str):
    if USE_LOCK:
        with STATE.lock:
            STATE.hits[url_path] += 1
    else:
        cur = STATE.hits[url_path]
        time.sleep(0.005) # add tiny sleeps to force interlacing
        STATE.hits[url_path] = cur + 1

def snapshot_hits():
    if USE_LOCK:
        with STATE.lock:
            return dict(STATE.hits)
    return dict(STATE.hits)

def rate_limited(ip: str) -> bool:
    if RATE_LIMIT <= 0:
        return False
    now = time.monotonic()
    window_start = now - WINDOW_SEC
    if USE_LOCK:
        with STATE.lock:
            dq = STATE.ip_buckets[ip]
            while dq and dq[0] < window_start:
                dq.popleft()
            if len(dq) >= RATE_LIMIT:
                return True
            dq.append(now)
            return False
    else:
        dq = STATE.ip_buckets[ip]
        while dq and dq[0] < window_start:
            dq.popleft()
        if len(dq) >= RATE_LIMIT:
            return True
        dq.append(now)
        return False

def render_listing(absdir: str, url_norm: str) -> bytes:
    parent = ""
    if url_norm not in ("/", ""):
        parent_trim = url_norm.rstrip("/")
        cut = parent_trim.rfind("/")
        parent = "/" if cut <= 0 else parent_trim[:cut] + "/"

    try:
        hits_map = snapshot_hits()
    except NameError:
        hits_map = {}

    rows = []
    if parent:
        rows.append(
            f"<tr>"
            f"<td><a href=\"{escape(parent)}\">⬆ Parent directory</a></td>"
            f"<td class='num'>–</td>"
            f"</tr>"
        )

    for name in sorted(os.listdir(absdir), key=str.lower):
        if name in (".DS_Store", "404.html"):
            continue

        p = os.path.join(absdir, name)
        is_dir = os.path.isdir(p)
        disp = name + ("/" if is_dir else "")
        href = urllib.parse.quote(name) + ("/" if is_dir else "")

        if url_norm != "/":
            hit_key = url_norm.rstrip("/") + "/" + name + ("/" if is_dir else "")
        else:
            hit_key = "/" + name + ("/" if is_dir else "")

        h = hits_map.get(hit_key, 0)

        rows.append(
            f"<tr>"
            f"<td><a href=\"{href}\">{escape(disp)}</a></td>"
            f"<td class='num'>{h}</td>"
            f"</tr>"
        )

    page = f"""<!doctype html>
    <html>
      <head>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width,initial-scale=1"/>
        <title>Index of {escape(url_norm)}</title>
        <style>
          :root {{
            --bg: #0b1020;
            --card: #141a2b;
            --text: #e7ecf3;
            --muted: #9fb0c3;
            --accent: #5aa9ff;
            --border: rgba(255,255,255,.08);
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
          .wrap {{ max-width: 960px; margin: 0 auto; }}
          header {{ margin-bottom: 1rem; }}
          h1 {{
            font-size: 1.2rem;
            color: var(--muted);
            font-weight: 600;
            letter-spacing: .3px;
            margin: 0 0 .5rem 0;
          }}
          .legend {{
            color: var(--muted);
            font-size: .9rem;
            margin-bottom: 1rem;
          }}
          .card {{
            background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.01));
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1rem;
            backdrop-filter: blur(8px);
            box-shadow: 0 10px 30px rgba(0,0,0,.35);
          }}
          table {{ width: 100%; border-collapse: collapse; }}
          th, td {{
            padding: .75rem .9rem;
            border-bottom: 1px solid var(--border);
          }}
          thead th {{
            text-align: left;
            color: var(--muted);
            font-weight: 700;
            font-size: .95rem;
          }}
          td.num, th.num {{ text-align: right; width: 140px; }}
          a {{
            color: var(--accent);
            text-decoration: none;
            font-weight: 600;
            word-break: break-all;
          }}
          tr:hover td {{ background: rgba(255,255,255,.04); }}
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
            <h1>Index of <code>{escape(url_norm if url_norm else "/")}</code></h1>
            <div class="legend">Click to open files or browse subdirectories.</div>
          </header>
          <section class="card">
            <table>
              <thead>
                <tr><th>File / Directory</th><th class="num">Hits</th></tr>
              </thead>
              <tbody>
                {''.join(rows) if rows else '<tr><td>(empty)</td><td class="num">0</td></tr>'}
              </tbody>
            </table>
          </section>
          <footer>PR Lab 2 – Concurrent HTTP file server. Made by Aliosa Pavlovschii. FAF-231</footer>
        </div>
      </body>
    </html>"""
    return page.encode("utf-8")

def handle_request(conn, addr, base_dir: str):
    client_ip = addr[0]
    if rate_limited(client_ip):
        body = b"<!doctype html><html><body><h1>429 Too Many Requests</h1><p>Rate limit 5 req/s per IP.</p></body></html>"
        resp = build_response(429, "Too Many Requests",
                              {"Content-Type":"text/html; charset=utf-8"}, body)
        conn.sendall(resp)
        return

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
        resp = build_response(400, "Bad Request", {"Content-Type":"text/plain; charset=utf-8"}, b"Bad Request")
        conn.sendall(resp)
        return

    method, target, _ = parts
    if method != "GET":
        resp = build_response(405, "Method Not Allowed",
                              {"Content-Type":"text/plain; charset=utf-8"},
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
        url_norm = path if path.endswith("/") else path + "/"
        inc_hit(url_norm)
        body = render_listing(abs_path, url_norm)
        resp = build_response(200, "OK", {"Content-Type":"text/html; charset=utf-8"}, body)
        conn.sendall(resp)
        return

    if not os.path.exists(abs_path) or not allowed_file(abs_path):
        error_path = os.path.join(base_dir, "404.html")
        with open(error_path, "rb") as f:
            body = f.read()
        resp = build_response(404, "Not Found", {"Content-Type":"text/html; charset=utf-8"}, body)
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

    inc_hit(path if path.startswith("/") else "/" + path)
    ctype = content_type_for(abs_path)
    resp = build_response(200, "OK", {"Content-Type": ctype}, body)
    conn.sendall(resp)

def handle_client(conn, addr, base_dir):
    with conn:
        handle_request(conn, addr, base_dir)

def main():
    if len(sys.argv) != 2:
        print("Usage: python server_mt.py <directory_to_serve>", file=sys.stderr)
        sys.exit(2)
    base_dir = os.path.abspath(sys.argv[1])
    if not os.path.isdir(base_dir):
        print(f"Error: '{base_dir}' is not a directory", file=sys.stderr)
        sys.exit(2)

    print(f"[MT] Using {'LOCKED' if USE_LOCK else 'NAIVE'} counters | Delay={DELAY_MS}ms | Rate={RATE_LIMIT}/s per IP")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(128)
        print(f"Serving {base_dir} on http://{HOST}:{PORT} ... (multithreaded)")
        while True:
            conn, addr = s.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr, base_dir), daemon=True)
            t.start()

if __name__ == "__main__":
    main()
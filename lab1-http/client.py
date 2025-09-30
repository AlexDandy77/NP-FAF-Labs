import os
import sys
import socket
from urllib.parse import urlparse

def http_get(url: str) -> bytes:
    u = urlparse(url)
    if u.scheme not in ("http", None, ""):
        raise ValueError("Only http:// URLs are supported")
    host = u.hostname or "127.0.0.1"
    port = u.port or 80
    path = u.path if u.path else "/"
    if u.query:
        path += "?" + u.query

    with socket.create_connection((host, port), timeout=10) as s:
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"Connection: close\r\n"
            f"User-Agent: PR-Lab1-Client/1.0\r\n"
            f"\r\n"
        )
        s.sendall(req.encode("utf-8"))
        data = b""
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
    return data

def split_head_body(resp: bytes):
    head, sep, body = resp.partition(b"\r\n\r\n")
    return head, body

def parse_headers(head: bytes):
    lines = head.decode("iso-8859-1", "replace").split("\r\n")
    status_line = lines[0] if lines else ""
    headers = {}
    for line in lines[1:]:
        if not line.strip():
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return status_line, headers

def infer_extension(ct: str) -> str:
    ct = (ct or "").split(";")[0].strip().lower()
    if ct == "text/html":
        return ".html"
    if ct == "image/png":
        return ".png"
    if ct == "application/pdf":
        return ".pdf"
    return ""

def main():
    if len(sys.argv) != 3:
        print("Usage: python client.py <URL> <download_dir>", file=sys.stderr)
        print("HTML -> print body to stdout")
        print("PNG/PDF -> save into <download_dir>", file=sys.stderr)
        sys.exit(2)

    url = sys.argv[1]
    out_dir = sys.argv[2]

    os.makedirs(out_dir, exist_ok=True)

    resp = http_get(url)
    head, body = split_head_body(resp)
    status_line, headers = parse_headers(head)
    print(status_line)

    ctype = headers.get("content-type", "")
    ext = infer_extension(ctype)

    if ext == ".html":
        try:
            print(body.decode("utf-8"))
        except UnicodeDecodeError:
            print(body.decode("iso-8859-1", "replace"))
    elif ext in (".png", ".pdf"):
        parsed = urlparse(url)
        base = os.path.basename(parsed.path) or ("download" + ext)
        if not base.lower().endswith(ext):
            base += ext
        dest = os.path.join(out_dir, base)
        with open(dest, "wb") as f:
            f.write(body)
        print(f"Saved: {dest}")
    else:
        print("Unknown or unsupported content type; nothing saved.", file=sys.stderr)

if __name__ == "__main__":
    main()
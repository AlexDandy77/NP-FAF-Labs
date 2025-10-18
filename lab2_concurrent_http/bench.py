#!/usr/bin/env python3
import argparse
import os
import sys
import time
import socket
import subprocess
import threading
from http.client import HTTPConnection

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
WWW_DIR = os.path.join(REPO_ROOT, 'lab1_http', 'www')
ST_SERVER = os.path.join(REPO_ROOT, 'lab1_http', 'server.py')
MT_SERVER = os.path.join(REPO_ROOT, 'lab2_concurrent_http', 'server_mt.py')
HOST = os.environ.get('HOST', '127.0.0.1')
PORT = int(os.environ.get('PORT', '8080'))
BASE_URL = f"http://{HOST}:{PORT}"


def http_get(path: str, timeout=100.0) -> int: # adjust timeout
    conn = HTTPConnection(HOST, PORT, timeout=timeout)
    try:
        conn.request('GET', path)
        resp = conn.getresponse()
        status = resp.status
        try:
            resp.read()
        finally:
            conn.close()
        return status
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return -1


def run_concurrent(n: int, path: str) -> float:
    start = time.perf_counter()
    statuses = [None] * n

    def worker(i):
        statuses[i] = http_get(path)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads: t.start()
    for t in threads: t.join()
    end = time.perf_counter()
    return end - start


def wait_port(host: str, port: int, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            try:
                s.connect((host, port))
                return True
            except Exception:
                time.sleep(0.05)
    return False


class ServerProc:
    def __init__(self, script_path: str, base_dir: str, env_overrides=None):
        self.script_path = script_path
        self.base_dir = base_dir
        self.env_overrides = env_overrides or {}
        self.p = None

    def __enter__(self):
        env = os.environ.copy()
        env.update(self.env_overrides)
        # Ensure HOST/PORT are consistent and predictable
        env['HOST'] = HOST
        env['PORT'] = str(PORT)
        self.p = subprocess.Popen([sys.executable, self.script_path, self.base_dir], env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=REPO_ROOT)
        if not wait_port(HOST, PORT, timeout=6.0):
            try:
                out = self.p.stdout.read().decode('utf-8', 'replace')
                print(out)
            except Exception:
                pass
            raise RuntimeError('Server did not start listening on port')
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.p is not None:
            self.p.terminate()
            try:
                self.p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.p.kill()
        self.p = None


# -------------- HTML parsing helper for listing --------------

def parse_listing_hits(html: str, entry_name: str) -> int:
    # Very simple parsing: find anchor for entry_name and read the number in the following <td class='num'>X</td>
    # We look for href="{entry_name}" or href="{entry_name}/" as produced by server_mt.py
    variants = [f'"{entry_name}"', f'"{entry_name}/"']
    idx = -1
    for v in variants:
        idx = html.find(f'<a href={v}>')
        if idx != -1:
            break
    if idx == -1:
        return -1
    # Find next td with class='num'
    td_start = html.find("<td class='num'>", idx)
    if td_start == -1:
        td_start = html.find('class="num"', idx)
        if td_start != -1:
            td_start = html.find('>', td_start) + 1
    else:
        td_start += len("<td class='num'>")
    if td_start == -1:
        return -1
    td_end = html.find('</td>', td_start)
    if td_end == -1:
        return -1
    num_str = html[td_start:td_end].strip()
    try:
        return int(num_str)
    except ValueError:
        return -1


def get_listing_html(path: str = '/') -> str:
    conn = HTTPConnection(HOST, PORT, timeout=5.0)
    conn.request('GET', path)
    resp = conn.getresponse()
    body = resp.read().decode('utf-8', 'replace')
    conn.close()
    return body


def bench_concurrency(delay_ms=100, n=10):
    print(f"== Concurrency test: {n} concurrent GETs with ~{delay_ms}ms handler delay ==")
    # Multithreaded
    with ServerProc(MT_SERVER, WWW_DIR, env_overrides={'DELAY_MS': str(delay_ms) }):
        dt_mt = run_concurrent(n, '/')
        print(f"MT server handled {n} concurrent requests in {dt_mt:.4f}s")
    # Single-threaded
    with ServerProc(ST_SERVER, WWW_DIR, env_overrides={'HOST': HOST, 'PORT': str(PORT), 'DELAY_MS': str(delay_ms) }):
        dt_st = run_concurrent(n, '/')
        print(f"ST server handled {n} concurrent requests in {dt_st:.4f}s")
    print("Note: MT should be ~delay (≈1s), ST should be ≈ n * delay (≈10s) for n=10.")


def bench_counter_race(target='/', requests=200, delay_ms=0):
    print(f"== Counter race test on {target} with {requests} concurrent requests ==")
    target = target if target.startswith('/') else '/' + target

    if target.endswith('/'): # Directory
        entry_name = target.strip('/').split('/')[-1]
        parent = target.rstrip('/')  # '/books'
        parent = parent.rsplit('/', 1)[0]
        dir_path = '/' if parent == '' else parent + '/'
    else: # File
        dir_path = target.rsplit('/', 1)[0] or '/'
        if not dir_path.endswith('/'):
            dir_path += '/'
        entry_name = target.strip('/').split('/')[-1]

    # Naive (racey)
    with ServerProc(MT_SERVER, WWW_DIR, env_overrides={'USE_LOCK': '0', 'DELAY_MS': str(delay_ms), 'RATE_LIMIT': '0'}):
        dt = run_concurrent(requests, target)
        html = get_listing_html(dir_path)
        hits_naive = parse_listing_hits(html, entry_name)
        print(f"Naive (no lock) time {dt:.3f}s, counted hits={hits_naive} (expected {requests})")
    # Locked (correct)
    with ServerProc(MT_SERVER, WWW_DIR, env_overrides={'USE_LOCK': '1', 'DELAY_MS': str(delay_ms), 'RATE_LIMIT': '0'}):
        dt = run_concurrent(requests, target)
        html = get_listing_html(dir_path)
        hits_locked = parse_listing_hits(html, entry_name)
        print(f"Locked (with lock) time {dt:.3f}s, counted hits={hits_locked} (expected {requests})")


def bench_rate_limit(duration=10.0, rate_limit=5):
    print(f"== Rate limiting test for {duration:.1f}s with per-IP limit ≈ {rate_limit}/s ==")
    stop = threading.Event()

    def spammer():
        ok = 0
        blocked = 0
        while not stop.is_set():
            st = http_get('/')
            if st == 200:
                ok += 1
            elif st == 429:
                blocked += 1
            time.sleep(0.01)  # ~100 rps attempt
        return ok, blocked

    def polite():
        ok = 0
        blocked = 0
        interval = 0.25  # 4 rps
        next_t = time.perf_counter()
        while not stop.is_set():
            now = time.perf_counter()
            if now < next_t:
                time.sleep(min(0.01, next_t - now))
                continue
            st = http_get('/')
            if st == 200:
                ok += 1
            elif st == 429:
                blocked += 1
            next_t += interval
        return ok, blocked

    with ServerProc(MT_SERVER, WWW_DIR, env_overrides={'RATE_LIMIT': str(rate_limit), 'WINDOW_SEC': '1.0'}):
        res_spam = {}
        res_pol = {}
        def spam_runner():
            ok, blk = spammer()
            res_spam['ok'] = ok
            res_spam['blk'] = blk
        def pol_runner():
            ok, blk = polite()
            res_pol['ok'] = ok
            res_pol['blk'] = blk
        t1 = threading.Thread(target=spam_runner)
        t2 = threading.Thread(target=pol_runner)
        t1.start(); t2.start()
        time.sleep(duration)
        stop.set()
        t1.join(); t2.join()
        spam_ok, spam_block = res_spam.get('ok',0), res_spam.get('blk',0)
        pol_ok, pol_block = res_pol.get('ok',0), res_pol.get('blk',0)
        print(f"Spammer: {spam_ok} OK, {spam_block} blocked (avg {spam_ok/duration:.1f} OK/s)")
        print(f"Polite:  {pol_ok} OK, {pol_block} blocked (avg {pol_ok/duration:.1f} OK/s)")
        print("Expectation: Spammer gets mostly 429; Polite stays under limit and should see near-zero 429s.")


def main():
    ap = argparse.ArgumentParser(description='Lab2 Benchmark and Demo for concurrent HTTP server')
    sub = ap.add_subparsers(dest='cmd')

    ap_conc = sub.add_parser('concurrency', help='Compare MT vs ST with artificial delay')
    ap_conc.add_argument('-n', '--num', type=int, default=10, help='Concurrent requests (default 10)')
    ap_conc.add_argument('--delay-ms', type=int, default=100, help='Artificial per-request delay in ms (default 100)')

    ap_counter = sub.add_parser('counter', help='Show counter race (naive) vs fixed (lock)')
    ap_counter.add_argument('--path', default='/books/', help='File path to target (default /books/)')
    ap_counter.add_argument('-n', '--num', type=int, default=200, help='Concurrent requests to send (default 200)')

    ap_rate = sub.add_parser('ratelimit', help='Demonstrate per-IP rate limiting')
    ap_rate.add_argument('-d', '--duration', type=float, default=10.0, help='Test duration seconds (default 10.0)')
    ap_rate.add_argument('--limit', type=int, default=5, help='Rate limit per second (default 5)')

    args = ap.parse_args()
    if args.cmd == 'concurrency':
        bench_concurrency(delay_ms=args.delay_ms, n=args.num)
    elif args.cmd == 'counter':
        bench_counter_race(target=args.path, requests=args.num)
    elif args.cmd == 'ratelimit':
        bench_rate_limit(duration=args.duration, rate_limit=args.limit)
    else:
        ap.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()

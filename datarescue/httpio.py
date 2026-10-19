"""Bounded HTTP exchange. DNS resolution remains a system-resolver prerequisite."""

import http.client
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit

from .dataset import Error


class DeadlineHTTP(http.client.HTTPConnection):
    def __init__(self, host, port, timeout, *, tls=False, ip=None):
        super().__init__(host, port, timeout=timeout)
        self.tls, self.ip = tls, ip
        self.deadline = None
        self.active_socket = None

    def connect(self):
        address = self.ip or self.host
        # Explicitly resolve before the I/O deadline; libc DNS is not interruptible
        # portably. A source address is already validated/pinned by network.py.
        records = socket.getaddrinfo(address, self.port, type=socket.SOCK_STREAM)
        if not records:
            raise OSError("No endpoint address")
        records.sort(key=lambda r: r[0] != socket.AF_INET)
        self.deadline = time.monotonic() + self.timeout
        family, socktype, proto, _, target = records[0]
        sock = socket.socket(family, socktype, proto)
        self.active_socket = sock
        try:
            sock.settimeout(self.timeout)
            sock.connect(target)
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError()
            sock.settimeout(remaining)
            if self.tls:
                sock = ssl.create_default_context().wrap_socket(
                    sock, server_hostname=self.host, do_handshake_on_connect=False
                )
                self.active_socket = sock
                sock.do_handshake()
            self.sock = sock
        except Exception:
            sock.close()
            raise

    def abort(self):
        sock = self.active_socket
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()


def read_exchange(conn, method, path, headers, *, body=None, timeout=20, max_bytes=524_288):
    timer = None
    expired = threading.Event()
    try:
        conn.connect()
        active_socket = conn.sock
        deadline = getattr(conn, "deadline", None)
        if not isinstance(deadline, (int, float)):
            deadline = time.monotonic() + timeout
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise Error("HTTP time budget exhausted")

        def abort():
            expired.set()
            try:
                active_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            active_socket.close()

        timer = threading.Timer(remaining, abort)
        timer.daemon = True
        timer.start()
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        result_headers = {k.lower(): v for k, v in response.getheaders()}
        chunks, size = [], 0
        while True:
            if expired.is_set() or time.monotonic() >= deadline:
                raise Error("HTTP time budget exhausted")
            chunk = response.read1(min(65536, max_bytes + 1 - size))
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                raise Error("HTTP response exceeds byte budget")
            chunks.append(chunk)
        if expired.is_set():
            raise Error("HTTP time budget exhausted")
        return response.status, result_headers, b"".join(chunks)
    except (OSError, http.client.HTTPException, ValueError):
        raise Error("HTTP connection failed or timed out") from None
    finally:
        if timer:
            timer.cancel()
        conn.close()


def request_bytes(url, *, body=None, headers=None, timeout=20, max_bytes=128_000):
    u = urlsplit(url)
    tls = u.scheme == "https"
    conn = DeadlineHTTP(u.hostname, u.port or (443 if tls else 80), timeout, tls=tls)
    return read_exchange(
        conn,
        "POST" if body is not None else "GET",
        (u.path or "/") + ("?" + u.query if u.query else ""),
        headers or {},
        body=body,
        timeout=timeout,
        max_bytes=max_bytes,
    )

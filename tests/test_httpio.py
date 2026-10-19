import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from datarescue.dataset import Error
from datarescue.httpio import request_bytes


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(302 if self.path == "/redirect" else 200)
        self.send_header("Location", "/not-followed")
        self.end_headers()
        try:
            if self.path == "/slow":
                for _ in range(30):
                    self.wfile.write(b"x")
                    self.wfile.flush()
                    time.sleep(0.025)
            else:
                self.wfile.write(b"hello")
        except (OSError, ConnectionError):
            pass


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_actual_http_and_redirect_not_followed(self):
        self.assertEqual(request_bytes(self.url)[2], b"hello")
        self.assertEqual(request_bytes(self.url + "/redirect")[0], 302)

    def test_actual_response_size_limit(self):
        with self.assertRaises(Error):
            request_bytes(self.url, max_bytes=3)

    def test_slow_drip_has_absolute_io_deadline(self):
        started = time.monotonic()
        with self.assertRaises(Error):
            request_bytes(self.url + "/slow", timeout=0.12)
        self.assertLess(time.monotonic() - started, 0.6)

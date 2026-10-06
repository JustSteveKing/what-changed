import json
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


@dataclass
class SseScript:
    events: list[dict[str, Any]] = field(default_factory=list)
    delay_s: float = 0.0
    # Leave the connection open after the last event, as a stuck stream would.
    hang: bool = False
    # Respond with this HTTP status and a JSON error instead of a stream.
    status: int | None = None


# A local stand-in for POST /research that replays scripted SSE events.
class SseServer:
    def __init__(self, script: SseScript) -> None:
        self.script = script
        self.requests = 0
        self.requested = threading.Event()
        self._stop = threading.Event()
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                pass

            def do_POST(self) -> None:
                server.requests += 1
                server.requested.set()
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                if server.script.status is not None:
                    body = json.dumps({"error": "scripted failure"}).encode()
                    self.send_response(server.script.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                try:
                    for event in server.script.events:
                        time.sleep(server.script.delay_s)
                        self.wfile.write(f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n".encode())
                        self.wfile.flush()
                    while server.script.hang and not server._stop.is_set():
                        time.sleep(0.02)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                self.close_connection = True

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        self.base_url = f"http://127.0.0.1:{self._httpd.server_address[1]}"
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def __enter__(self) -> "SseServer":
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._httpd.shutdown()
        self._httpd.server_close()

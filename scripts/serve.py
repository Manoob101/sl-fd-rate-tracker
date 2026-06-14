#!/usr/bin/env python3
"""Serve the dashboard locally so fetch() of the JSON works.

    python3 scripts/serve.py        # -> http://localhost:8799 (or next free port)

Opening site/index.html directly as a file:// also works (it falls back to the
data/rates.js shim), but serving is closest to the deployed setup.
"""
import http.server, os, socketserver, webbrowser

PREFERRED = int(os.environ.get("PORT", "8799"))
ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def serve():
    # Try the preferred port; if it's taken, walk up until we find a free one.
    for port in range(PREFERRED, PREFERRED + 20):
        try:
            return socketserver.TCPServer(("", port), Handler), port
        except OSError:
            continue
    raise SystemExit("No free port found in range.")


if __name__ == "__main__":
    os.chdir(ROOT)
    httpd, port = serve()
    url = f"http://localhost:{port}/"
    print(f"Serving {ROOT}\n  {url}\nCtrl-C to stop.")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    with httpd:
        httpd.serve_forever()

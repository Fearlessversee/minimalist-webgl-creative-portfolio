import http.server
import os
import urllib.parse
import mimetypes
import functools
import re
import sys

PORT = 5179
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("image/png", ".png")
mimetypes.add_type("image/jpeg", ".jpg")
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/ttf", ".ttf")
mimetypes.add_type("audio/mpeg", ".mp3")
mimetypes.add_type("audio/wav", ".wav")
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("video/webm", ".webm")
mimetypes.add_type("video/mp4", ".mp4")
mimetypes.add_type("application/wasm", ".wasm")

class UniversalMinimalistHandler(http.server.SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Range")
        self.send_header("Access-Control-Expose-Headers", "Content-Range, Accept-Ranges, Content-Length")
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_POST(self):
        # Handle newsletter subscriptions or contact submissions
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"success": true, "message": "Successfully recorded."}')

    def do_HEAD(self):
        parsed = urllib.parse.urlparse(self.path)
        clean_path = parsed.path.rstrip('/')
        if clean_path in ('/meta.json', '/.well-known/appspecific/com.chrome.devtools.json'):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", "2")
            self.end_headers()
            return
        super().do_HEAD()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        clean_path = parsed.path.rstrip('/')

        # 1. DevTools & Meta Probes
        if clean_path in ('/meta.json', '/.well-known/appspecific/com.chrome.devtools.json'):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")
            return

        # 2. Resolve path
        rel_path = parsed.path.lstrip('/')
        if not rel_path:
            rel_path = "index.html"

        file_path = os.path.join(DIRECTORY, rel_path.replace('/', os.sep))

        # Check directory index
        if os.path.isdir(file_path):
            file_path = os.path.join(file_path, "index.html")
        elif not os.path.exists(file_path):
            # Check without trailing slash: e.g. /full -> full/index.html
            alt_path = os.path.join(DIRECTORY, rel_path.replace('/', os.sep), "index.html")
            if os.path.exists(alt_path):
                file_path = alt_path

        if not os.path.isfile(file_path):
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h1>404 Not Found</h1>")
            return

        # 3. Content Type & Size
        file_size = os.path.getsize(file_path)
        mime, _ = mimetypes.guess_type(file_path)
        if not mime:
            ext = os.path.splitext(file_path)[1].lower()
            mime = mimetypes.types_map.get(ext, "application/octet-stream")

        # Range request support for media assets
        range_header = self.headers.get("Range")
        if range_header and file_size > 0:
            range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if range_match:
                start = int(range_match.group(1))
                end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
                end = min(end, file_size - 1)
                length = end - start + 1

                self.send_response(206)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Content-Length", str(length))
                self.send_caching_header(clean_path)
                self.end_headers()

                with open(file_path, "rb") as f:
                    f.seek(start)
                    self.copy_range(f, length)
                return

        # Standard 200 GET
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(file_size))
        self.send_caching_header(clean_path)
        self.end_headers()

        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    break

    def send_caching_header(self, path):
        if path.startswith("/_nuxt/"):
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        elif path.endswith((".html", "/")) or not path:
            self.send_header("Cache-Control", "no-cache, must-revalidate")
        else:
            self.send_header("Cache-Control", "public, max-age=86400")

    def copy_range(self, source, length):
        buffer_size = 65536
        bytes_sent = 0
        while bytes_sent < length:
            to_read = min(buffer_size, length - bytes_sent)
            buf = source.read(to_read)
            if not buf:
                break
            try:
                self.wfile.write(buf)
            except (BrokenPipeError, ConnectionResetError):
                break
            bytes_sent += len(buf)

if __name__ == "__main__":
    os.chdir(DIRECTORY)
    handler = functools.partial(UniversalMinimalistHandler, directory=DIRECTORY)
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), handler)
    print("=" * 60)
    print(f" Scandinavian Minimalist WebGL Showcase Live: http://localhost:{PORT}")
    print(f" Directory: {DIRECTORY}")
    print("=" * 60)
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")

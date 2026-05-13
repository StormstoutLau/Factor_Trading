import http.server
import socketserver
import os

PORT = 9000
os.chdir(os.path.dirname(os.path.abspath(__file__)))

handler = http.server.SimpleHTTPRequestHandler

with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
    print(f"Server running at http://127.0.0.1:{PORT}/")
    httpd.serve_forever()

"""Production-grade entry point for testing with real users.

The Flask dev server (app.py run directly) is single-threaded and not meant
for more than one person at a time. This uses waitress, a production WSGI
server, so ~100 concurrent testers won't queue behind each other.
"""
import os

from waitress import serve

from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    threads = int(os.environ.get("THREADS", 8))
    serve(app, host="0.0.0.0", port=port, threads=threads)

"""Production-grade entry point for testing with real users.

The Flask dev server (app.py run directly) is single-threaded and not meant
for more than one person at a time. This uses waitress, a production WSGI
server, so testers won't queue behind each other.

THREADS is deliberately low: file checks are memory-heavy (PyMuPDF page
rendering), and on a small instance (e.g. a 512 MB free tier) too many
concurrent uploads stack up RAM and trigger an out-of-memory crash that takes
the whole app down. 3 threads trades some throughput for staying alive. Raise
it via the THREADS env var once you're on an instance with more memory.
"""
import os

from waitress import serve

from app import app

# Warm the spell-checker dictionary at boot so the FIRST user's check isn't
# slowed by loading it on demand.
try:
    import content_quality
    content_quality._get_spell()
except Exception:
    pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    threads = int(os.environ.get("THREADS", 3))
    serve(app, host="0.0.0.0", port=port, threads=threads)

#!/usr/bin/env python3
"""
Desktop launcher for the packaged Resolva build.

Starts the same Flask app on a local port and opens it in the default
browser, so a non-technical user just double-clicks the .exe. Used only by
the PyInstaller build (resolva.spec); for local dev you can run `python app.py`
directly instead.
"""

import threading
import webbrowser

from app import app, store

PORT = 5000
URL = f"http://127.0.0.1:{PORT}"


def open_browser():
    webbrowser.open(URL)


if __name__ == "__main__":
    store.init_db()
    threading.Timer(1.2, open_browser).start()
    # use_reloader=False is essential in a frozen build.
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)

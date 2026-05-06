"""
keep_alive.py
Flask minimal pour maintenir le bot vivant sur Render.
Render nécessite un serveur HTTP qui écoute sur le port 10000.
"""

import threading
from flask import Flask
from config import FLASK_PORT

app = Flask(__name__)


@app.route("/")
def home():
    return "Bot Discord actif ✅", 200


@app.route("/health")
def health():
    return {"status": "ok"}, 200


def run():
    app.run(host="0.0.0.0", port=FLASK_PORT, use_reloader=False)


def keep_alive():
    """Lance Flask dans un thread séparé pour ne pas bloquer le bot."""
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    print(f"[KeepAlive] Flask démarré sur le port {FLASK_PORT}")

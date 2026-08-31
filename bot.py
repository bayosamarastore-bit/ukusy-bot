import os
import json
import threading
import uuid
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
TOKEN = os.environ.get("TOKEN")

DATA_DIR = "/tmp/ukusy_data"
DATA_FILE = os.path.join(DATA_DIR, "data.json")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")

try:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
except PermissionError:
    UPLOAD_DIR = "/tmp/ukusy_uploads"
    os.makedirs(UPLOAD_DIR, exist_ok=True)

_lock = threading.Lock()


def load_data():
    with _lock:
        if not os.path.exists(DATA_FILE):
            return {"places": [], "comments": {}}
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"places": [], "comments": {}}


def save_data(data):
    with _lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def _encode_photo_as_base64(photo_url):
    """Если photo — локальный uploads URL, загрузить и вернуть data:image/...;base64,..."""
    if not photo_url or not isinstance(photo_url, str):
        return photo_url
    if photo_url.startswith("data:"):
        return photo_url
    if not photo_url.startswith("/uploads/"):
        return photo_url
    fname = photo_url.replace("/uploads/", "")
    path = os.path.join(UPLOAD_DIR, fname)
    if not os.path.exists(path):
        return photo_url
    try:
        import base64
        ext = os.path.splitext(fname)[1].lower().lstrip('.') or 'jpeg'
        if ext == 'jpg': ext = 'jpeg'
        with open(path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('ascii')
        return f"data:image/{ext};base64,{b64}"
    except Exception as e:
        print("base64 encode failed:", e)
        return photo_url


@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


@app.route("/", methods=["GET", "OPTIONS"])
def home():
    return "Ukusy backend is alive!"


@app.route("/appss_verify")
def verify():
    return "appss_98ec27"


@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/api/upload", methods=["POST", "OPTIONS"])
def upload():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "no file"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"ok": False, "error": "empty filename"}), 400
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"):
        return jsonify({"ok": False, "error": "bad ext"}), 400
    name = f"{uuid.uuid4().hex}{ext}"
    f.save(os.path.join(UPLOAD_DIR, name))
    url = f"{request.host_url.rstrip('/')}/uploads/{name}"
    return jsonify({"ok": True, "url": url, "filename": name})


@app.route("/api/places", methods=["GET", "OPTIONS"])
def get_places():
    data = load_data()
    places = data.get("places", [])
    # Встраиваем локальные фото как base64 — обход CSP Telegram WebApp
    for p in places:
        try:
            if p.get("photo"):
                p["photo"] = _encode_photo_as_base64(p["photo"])
            if p.get("photos"):
                p["photos"] = [_encode_photo_as_base64(u) for u in p["photos"]]
        except Exception as e:
            print("encode photo failed:", e)
    return jsonify({"places": places})


@app.route("/api/places", methods=["POST", "OPTIONS"])
def add_place():
    payload = request.get_json() or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    data = load_data()
    new_id = max([p.get("id", 0) for p in data.get("places", [])] + [200]) + 1
    new_place = {
        "id": new_id,
        "name": name[:80],
        "rating": float(payload.get("rating") or 4.5),
        "desc": (payload.get("desc") or "").strip()[:600],
        "tags": payload.get("tags") or [],
        "emoji": payload.get("emoji") or "🍴",
        "likes": 0,
        "comments": 0,
        "address": (payload.get("address") or "").strip()[:200],
        "phone": (payload.get("phone") or "").strip()[:40],
        "hours": (payload.get("hours") or "").strip()[:60],
        "photo": payload.get("photo") or "",
        "photos": payload.get("photos") or [],
        "addedBy": (payload.get("addedBy") or "Guest")[:40],
        "date": payload.get("date") or "",
    }
    data.setdefault("places", []).append(new_place)
    save_data(data)
    return jsonify({"ok": True, "place": new_place})


@app.route("/api/places/<int:place_id>/like", methods=["POST", "OPTIONS"])
def like_place(place_id):
    data = load_data()
    place = next((p for p in data.get("places", []) if p.get("id") == place_id), None)
    if place is None:
        return jsonify({"error": "not found"}), 404
    place["likes"] = place.get("likes", 0) + 1
    idx = next((i for i, p in enumerate(data["places"]) if p.get("id") == place_id), -1)
    if idx >= 0:
        data["places"][idx] = place
    save_data(data)
    return jsonify({"ok": True, "likes": place["likes"]})


@app.route("/api/comments/<int:place_id>", methods=["GET", "OPTIONS"])
def get_comments(place_id):
    data = load_data()
    comments = data.get("comments", {}).get(str(place_id), [])
    return jsonify({"comments": comments})


@app.route("/api/comments/<int:place_id>", methods=["POST", "OPTIONS"])
def add_comment(place_id):
    payload = request.get_json() or {}
    text = (payload.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text required"}), 400
    data = load_data()
    comments = data.setdefault("comments", {}).setdefault(str(place_id), [])
    from datetime import datetime
    today = datetime.utcnow()
    date = f"{today.day}.{today.month}.{today.year}"
    author = (payload.get("author") or "Guest")[:40]
    new_c = {"author": author, "text": text[:600], "date": date}
    comments.append(new_c)
    save_data(data)
    return jsonify({"ok": True, "comment": new_c, "total": len(comments)})


@app.route("/" + (TOKEN or ""), methods=["POST"])
def webhook():
    data = request.get_json()
    if data and "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")
        if text == "/appss_verify":
            requests.get(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                params={"chat_id": chat_id, "text": "appss_98ec27"},
            )
        elif text == "/start":
            requests.get(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                params={
                    "chat_id": chat_id,
                    "text": "Укусы Нячанга — твой гид по вкусной еде Кханьхоа!\n\nНайди лучшие кафе, добавь свои места, читай отзывы.\n\nОткрой приложение через меню → Открыть Гид",
                },
            )
        elif text == "/help":
            requests.get(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                params={
                    "chat_id": chat_id,
                    "text": "Команды:\n/start — начать\n/help — помощь\n/appss_verify — проверка",
                },
            )
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>ukusy-bot.py — копировалка</title>
<style>
body { font-family: ui-monospace, monospace; background: #0e0e10; color: #e0e0e0; margin: 0; padding: 24px; }
h1 { color: #ff7a5c; font-size: 18px; margin: 0 0 16px; }
.wrap { max-width: 880px; margin: 0 auto; }
.bar { display: flex; gap: 12px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
.bar button { background: #ff7a5c; color: #0e0e10; border: 0; padding: 10px 18px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 14px; }
.bar button:hover { background: #ff9b82; }
.bar .status { color: #6a6; font-size: 14px; }
.bar .status.err { color: #d66; }
pre { background: #16161a; padding: 20px; border-radius: 10px; overflow: auto; font-size: 13px; line-height: 1.5; border: 1px solid #2a2a30; }
.tip { color: #888; font-size: 13px; margin: 12px 0 0; }
</style>
</head>
<body>
<div class="wrap">
<h1>🐙 bot.py — код для ukusy-bot (с загрузкой фото)</h1>
<div class="bar">
<button onclick="copyAll()">📋 Скопировать всё</button>
<button onclick="selectAll()">Выделить</button>
<span id="status" class="status"></span>
</div>
<pre id="code">import os
import json
import threading
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
import requests

app = Flask(__name__)
TOKEN = os.environ.get("TOKEN")
DATA_FILE = "/tmp/ukusy_data.json"
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


@app.route("/")
def home():
    return "Ukusy backend is alive!"


@app.route("/appss_verify")
def verify():
    return "appss_98ec27"


@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "no file"}), 400
    f = request.files["file"]
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "empty"}), 400
    ext = os.path.splitext(f.filename)[1].lower() or ".jpg"
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return jsonify({"ok": False, "error": "bad ext"}), 400
    name = f"{uuid.uuid4().hex}{ext}"
    f.save(os.path.join(UPLOAD_DIR, name))
    url = f"{request.host_url.rstrip('/')}/uploads/{name}"
    return jsonify({"ok": True, "url": url, "filename": name})


@app.route("/api/places", methods=["GET"])
def get_places():
    data = load_data()
    return jsonify({"places": data.get("places", [])})


@app.route("/api/places", methods=["POST"])
def add_place():
    payload = request.get_json() or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    data = load_data()
    new_id = max([p.get("id", 0) for p in data.get("places", [])] + [0]) + 1
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
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
    }
    data.setdefault("places", []).append(new_place)
    save_data(data)
    return jsonify({"ok": True, "place": new_place})


@app.route("/api/places/<int:place_id>/like", methods=["POST"])
def like_place(place_id):
    data = load_data()
    places = data.get("places", [])
    place = next((p for p in places if p.get("id") == place_id), None)
    if place is None:
        return jsonify({"error": "not found"}), 404
    place["likes"] = place.get("likes", 0) + 1
    save_data(data)
    return jsonify({"ok": True, "likes": place["likes"]})


@app.route("/api/comments/<int:place_id>", methods=["GET"])
def get_comments(place_id):
    data = load_data()
    comments = data.get("comments", {}).get(str(place_id), [])
    return jsonify({"comments": comments})


@app.route("/api/comments/<int:place_id>", methods=["POST"])
def add_comment(place_id):
    payload = request.get_json() or {}
    text = (payload.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text required"}), 400
    data = load_data()
    comments = data.setdefault("comments", {}).setdefault(str(place_id), [])
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
            requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                params={"chat_id": chat_id, "text": "appss_98ec27"})
        elif text == "/start":
            requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                params={"chat_id": chat_id,
                        "text": "Укусы Нячанга — твой гид по вкусной еде Кханьхоа!\n\nНайди лучшие кафе, добавь свои места, читай отзывы.\n\nОткрой приложение через меню → Открыть Гид"})
        elif text == "/help":
            requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                params={"chat_id": chat_id,
                        "text": "Команды:\n/start — начать\n/help — помощь\n/appss_verify — проверка"})
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
</pre>
<p class="tip">Открой в браузере на ПК → 📋 Скопировать всё → в GitHub замени содержимое bot.py → Commit changes → Manual Deploy.</p>
</div>
<script>
function copyAll() {
  const code = document.getElementById('code').innerText;
  navigator.clipboard.writeText(code).then(() => {
    const s = document.getElementById('status');
    s.textContent = '✅ Скопировано!';
    s.classList.remove('err');
  }, () => {
    const s = document.getElementById('status');
    s.textContent = '❌ Не вышло. Тыкни «Выделить» и Ctrl+C.';
    s.classList.add('err');
  });
}
function selectAll() {
  const r = document.createRange();
  r.selectNodeContents(document.getElementById('code'));
  const s = window.getSelection();
  s.removeAllRanges();
  s.addRange(r);
}
</script>
<script src="https://p.spru.io/badge.js" data-site="7e401a" defer></script>
</body>
</html>

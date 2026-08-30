import os
import json
import threading
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)
TOKEN = os.environ.get("TOKEN")
DATA_FILE = "/tmp/ukusy_data.json"

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

DEFAULT_PLACES = [
    {
        "id": 100,
        "name": "Thao Nhien",
        "rating": 4.7,
        "desc": "Бульон наваристый, говядина тонкими слайсами прямо в пиале — обваривается кипятком и тает. Зелени дают море: зелёный базилик, салат и ещё какие-то травы — не кинза. Ростки и лайм отдельно. Самое то — соевый соус + хойсин + свежий чили сбоку. Цена 39K за обычный фо бо — это подарок за такой объём. Открываются в 5:30 — идеально для тех, кто гуляет на рассвете или просто хочет начать день как местный.",
        "tags": ["фо бо", "супы", "вьетнамская кухня", "бюджетно", "утром"],
        "emoji": "\U0001F35C",
        "likes": 0,
        "comments": 0,
        "address": "102 CT4 CC MUD XH 2, Đường Ngô Thị Kim, Nha Trang",
        "phone": "0972 558 044",
        "hours": "5:30 — 20:00",
        "addedBy": "BAYO"
    }
]

@app.route("/")
def home():
    return "Ukusy backend is alive!"

@app.route("/appss_verify")
def verify():
    return "appss_98ec27"

@app.route("/api/places", methods=["GET"])
def get_places():
    data = load_data()
    places = DEFAULT_PLACES + data.get("places", [])
    return jsonify({"places": places})

@app.route("/api/places", methods=["POST"])
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
        "emoji": payload.get("emoji") or "\U0001F37D",
        "likes": 0,
        "comments": 0,
        "address": (payload.get("address") or "").strip()[:200],
        "phone": (payload.get("phone") or "").strip()[:40],
        "hours": (payload.get("hours") or "").strip()[:60],
        "photo": payload.get("photo") or "",
        "photos": payload.get("photos") or [],
        "addedBy": (payload.get("addedBy") or "Guest")[:40],
    }
    data.setdefault("places", []).append(new_place)
    save_data(data)
    return jsonify({"ok": True, "place": new_place})
@app.route("/api/places/<int:place_id>/like", methods=["POST"])
def like_place(place_id):
    data = load_data()
    place = next((p for p in data.get("places", []) if p.get("id") == place_id), None)
    if place is None:
        for p in DEFAULT_PLACES:
            if p.get("id") == place_id:
                place = p
                break
    if place is None:
        return jsonify({"error": "not found"}), 404
    place["likes"] = place.get("likes", 0) + 1
    idx = next((i for i, p in enumerate(data["places"]) if p.get("id") == place_id), -1)
    if idx >= 0:
        data["places"][idx] = place
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

import os
import json
import threading
import base64
import logging
from flask import Flask, request, jsonify
import requests

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ukusy")

app = Flask(__name__)

# Поддержка обоих имён для совместимости
TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("TOKEN")
PHOTO_CHANNEL = os.environ.get("PHOTO_CHANNEL", "@ukusy_photos_channel")
try:
    ADMIN_ID = int(os.environ.get("ADMIN_ID", "0") or 0)
except (TypeError, ValueError):
    ADMIN_ID = 0
PUBLIC_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
PORT = int(os.environ.get("PORT", "10000"))

# Временное хранилище одобренных фото — в ENV (base64 JSON), не на диске
APPROVED_ENV_KEY = "APPROVED_PHOTOS"
def load_approved():
    raw = os.environ.get(APPROVED_ENV_KEY, "")
    if not raw:
        return []
    try:
        return json.loads(base64.b64decode(raw).decode("utf-8"))
    except Exception:
        return []

def save_approved(items):
    """Сохранить нельзя на Render free — ENV только для чтения после старта.
    Поэтому просто держим в памяти процесса (сбрасывается при рестарте)."""
    log.info(f"approved count in memory: {len(items)}")

_lock = threading.Lock()
_pending = {}
_approved_inmem = load_approved()


DEFAULT_PLACES = [
    {
        "id": 100,
        "name": "Thảo Nhiên",
        "rating": 4.7,
        "desc": "Бульон наваристый, говядина тонкими слайсами прямо в пиале — обваривается кипятком и тает. Зелени дают море: зелёный базилик, салат и ещё какие-то травы — не кинза. Ростки и лайм отдельно. Самое то — соевый соус + хойсин + свежий чили сбоку. Цена 39K за обычный фо бо — это подарок за такой объём. Открываются в 5:30 — идеально для тех, кто гуляет на рассвете или просто хочет начать день как местный.",
        "tags": ["фо бо", "супы", "вьетнамская кухня", "бюджетно", "утром"],
        "emoji": "🍜",
        "likes": 0,
        "comments": 0,
        "address": "102 CT4 CC MUD XH 2, Đường Ngô Thị Kim, Nha Trang",
        "phone": "0972 558 044",
        "hours": "5:30 — 20:00",
        "addedBy": "BAYO"
    }
]


def tg_api(method, **params):
    if not TOKEN:
        log.error("TOKEN not set")
        return None
    try:
        r = requests.get(f"https://api.telegram.org/bot{TOKEN}/{method}",
                         params=params, timeout=15)
        return r.json()
    except Exception as e:
        log.error(f"tg_api {method}: {e}")
        return None


def send(chat_id, text, reply_markup=None):
    log.info(f"send to {chat_id}: {text[:60]}")
    params = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        params["reply_markup"] = json.dumps(reply_markup)
    r = tg_api("sendMessage", **params)
    if not r or not r.get("ok"):
        log.error(f"send FAILED to {chat_id}: {r}")
    return r


def forward_to_channel(file_id, caption):
    """Переслать фото в приватный канал. Возвращает новый file_id."""
    if not TOKEN or not PHOTO_CHANNEL:
        log.error("TOKEN or PHOTO_CHANNEL missing")
        return None
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
            data={"chat_id": PHOTO_CHANNEL, "photo": file_id, "caption": caption[:1024]},
            timeout=15,
        )
        data = r.json()
        if not data.get("ok"):
            log.error(f"forward failed: {data}")
            return None
        photos = data.get("result", {}).get("photo", [])
        if photos:
            return photos[-1]["file_id"]
    except Exception as e:
        log.error(f"forward_to_channel: {e}")
    return None


@app.route("/")
def home():
    return "Ukusy Nha Trang backend is alive!"


@app.route("/health")
def health():
    return jsonify({"ok": True, "approved": len(_approved_inmem), "admin": bool(ADMIN_ID), "channel": bool(PHOTO_CHANNEL)})


@app.route("/appss_verify")
def verify():
    return "appss_98ec27"


@app.route("/api/places", methods=["GET"])
def get_places():
    return jsonify({"places": DEFAULT_PLACES})


@app.route("/api/places", methods=["POST"])
def add_place():
    payload = request.get_json() or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    place = {
        "id": int(__import__("time").time()),
        "name": name[:80],
        "rating": float(payload.get("rating") or 4.5),
        "desc": (payload.get("desc") or "").strip()[:600],
        "tags": payload.get("tags") or [],
        "emoji": payload.get("emoji") or "🍜",
        "likes": 0,
        "comments": 0,
        "address": (payload.get("address") or "").strip()[:200],
        "phone": (payload.get("phone") or "").strip()[:40],
        "hours": (payload.get("hours") or "").strip()[:60],
        "photo": payload.get("photo") or "",
        "addedBy": (payload.get("addedBy") or "Гость")[:40],
    }
    return jsonify({"ok": True, "place": place})


@app.route(f"/{TOKEN or 'WEBHOOK_TOKEN_MISSING'}", methods=["POST"])
def webhook():
    if not TOKEN:
        return "token missing", 500
    data = request.get_json(silent=True) or {}

    if "callback_query" in data:
        handle_callback(data["callback_query"])
        return "ok"

    if "message" in data:
        message = data["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        if text == "/appss_verify":
            send(chat_id, "appss_98ec27")
        elif text == "/start":
            send(chat_id, "Укусы Нячанга — твой гид по вкусной еде Кханьхоа!\n\n"
                          "Найди лучшие кафе, добавь свои места, читай отзывы.\n\n"
                          "Открой приложение через меню → Open Guide 👇")
        elif text == "/help":
            send(chat_id, "Пришли фото с подписью (где, что вкусного) — опубликую после модерации.")
        elif "photo" in message:
            handle_photo(message)
        else:
            send(chat_id, "Пришли фото еды с подписью — добавлю в ленту Укусов Нячанга после модерации 🍜")

    return "ok"


def handle_photo(message):
    user_id = message["from"]["id"]
    user_name = message.get("from", {}).get("first_name", "Гость")
    photos = message.get("photo", [])
    log.info(f"handle_photo from user_id={user_id} name={user_name}")
    if not photos:
        log.warning("handle_photo: no photos in message")
        return
    file_id = photos[-1]["file_id"]
    caption = message.get("caption", "")

    # Если нет ADMIN_ID — фото сразу в канал (без модерации)
    if not ADMIN_ID:
        log.warning("ADMIN_ID not set, sending directly to channel")
        result = forward_to_channel(file_id, caption or f"от {user_name}")
        if result:
            send(user_id, "✅ Фото опубликовано в ленте Укусов Нячанга!")
        else:
            send(user_id, "⚠️ Ошибка публикации. Попробуй позже.")
        return

    # Сначала шлём фото админу (он увидит его в чате)
    log.info(f"sending photo to admin {ADMIN_ID}")
    photo_resp = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
        data={"chat_id": ADMIN_ID, "photo": file_id, "caption": f"📸 Новое фото от {user_name} (id {user_id})\n{caption or 'без подписи'}"},
        timeout=15,
    )
    log.info(f"admin photo response: {photo_resp.status_code}")
    
    # Генерируем короткий ключ и сохраняем в памяти
    import secrets
    short_id = secrets.token_urlsafe(6)[:8]
    with _lock:
        _pending[short_id] = {"user_id": user_id, "file_id": file_id, "name": user_name, "caption": caption}
    
    # Затем шлём кнопки с короткими callback_data
    msg_resp = send(
        ADMIN_ID,
        f"📸 Новое фото на модерацию\n\n"
        f"От: {user_name} (id {user_id})\n"
        f"Подпись: {caption or '—'}\n\n"
        f"Нажми кнопку ниже:",
        reply_markup={
            "inline_keyboard": [
                [
                    {"text": "✅ Одобрить", "callback_data": f"a:{short_id}"},
                    {"text": "❌ Отклонить", "callback_data": f"r:{short_id}"}
                ]
            ]
        },
    )
    log.info(f"admin button message response: {msg_resp}")
    
    send(user_id, "✅ Фото принято на модерацию! Обычно проверяем в течение дня.")


def handle_callback(callback):
    data = callback.get("data", "")
    admin_id = callback["from"]["id"]
    log.info(f"callback from {admin_id}: {data}")
    if admin_id != ADMIN_ID:
        log.warning(f"callback from non-admin {admin_id}, ignoring")
        return

    if data.startswith(("a:", "r:")):
        action, short_id = data.split(":", 1)
        with _lock:
            pending = _pending.pop(short_id, None)
        if not pending:
            send(ADMIN_ID, "⚠️ Фото не найдено (возможно уже обработано).")
            return
        user_id = pending["user_id"]
        user_name = pending["name"]
        file_id = pending["file_id"]
        caption = pending["caption"]

        if action == "a:":
            log.info(f"approving photo {short_id} from {user_id}")
            channel_file_id = forward_to_channel(file_id, caption or f"от {user_name}")
            if channel_file_id:
                send(user_id, "🎉 Твоё фото одобрено! Теперь оно в ленте Укусов Нячанга.")
                send(ADMIN_ID, f"✅ Фото одобрено и залито в канал (id {PHOTO_CHANNEL}).")
                with _lock:
                    _approved_inmem.append({
                        "file_id": channel_file_id,
                        "user_id": user_id,
                        "ts": __import__("time").time(),
                    })
            else:
                send(ADMIN_ID, "⚠️ Ошибка при загрузке в канал. Проверь, что бот — админ канала.")
        else:
            log.info(f"rejecting photo {short_id} from {user_id}")
            send(user_id, "😔 К сожалению, твоё фото не прошло модерацию.")
            send(ADMIN_ID, f"❌ Фото отклонено (от {user_name}).")


def setup_webhook():
    """Установить webhook на Render URL при старте."""
    if not TOKEN or not PUBLIC_URL:
        log.warning("webhook not set: TOKEN or RENDER_EXTERNAL_URL missing")
        return
    webhook_url = f"{PUBLIC_URL}/{TOKEN}"
    log.info(f"setting webhook: {PUBLIC_URL}/...")
    result = tg_api("setWebhook", url=webhook_url, allowed_updates=["message", "callback_query"])
    if result and result.get("ok"):
        log.info("webhook installed ok")
    else:
        log.error(f"webhook install failed: {result}")


with app.app_context():
    setup_webhook()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)

# Укусы Нячанга v3 — бот для канала @ukusy_photos
# Токен захардкожен — ничего не надо настраивать в Render
# После замены bot.py в GitHub: webhook автоматически заработает

import os
import json
import threading
import requests
from flask import Flask, request, jsonify

TOKEN = "8980305420:AAH7Bd100ZtYmujvt2aBMf18Hp3rB2i2Q4o"
ADMIN_ID = 8558294
CHANNEL = "@ukusy_photos"
API = f"https://api.telegram.org/bot{TOKEN}"

app = Flask(__name__)

# Хранилище pending submissions
# {chat_id: {"step": ..., "photo_id": ..., "name": ..., "address": ..., "rating": ...}}
_pending = {}
_lock = threading.Lock()


def send(chat_id, text, **kwargs):
    params = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    params.update(kwargs)
    return requests.post(f"{API}/sendMessage", json=params, timeout=10).json()


def edit(chat_id, message_id, text, reply_markup=None):
    params = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        params["reply_markup"] = reply_markup
    return requests.post(f"{API}/editMessageText", json=params, timeout=10).json()


def answer_callback(cb_id, text=""):
    requests.post(f"{API}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": text}, timeout=10)


def main_menu(chat_id, message_id=None, cb_id=None):
    text = (
        "🍜 <b>Укусы Нячанга</b>\n"
        "Твой гид по вкусной еде Кханьхоа.\n"
        "Найди лучшие кафе, добавь свои места, читай отзывы.\n\n"
        f"📢 Канал с отзывами: {CHANNEL}\n\n"
        "Выбирай действие ↓"
    )
    kb = {
        "inline_keyboard": [
            [{"text": "🍜 Лента последних мест", "callback_data": "feed"}],
            [{"text": "➕ Добавить место", "callback_data": "add"}],
            [{"text": "ℹ️ О боте", "callback_data": "about"}],
        ]
    }
    if message_id:
        edit(chat_id, message_id, text, json.dumps(kb))
    else:
        send(chat_id, text, reply_markup=json.dumps(kb))
    if cb_id:
        answer_callback(cb_id)


def show_feed(chat_id, message_id=None, cb_id=None):
    text = (
        f"📢 <b>Все отзывы — в канале {CHANNEL}</b>\n\n"
        "Там:\n"
        "• Свежие фото мест\n"
        "• Лайки ❤️ и реакции\n"
        "• Комментарии прямо в Telegram\n\n"
        "Жми кнопку ниже 👇"
    )
    kb = {
        "inline_keyboard": [
            [{"text": "📢 Открыть канал", "url": f"https://t.me/{CHANNEL.lstrip('@')}"}],
            [{"text": "↩️ В меню", "callback_data": "menu"}],
        ]
    }
    if message_id:
        edit(chat_id, message_id, text, json.dumps(kb))
    else:
        send(chat_id, text, reply_markup=json.dumps(kb))
    if cb_id:
        answer_callback(cb_id)


def show_about(chat_id, message_id=None, cb_id=None):
    text = (
        "ℹ️ <b>О боте</b>\n\n"
        "Этот бот помогает жителям и туристам Нячанга находить "
        "лучшие кафе и уличную еду.\n\n"
        "Все добавленные места публикуются в канале "
        f"{CHANNEL} после модерации.\n\n"
        "Версия: 3.0\n"
    )
    kb = {"inline_keyboard": [[{"text": "↩️ В меню", "callback_data": "menu"}]]}
    if message_id:
        edit(chat_id, message_id, text, json.dumps(kb))
    else:
        send(chat_id, text, reply_markup=json.dumps(kb))
    if cb_id:
        answer_callback(cb_id)


def add_start(chat_id, message_id=None, cb_id=None):
    text = (
        "➕ <b>Добавить место</b>\n\n"
        "Шаг 1 из 4:\n"
        "📸 Пришли фото еды.\n\n"
        "Отправляй как фото (не файлом), чтобы я видел превью."
    )
    kb = {"inline_keyboard": [[{"text": "↩️ Отмена", "callback_data": "menu"}]]}
    if message_id:
        edit(chat_id, message_id, text, json.dumps(kb))
    else:
        send(chat_id, text, reply_markup=json.dumps(kb))
    if cb_id:
        answer_callback(cb_id)
    with _lock:
        _pending[chat_id] = {"step": "photo"}


def add_prompt_name(chat_id):
    with _lock:
        st = _pending.get(chat_id, {})
        st["step"] = "name"
        _pending[chat_id] = st
    send(chat_id, "Шаг 2 из 4:\n🍜 <b>Название места?</b>\nНапиши текстом.",
         reply_markup=json.dumps({"inline_keyboard": [[{"text": "↩️ Отмена", "callback_data": "menu"}]]}))


def add_prompt_address(chat_id):
    with _lock:
        st = _pending.get(chat_id, {})
        st["step"] = "address"
        _pending[chat_id] = st
    send(chat_id, "Шаг 3 из 4:\n📍 <b>Адрес или район?</b>\nНапиши текстом.",
         reply_markup=json.dumps({"inline_keyboard": [[{"text": "↩️ Отмена", "callback_data": "menu"}]]}))


def add_prompt_rating(chat_id):
    with _lock:
        st = _pending.get(chat_id, {})
        st["step"] = "rating"
        _pending[chat_id] = st
    kb = {
        "inline_keyboard": [
            [
                {"text": "⭐", "callback_data": "rate:1"},
                {"text": "⭐⭐", "callback_data": "rate:2"},
                {"text": "⭐⭐⭐", "callback_data": "rate:3"},
                {"text": "⭐⭐⭐⭐", "callback_data": "rate:4"},
                {"text": "⭐⭐⭐⭐⭐", "callback_data": "rate:5"},
            ],
            [{"text": "↩️ Отмена", "callback_data": "menu"}],
        ]
    }
    send(chat_id, "Шаг 4 из 4:\n⭐ <b>Твоя оценка?</b>", reply_markup=json.dumps(kb))


def submit_for_moderation(chat_id, rating):
    with _lock:
        st = _pending.pop(chat_id, {})
    st["rating"] = rating
    caption = (
        f"🍜 <b>{st.get('name', '?')}</b>\n"
        f"📍 {st.get('address', '?')}\n"
        f"⭐ {'⭐' * rating}\n"
        f"👤 От: {st.get('user_name', 'Аноним')}"
    )
    # Отправляем админу с кнопками approve/reject
    kb = {
        "inline_keyboard": [
            [
                {"text": "✅ Опубликовать", "callback_data": f"approve:{chat_id}:{rating}"},
                {"text": "❌ Отклонить", "callback_data": f"reject:{chat_id}"},
            ]
        ]
    }
    requests.post(
        f"{API}/sendPhoto",
        json={
            "chat_id": ADMIN_ID,
            "photo": st["photo_id"],
            "caption": caption,
            "parse_mode": "HTML",
            "reply_markup": json.dumps(kb),
        },
        timeout=10,
    )
    send(chat_id, "✅ Отправлено на модерацию! Я напишу когда опубликую.")


def publish_to_channel(photo_id, name, address, rating, user_name):
    caption = (
        f"🍜 <b>{name}</b>\n"
        f"📍 {address}\n"
        f"⭐ {'⭐' * rating}\n\n"
        f"👤 Добавил: {user_name}\n\n"
        f"#нячанг #еда #обзор"
    )
    requests.post(
        f"{API}/sendPhoto",
        json={
            "chat_id": CHANNEL,
            "photo": photo_id,
            "caption": caption,
            "parse_mode": "HTML",
        },
        timeout=10,
    )


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True, silent=True) or {}
    msg = data.get("message") or data.get("edited_message")
    cb = data.get("callback_query")

    # === Callback queries (кнопки) ===
    if cb:
        chat_id = cb["message"]["chat"]["id"]
        msg_id = cb["message"]["message_id"]
        cb_id = cb["id"]
        action = cb.get("data", "")

        if action == "menu":
            main_menu(chat_id, message_id=msg_id, cb_id=cb_id)
        elif action == "feed":
            show_feed(chat_id, message_id=msg_id, cb_id=cb_id)
        elif action == "about":
            show_about(chat_id, message_id=msg_id, cb_id=cb_id)
        elif action == "add":
            add_start(chat_id, message_id=msg_id, cb_id=cb_id)
        elif action.startswith("rate:"):
            rating = int(action.split(":")[1])
            submit_for_moderation(chat_id, rating)
            answer_callback(cb_id, "Отправлено!")
        elif action.startswith("approve:"):
            parts = action.split(":")
            user_chat_id = int(parts[1])
            rating = int(parts[2])
            with _lock:
                st = _pending.get(user_chat_id, {})
            if not st or not st.get("photo_id"):
                answer_callback(cb_id, "Нет данных")
                return "ok"
            publish_to_channel(
                st["photo_id"],
                st.get("name", "?"),
                st.get("address", "?"),
                rating,
                st.get("user_name", "Аноним"),
            )
            with _lock:
                _pending.pop(user_chat_id, None)
            edit(chat_id, msg_id, "✅ Опубликовано!", None)
            send(user_chat_id, "🎉 Твоё место опубликовано в канале!")
            answer_callback(cb_id, "Опубликовано")
        elif action.startswith("reject:"):
            user_chat_id = int(action.split(":")[1])
            with _lock:
                _pending.pop(user_chat_id, None)
            edit(chat_id, msg_id, "❌ Отклонено.", None)
            send(user_chat_id, "😔 Модератор отклонил место. Попробуй другое.")
            answer_callback(cb_id, "Отклонено")
        return "ok"

    # === Сообщения ===
    if not msg:
        return "ok"
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")
    photo = msg.get("photo")
    user = msg.get("from", {})
    user_name = user.get("first_name", "Аноним")

    with _lock:
        state = _pending.get(chat_id, {}).get("step")

    # /start
    if text == "/start":
        with _lock:
            _pending.pop(chat_id, None)
        main_menu(chat_id)
        return "ok"

    # /help
    if text == "/help":
        send(chat_id, "Просто жми кнопки в меню.\n/start — на главную.")
        return "ok"

    # FSM
    if state == "photo":
        if not photo:
            send(chat_id, "Жду фото (не файл). Пришли как фото 📸")
            return "ok"
        biggest = photo[-1]
        with _lock:
            st = _pending.get(chat_id, {})
            st["photo_id"] = biggest["file_id"]
            st["user_name"] = user_name
            _pending[chat_id] = st
        add_prompt_name(chat_id)
        return "ok"

    if state == "name":
        if not text:
            send(chat_id, "Напиши название текстом.")
            return "ok"
        with _lock:
            st = _pending.get(chat_id, {})
            st["name"] = text.strip()
            _pending[chat_id] = st
        add_prompt_address(chat_id)
        return "ok"

    if state == "address":
        if not text:
            send(chat_id, "Напиши адрес текстом.")
            return "ok"
        with _lock:
            st = _pending.get(chat_id, {})
            st["address"] = text.strip()
            _pending[chat_id] = st
        add_prompt_rating(chat_id)
        return "ok"

    # Просто текст без контекста
    if text and not state:
        send(chat_id, "Не понял 🤔 Жми /start для главного меню.")

    return "ok"


@app.route("/")
def home():
    return "Ukusy bot v3 is alive!"


@app.route("/health")
def health():
    return jsonify({"ok": True, "pending": len(_pending), "token_suffix": TOKEN[-10:]})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)

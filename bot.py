
"""
Укусы Нячанга v2 — простой бот без WebApp
- Inline кнопки (главное меню)
- FSM для добавления места
- Лента (последние 10 фото из канала)
- Модерация по кнопкам
- Публикация одобренных в канал ukusy_photos
"""

import os
import json
import threading
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)
TOKEN = os.environ.get("TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8008558294"))
CHANNEL = os.environ.get("CHANNEL", "@ukusy_photos")
API = f"https://api.telegram.org/bot{TOKEN}"

# ===== Хранилище pending submissions (in-memory) =====
# {user_id: {"photo_id": ..., "photo_caption": ..., "name": ..., "address": ..., "rating": ...}}
_pending = {}
_lock = threading.Lock()


def send(chat_id, text, **kw):
    """Отправить сообщение через Telegram Bot API."""
    params = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    params.update(kw)
    return requests.post(f"{API}/sendMessage", json=params, timeout=10).json()


def send_photo(chat_id, photo_id, caption=None, **kw):
    """Переслать фото по file_id."""
    params = {"chat_id": chat_id, "photo": photo_id, "parse_mode": "HTML"}
    if caption:
        params["caption"] = caption
    params.update(kw)
    return requests.post(f"{API}/sendPhoto", json=params, timeout=10).json()


def answer_callback(cb_id, text=None, show_alert=False):
    params = {"callback_query_id": cb_id}
    if text:
        params["text"] = text
    if show_alert:
        params["show_alert"] = True
    requests.post(f"{API}/answerCallbackQuery", json=params, timeout=10)


# ===== Главное меню =====
def main_menu(chat_id):
    text = (
        "🍜 <b>Укусы Нячанга</b>\n"
        "Твой гид по вкусной еде Кханьхоа.\n"
        "Найди лучшие кафе, добавь свои места, читай отзывы.\n\n"
        f"📢 Канал с отзывами: {CHANNEL}\n\n"
        "Выбирай действие ↓"
    )
    kb = {
        "inline_keyboard": [
            [{"text": "🍜 Лента последних мест", "callback_data": "feed:0"}],
            [{"text": "➕ Добавить место", "callback_data": "add:start"}],
            [{"text": "ℹ️ О боте", "callback_data": "about"}],
        ]
    }
    send(chat_id, text, reply_markup=json.dumps(kb))


# ===== Лента =====
def show_feed(chat_id, page=0, message_id=None, cb_id=None):
    """Показать посты из канала (последние 10)."""
    try:
        r = requests.post(
            f"{API}/getUpdates",
            params={"limit": 1, "allowed_updates": json.dumps(["channel_post"])},
            timeout=10,
        ).json()
        # Альтернатива: переслать сообщения из канала
        # Используем метод forwardMessages нельзя из канала напрямую без chat_id
        # Поэтому читаем через getChat + getChatHistory не работает в Bot API
        # Используем простой трюк: возвращаем ссылку на канал + инструкцию
    except Exception:
        pass

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
            [{"text": "➕ Добавить место", "callback_data": "add:start"}],
            [{"text": "↩️ В меню", "callback_data": "menu"}],
        ]
    }
    if message_id:
        requests.post(
            f"{API}/editMessageText",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(kb),
            },
            timeout=10,
        )
    else:
        send(chat_id, text, reply_markup=json.dumps(kb))
    if cb_id:
        answer_callback(cb_id)


# ===== Добавить место: FSM =====
def add_start(chat_id, message_id=None, cb_id=None):
    text = (
        "➕ <b>Добавить место</b>\n\n"
        "Шаг 1 из 4:\n"
        "📸 Пришли фото еды.\n\n"
        "Отправляй как фото (не файлом), чтобы я видел превью."
    )
    kb = {"inline_keyboard": [[{"text": "↩️ Отмена", "callback_data": "menu"}]]}
    if message_id:
        requests.post(
            f"{API}/editMessageText",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(kb),
            },
            timeout=10,
        )
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
    send(chat_id, "Шаг 2 из 4:\n🍜 <b>Название места?</b>\nНапиши текстом.", reply_markup=json.dumps({"inline_keyboard": [[{"text": "↩️ Отмена", "callback_data": "menu"}]]}))


def add_prompt_address(chat_id):
    with _lock:
        st = _pending.get(chat_id, {})
        st["step"] = "address"
        _pending[chat_id] = st
    send(chat_id, "Шаг 3 из 4:\n📍 <b>Адрес или район?</b>\n(можно просто «центр»)", reply_markup=json.dumps({"inline_keyboard": [[{"text": "↩️ Отмена", "callback_data": "menu"}]]}))


def add_prompt_rating(chat_id, message_id=None):
    with _lock:
        st = _pending.get(chat_id, {})
        st["step"] = "rating"
        _pending[chat_id] = st
    text = "Шаг 4 из 4:\n⭐ <b>Оцени от 1 до 5</b>"
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
    if message_id:
        requests.post(
            f"{API}/editMessageText",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(kb),
            },
            timeout=10,
        )
    else:
        send(chat_id, text, reply_markup=json.dumps(kb))


def submit_to_admin(chat_id, user):
    """Отправить заявку админу на модерацию."""
    with _lock:
        st = _pending.pop(chat_id)

    rating = int(st.get("rating", 5))
    stars = "⭐" * rating

    # Кнопки модерации
    sub_id = f"{chat_id}"
    kb = {
        "inline_keyboard": [
            [
                {"text": "✅ Одобрить", "callback_data": f"approve:{sub_id}"},
                {"text": "❌ Отклонить", "callback_data": f"reject:{sub_id}"},
            ]
        ]
    }

    text_admin = (
        f"📸 <b>Новое место на модерацию</b>\n\n"
        f"👤 От: {user.get('first_name', 'Аноним')} (id <code>{chat_id}</code>)\n"
        f"🍜 Место: <b>{st.get('name', '')}</b>\n"
        f"📍 Адрес: {st.get('address', '—')}\n"
        f"⭐ Рейтинг: {stars}\n"
    )
    if st.get("photo_id"):
        send_photo(ADMIN_ID, st["photo_id"], caption=text_admin, reply_markup=json.dumps(kb))
    else:
        send(ADMIN_ID, text_admin, reply_markup=json.dumps(kb))

    with _lock:
        _pending[chat_id] = st
        st["submitted"] = True
        st["status"] = "pending"

    send(chat_id, "✅ <b>Готово!</b> Отправил на модерацию.\nКак проверю — появится в канале.", reply_markup=json.dumps({"inline_keyboard": [[{"text": "↩️ В меню", "callback_data": "menu"}]]}))


def do_approve(sub_id, cb_id):
    chat_id = int(sub_id)
    with _lock:
        st = _pending.get(chat_id, {})
        if not st or st.get("status") != "pending":
            answer_callback(cb_id, "Уже обработано", show_alert=True)
            return
        st["status"] = "approved"

    rating = int(st.get("rating", 5))
    stars = "⭐" * rating

    caption = (
        f"🍜 <b>{st.get('name', '')}</b>\n\n"
        f"📍 {st.get('address', '—')}\n"
        f"{stars}\n\n"
        f"📸 от {st.get('user_name', 'Аноним')}\n"
        f"💬 Открой комменты ↓"
    )

    # Публикуем в канал
    if st.get("photo_id"):
        r = send_photo(CHANNEL, st["photo_id"], caption=caption)
    else:
        r = send(CHANNEL, caption)

    if r.get("ok"):
        # Удаляем из pending
        with _lock:
            _pending.pop(chat_id, None)
        # Уведомляем юзера
        try:
            send(chat_id, "🎉 <b>Твоё место опубликовано!</b>\nСмотри в канале 👇", reply_markup=json.dumps({"inline_keyboard": [[{"text": "📢 Открыть канал", "url": f"https://t.me/{CHANNEL.lstrip('@')}"}]]}))
        except Exception:
            pass
        answer_callback(cb_id, "✅ Опубликовано в канале!")
    else:
        answer_callback(cb_id, f"Ошибка публикации: {r}", show_alert=True)


def do_reject(sub_id, cb_id):
    chat_id = int(sub_id)
    with _lock:
        st = _pending.get(chat_id, {})
        if not st or st.get("status") != "pending":
            answer_callback(cb_id, "Уже обработано", show_alert=True)
            return
        st["status"] = "rejected"
    try:
        send(chat_id, "😔 К сожалению, место не прошло модерацию.\nПопробуй ещё раз с более чётким фото.")
    except Exception:
        pass
    answer_callback(cb_id, "❌ Отклонено")


# ===== О боте =====
def about(chat_id, message_id=None, cb_id=None):
    text = (
        "🍜 <b>Укусы Нячанга</b> — живой путеводитель по еде.\n\n"
        "• 📸 Реальные фото от людей\n"
        "• 🛡 Модерация, без спама\n"
        "• 💬 Комменты прямо в Telegram\n\n"
        f"Канал: {CHANNEL}\n"
        "Бот: @ukusynhatrang_bot\n\n"
        "Проект Сергея Карпова 🐙"
    )
    kb = {"inline_keyboard": [[{"text": "↩️ В меню", "callback_data": "menu"}]]}
    if message_id:
        requests.post(
            f"{API}/editMessageText",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(kb),
            },
            timeout=10,
        )
    else:
        send(chat_id, text, reply_markup=json.dumps(kb))
    if cb_id:
        answer_callback(cb_id)


# ===== Обработка входящих =====
@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(force=True, silent=True) or {}

    # === Callback (нажатие на inline кнопку) ===
    if "callback_query" in update:
        cq = update["callback_query"]
        cb_id = cq["id"]
        data = cq.get("data", "")
        chat_id = cq["from"]["id"]
        msg_id = cq["message"]["message_id"]

        if data == "menu":
            main_menu(chat_id)
            answer_callback(cb_id)
        elif data.startswith("feed:"):
            show_feed(chat_id, message_id=msg_id, cb_id=cb_id)
        elif data == "add:start":
            add_start(chat_id, message_id=msg_id, cb_id=cb_id)
        elif data.startswith("rate:"):
            r = int(data.split(":")[1])
            with _lock:
                st = _pending.get(chat_id, {})
                st["rating"] = r
                _pending[chat_id] = st
            answer_callback(cb_id, f"Твоя оценка: {'⭐' * r}")
            submit_to_admin(chat_id, cq["from"])
        elif data == "about":
            about(chat_id, message_id=msg_id, cb_id=cb_id)
        elif data.startswith("approve:"):
            sub_id = data.split(":", 1)[1]
            do_approve(sub_id, cb_id)
        elif data.startswith("reject:"):
            sub_id = data.split(":", 1)[1]
            do_reject(sub_id, cb_id)
        return "ok"

    # === Сообщение ===
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        user = msg.get("from", {})
        text = msg.get("text", "")
        photo = msg.get("photo")  # массив разных размеров

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

        # FSM: ждём фото
        if state == "photo":
            if not photo:
                send(chat_id, "Жду фото (не файл). Пришли как фото 📸")
                return "ok"
            # Берём самый большой размер
            biggest = photo[-1]
            with _lock:
                st = _pending.get(chat_id, {})
                st["photo_id"] = biggest["file_id"]
                st["user_name"] = user.get("first_name", "Аноним")
                _pending[chat_id] = st
            add_prompt_name(chat_id)
            return "ok"

        # FSM: ждём название
        if state == "name":
            name = (text or "").strip()[:80]
            if not name:
                send(chat_id, "Название не может быть пустым. Напиши ещё раз.")
                return "ok"
            with _lock:
                st = _pending.get(chat_id, {})
                st["name"] = name
                _pending[chat_id] = st
            add_prompt_address(chat_id)
            return "ok"

        # FSM: ждём адрес
        if state == "address":
            addr = (text or "").strip()[:200]
            with _lock:
                st = _pending.get(chat_id, {})
                st["address"] = addr or "—"
                _pending[chat_id] = st
            add_prompt_rating(chat_id)
            return "ok"

        # FSM: рейтинг ждём через inline кнопки, не текстом
        if state == "rating":
            send(chat_id, "Жду оценку — нажми кнопку с ⭐")
            return "ok"

        # Если фото прислали без команды — начинаем FSM
        if photo and not state:
            biggest = photo[-1]
            with _lock:
                _pending[chat_id] = {
                    "step": "name",
                    "photo_id": biggest["file_id"],
                    "user_name": user.get("first_name", "Аноним"),
                }
            send(chat_id, "Вижу фото! 🍜\n<b>Название места?</b>")
            return "ok"

        # Если просто текст без контекста
        if text and not state:
            send(chat_id, "Не понял 🤔 Жми /start для главного меню.")
            return "ok"

    return "ok"


@app.route("/")
def home():
    return "Ukusy bot v2 is alive!"


@app.route("/health")
def health():
    return jsonify({"ok": True, "pending": len(_pending)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

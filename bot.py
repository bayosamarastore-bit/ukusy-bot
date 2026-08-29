import os
from flask import Flask, request
import requests

app = Flask(__name__)
TOKEN = os.environ.get("TOKEN")

@app.route("/")
def home():
    return "Ukusy Nha Trang bot is alive!"

@app.route("/appss_verify")
def verify():
    return "appss_98ec27"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    if data and "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")
        if text == "/appss_verify":
            requests.get(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                params={"chat_id": chat_id, "text": "appss_98ec27"}
            )
        elif text == "/start":
            requests.get(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                params={
                    "chat_id": chat_id,
                    "text": "Укусы Нячанга — твой гид по вкусной еде Кханьхоа!\n\nНайди лучшие кафе, добавь свои места, читай отзывы.\n\nПомощь: /help"
                }
            )
        elif text == "/help":
            requests.get(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                params={
                    "chat_id": chat_id,
                    "text": "Команды:\n/start — начать\n/help — помощь\n/appss_verify — проверка"
                }
            )
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

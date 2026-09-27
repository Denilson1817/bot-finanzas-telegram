"""Utilidad de un solo uso: obtiene tu Telegram user ID usando tu propio bot,
sin depender de bots de terceros.

Uso:
  1. En Telegram, manda cualquier mensaje a tu bot (ej. /start).
  2. Corre: python obtener_mi_id.py
  3. Pega tu TELEGRAM_BOT_TOKEN cuando se te pida (o ya debe estar en .env).
"""

import json
import os
import urllib.request

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        token = input("Pega tu TELEGRAM_BOT_TOKEN (el que te dio BotFather): ").strip()

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.load(resp)

    if not data.get("ok"):
        print("Error al consultar Telegram:", data)
        return

    updates = data["result"]
    if not updates:
        print(
            "No hay mensajes pendientes. Manda un mensaje (ej. /start) a tu bot "
            "en Telegram y vuelve a correr este script."
        )
        return

    vistos = {}
    for update in updates:
        msg = update.get("message") or update.get("edited_message")
        if not msg:
            continue
        user = msg["from"]
        vistos[user["id"]] = user

    print("Usuarios que te han escrito a este bot:\n")
    for user_id, user in vistos.items():
        nombre = user.get("first_name", "")
        username = f"@{user['username']}" if user.get("username") else "(sin username)"
        print(f"  id: {user_id}  ->  {nombre} {username}")

    print("\nUsa el id que corresponda a TU cuenta como ALLOWED_USER_ID en .env")


if __name__ == "__main__":
    main()

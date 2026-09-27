import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

TZ = ZoneInfo("America/Mexico_City")

PRESUPUESTO_CAJA_DEFAULT_CENTAVOS = 125_000
META_AHORRO_SEMANAL_DEFAULT_CENTAVOS = 100_000


def _get_bot_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "Falta TELEGRAM_BOT_TOKEN en el entorno. Copia .env.example a .env y complétalo."
        )
    return token


def _get_allowed_user_id() -> int:
    raw = os.environ.get("ALLOWED_USER_ID")
    if not raw:
        raise RuntimeError(
            "Falta ALLOWED_USER_ID en el entorno. Copia .env.example a .env y complétalo."
        )
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError("ALLOWED_USER_ID debe ser un número entero.") from exc


def get_db_url() -> str:
    return os.environ.get("DB_URL", "sqlite:///finanzas.db")


TELEGRAM_BOT_TOKEN = None
ALLOWED_USER_ID = None


def load_runtime_config() -> None:
    """Lee y valida las variables de entorno requeridas para correr el bot.

    Se llama explícitamente desde main.py (no al importar este módulo) para
    que los tests puedan importar app.config sin necesitar un .env.
    """
    global TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID
    TELEGRAM_BOT_TOKEN = _get_bot_token()
    ALLOWED_USER_ID = _get_allowed_user_id()

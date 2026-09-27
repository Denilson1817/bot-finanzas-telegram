import logging

from telegram.ext import ApplicationBuilder

from app import config
from app.bot.handlers import register_handlers
from app.db import create_session_factory

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


def main() -> None:
    config.load_runtime_config()
    session_factory = create_session_factory(config.get_db_url())

    application = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    application.bot_data["Session"] = session_factory
    register_handlers(application, config.ALLOWED_USER_ID)

    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()

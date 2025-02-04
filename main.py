import os
import json
import logging
from typing import Dict
import aiohttp
from aiohttp import ClientTimeout
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

MODE_LIVE = "live"
MODE_SANDBOX = "sandbox"

BASE_API = f"http://{os.environ.get('API_HOST')}:{os.environ.get('API_PORT')}/api/"
API_URL_LIVE = f"{BASE_API}check-imei"
API_URL_SANDBOX = f"{BASE_API}check-imei-sandbox"

TOKEN = os.environ.get("API_TOKEN")
TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN")
TEST = os.environ.get("TEST") == "True"


def load_env_vars():
    """Загружает переменные окружения и проверяет их наличие."""
    required_vars = ["API_HOST", "API_PORT", "API_TOKEN", "BOT_TOKEN", "TEST"]
    for var in required_vars:
        if not os.environ.get(var):
            raise EnvironmentError(f"Missing environment variable: {var}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет сообщение с кнопками для выбора режима."""
    keyboard = [
        [InlineKeyboardButton(f"Режим {MODE_LIVE}", callback_data=MODE_LIVE)],
        [InlineKeyboardButton(f"Режим {MODE_SANDBOX}", callback_data=MODE_SANDBOX)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите режим работы:", reply_markup=reply_markup)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатие кнопки и сохраняет выбранный режим."""
    query = update.callback_query
    await query.answer()
    context.user_data["selected_mode"] = query.data
    if query.data == MODE_LIVE:
        await query.edit_message_text(
            text=f"Вы выбрали Режим {MODE_LIVE}. Введите imei:"
        )
    elif query.data == MODE_SANDBOX:
        await query.edit_message_text(
            text=f"Вы выбрали Режим {MODE_SANDBOX}. Введите imei:"
        )


async def send_api_request(url: str, data: Dict) -> Dict:
    """Отправляет POST-запрос на API и возвращает ответ."""

    ssl_context = False if TEST else None
    logger.info(f"Sending API request to {url} with data: {data}")
    try:
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=None), timeout=ClientTimeout(total=5)
        ) as session:
            async with session.post(
                url, headers={"token": TOKEN}, params=data
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"API request failed with status {response.status}")
                    return {"error": f"Request failed with status {response.status}"}
    except Exception as e:
        logger.error(f"Error during API request: {e}")
        return {"error": "Failed to connect to API"}


async def process_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает введенные данные и отправляет запрос на API."""
    user_input = update.message.text
    selected_mode = context.user_data.get("selected_mode")
    if not selected_mode:
        await update.message.reply_text("Сначала выберите режим работы.")
        return

    api_url = API_URL_LIVE if selected_mode == MODE_LIVE else API_URL_SANDBOX
    response_data = await send_api_request(api_url, {"imei": user_input})

    formatted_response = json.dumps(response_data, indent=4, ensure_ascii=False)
    for d in formatted_response:
        await update.message.reply_text(
                    f"Ответ от API:\n<code>{d}</code>", parse_mode="HTML"
                )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Логирует ошибки и отправляет сообщение об ошибке пользователю."""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    error_message = "Произошла ошибка. Попробуйте снова."
    if isinstance(context.error, aiohttp.ClientConnectorError):
        error_message = "Не удалось подключиться к API. Пожалуйста, попробуйте позже."
    elif isinstance(context.error, aiohttp.ClientResponseError):
        error_message = f"Ошибка API: {context.error.status}. Попробуйте снова."

    if update and hasattr(update, "message"):
        await update.message.reply_text(error_message)


def main() -> None:
    """Запускает телеграм-бота."""
    load_env_vars()

    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .connect_timeout(5)
        .read_timeout(5)
        .write_timeout(5)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, process_data)
    )
    application.add_error_handler(error_handler)

    application.run_polling()


if __name__ == "__main__":
    import asyncio

    main()

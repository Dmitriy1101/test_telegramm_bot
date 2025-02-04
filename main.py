import os
import json
import logging
from typing import Dict

import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

MODE_LIVE = "live"
MODE_SANDBOX = "sandbox"
BASE_API = f"https://{os.environ.get('API_HOST')}:{os.environ.get('API_PORT')}"
API_URL_LIVE = f"{BASE_API}/api/check-imei"
API_URL_SANDBOX = f"{BASE_API}/check-imei-sandbox"
TOKEN = os.environ.get("API_TOKEN")
TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN")


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

    async with aiohttp.ClientSession(trust_env=True) as session:
        async with session.post(
            url, headers={"token": TOKEN}, params=data
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                logger.error(f"API request failed with status {response.status}")
                return {"error": f"Request failed with status {response.status}"}


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
    await update.message.reply_text(
        f"Ответ от API:\n<code>{formatted_response}</code>", parse_mode="HTML"
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Логирует ошибки и отправляет сообщение об ошибке пользователю."""

    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    await update.message.reply_text("Произошла ошибка. Попробуйте снова.")



def main() -> None:
    """Запускает телеграм-бота."""

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, process_data)
    )

    application.add_error_handler(error_handler)

    application.run_polling()


if __name__ == "__main__":
    main()

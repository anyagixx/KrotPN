# FILE: telegram-bot/bot.py
# VERSION: 1.0.0
# ROLE: ENTRY_POINT
# MAP_MODE: SUMMARY
# START_MODULE_CONTRACT
#   PURPOSE: Telegram bot for KrotPN — auth mediation, config delivery, subscription status
#   SCOPE: Telegram commands, backend API integration, user auth flow
#   DEPENDS: M-001 (core config), M-011 (telegram-bot), M-002 (users API), M-003 (vpn API)
#   LINKS: M-011 (telegram-bot), V-M-011
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   BackendClient (class): HTTP client for backend API
#     - telegram_auth: Authenticate user via Telegram
#     - get_user: Fetch current user profile
#     - get_vpn_config: Retrieve VPN configuration
#     - get_subscription: Retrieve subscription status
#     - get_plans: Retrieve available billing plans
#   start_command (async): Handle /start command, authenticate user, show welcome menu
#   help_command (async): Handle /help command, show usage instructions
#   config_command (async): Handle /config command, deliver VPN config as file
#   status_command (async): Handle /status command, show subscription status
#   plans_command (async): Handle /plans command, list billing plans
#   referral_command (async): Handle /referral command, show referral program info
#   button_callback (async): Handle inline button callbacks, dispatch to command handlers
#   main (sync): Entry point — configure and run bot (webhook or polling)
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY

"""
KrotPN Telegram Bot.

GRACE-lite module contract:
- Provides a convenience channel over backend APIs, not a separate source of truth.
- Bot auth ultimately depends on backend `/api/auth/telegram`.
- User access tokens are stored in process memory only; restarts lose bot session state.
- Bot changes should preserve parity with backend auth/subscription/config flows.
"""
# <!-- GRACE: module="M-011" entry-point="EP-004" -->

import asyncio
import os
from datetime import datetime

import httpx
from loguru import logger
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackContext,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Configuration
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL")
PORT = int(os.getenv("PORT", "8443"))

# Configure logging
logger.add(
    "logs/bot_{time}.log",
    rotation="1 day",
    retention="7 days",
    level="INFO",
)


# START_BLOCK: class BackendClient — HTTP client wrapping backend API calls
class BackendClient:
    """Client for backend API."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def telegram_auth(self, telegram_id: int, username: str | None) -> dict:
        """Authenticate via Telegram."""
        response = await self.client.post(
            f"{self.base_url}/api/auth/telegram",
            json={
                "telegram_id": telegram_id,
                "telegram_username": username,
            },
            headers={"X-Telegram-Bot-Token": BOT_TOKEN} if BOT_TOKEN else None,
        )
        response.raise_for_status()
        return response.json()

    async def get_user(self, token: str) -> dict:
        """Get current user."""
        response = await self.client.get(
            f"{self.base_url}/api/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        return response.json()

    async def get_vpn_config(self, token: str) -> str:
        """Get VPN config."""
        response = await self.client.get(
            f"{self.base_url}/api/vpn/config",
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        return response.json()

    async def get_subscription(self, token: str) -> dict:
        """Get subscription status."""
        response = await self.client.get(
            f"{self.base_url}/api/billing/subscription",
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        return response.json()

    async def get_plans(self) -> list:
        """Get available plans."""
        response = await self.client.get(f"{self.base_url}/api/billing/plans")
        response.raise_for_status()
        return response.json()
# END_BLOCK: class BackendClient


backend = BackendClient(BACKEND_URL)

# Store user tokens (in production, use Redis)
user_tokens: dict[int, str] = {}


# START_BLOCK: async start_command — handle /start, authenticate user, show welcome menu
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    telegram_id = update.effective_user.id
    username = update.effective_user.username

    # Check for referral code
    ref_code = None
    if context.args and len(context.args) > 0:
        ref_code = context.args[0]

    # Authenticate
    try:
        data = await backend.telegram_auth(telegram_id, username)
        token = data["access_token"]
        user_tokens[telegram_id] = token

        user = await backend.get_user(token)

        keyboard = [
            [InlineKeyboardButton("📱 Получить конфиг", callback_data="config")],
            [InlineKeyboardButton("📊 Моя подписка", callback_data="subscription")],
            [InlineKeyboardButton("💰 Тарифы", callback_data="plans")],
            [InlineKeyboardButton("🔗 Реферальная ссылка", callback_data="referral")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        welcome_text = f"""
🛡️ *Добро пожаловать в KrotPN!*

Привет, {user.get('display_name', 'пользователь')}!

Я помогу тебе управлять VPN подпиской:

• 📱 *Получить конфиг* — скачать конфигурацию
• 📊 *Моя подписка* — статус и остаток дней
• 💰 *Тарифы* — доступные планы
• 🔗 *Реферальная ссылка* — пригласи друзей

Выбери действие в меню ниже 👇
"""

        await update.message.reply_text(
            welcome_text,
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )

    except Exception as e:
        logger.error(f"[BOT] Auth error: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка. Попробуйте позже.",
        )
# END_BLOCK: async start_command


# START_BLOCK: async help_command — handle /help, show usage instructions
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = """
🛡️ *KrotPN Bot - Справка*

*Доступные команды:*
/start - Главное меню
/config - Получить VPN конфигурацию
/status - Статус подписки
/plans - Тарифные планы
/referral - Реферальная программа
/support - Связаться с поддержкой

*Как подключить VPN:*
1. Скачайте приложение AmneziaWG
2. Получите конфиг через /config
3. Сканируйте QR-код или импортируйте файл
4. Подключайтесь!

*Нужна помощь?*
Пишите: @krtpn_support
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")
# END_BLOCK: async help_command


# START_BLOCK: async config_command — handle /config, deliver VPN config as downloadable file
async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /config command."""
    telegram_id = update.effective_user.id

    if telegram_id not in user_tokens:
        await update.message.reply_text(
            "❌ Сначала нажмите /start для авторизации.",
        )
        return

    try:
        config = await backend.get_vpn_config(user_tokens[telegram_id])

        # Send config as file
        config_text = config.get("config", "")
        if config_text:
            from io import BytesIO
            file = BytesIO(config_text.encode())
            file.name = f"krtpn-{telegram_id}.conf"

            await update.message.reply_document(
                document=file,
                filename=f"krtpn.conf",
                caption=f"""
📱 *Ваша VPN конфигурация*

📍 Сервер: {config.get('server_location', 'N/A')}
🌐 IP: {config.get('address', 'N/A')}

*Инструкция:*
1. Скачайте файл
2. Откройте AmneziaWG
3. Импортируйте файл
4. Подключайтесь!
""",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                "❌ Конфигурация не найдена. Возможно, у вас нет активной подписки.",
            )

    except Exception as e:
        logger.error(f"[BOT] Config error: {e}")
        await update.message.reply_text("❌ Ошибка получения конфигурации.")
# END_BLOCK: async config_command


# START_BLOCK: async status_command — handle /status, show subscription status
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    telegram_id = update.effective_user.id

    if telegram_id not in user_tokens:
        await update.message.reply_text("❌ Сначала нажмите /start для авторизации.")
        return

    try:
        sub = await backend.get_subscription(user_tokens[telegram_id])

        if sub.get("has_subscription"):
            status_emoji = "✅" if sub.get("is_active") else "❌"
            trial_text = " (Пробный период)" if sub.get("is_trial") else ""

            text = f"""
📊 *Статус подписки*

{status_emoji} *Статус:* {"Активна" if sub.get("is_active") else "Неактивна"}{trial_text}
📅 *План:* {sub.get("plan_name", "N/A")}
⏰ *Осталось дней:* {sub.get("days_left", 0)}
🔄 *Автопродление:* {"Включено" if sub.get("is_recurring") else "Выключено"}
"""
        else:
            text = """
📊 *Статус подписки*

❌ У вас нет активной подписки.

Нажмите /plans чтобы посмотреть тарифы.
"""

        await update.message.reply_text(text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"[BOT] Status error: {e}")
        await update.message.reply_text("❌ Ошибка получения статуса.")
# END_BLOCK: async status_command


# START_BLOCK: async plans_command — handle /plans, list available billing plans
async def plans_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /plans command."""
    try:
        plans = await backend.get_plans()

        if not plans:
            await update.message.reply_text("❌ Тарифы временно недоступны.")
            return

        text = "💰 *Тарифные планы*\n\n"

        for plan in plans:
            popular = " ⭐" if plan.get("is_popular") else ""
            text += f"""
*{plan['name']}{popular}*
💵 {plan['price']}₽ / {plan['duration_days']} дней
📝 {plan.get('description', '')}

"""

        text += "Для покупки перейдите на сайт: krtpn.com"

        await update.message.reply_text(text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"[BOT] Plans error: {e}")
        await update.message.reply_text("❌ Ошибка получения тарифов.")
# END_BLOCK: async plans_command


# START_BLOCK: async referral_command — handle /referral, show referral program info
async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /referral command."""
    telegram_id = update.effective_user.id

    if telegram_id not in user_tokens:
        await update.message.reply_text("❌ Сначала нажмите /start для авторизации.")
        return

    # For now, just show placeholder
    text = """
🎁 *Реферальная программа*

Пригласите друзей и получите бонусные дни подписки!

*Условия:*
• За каждого приглашенного друга — +7 дней
• Бонус зачисляется после первой оплаты друга
• Без ограничений по количеству приглашений

Ваша реферальная ссылка доступна в личном кабинете: krtpn.com/referrals
"""
    await update.message.reply_text(text, parse_mode="Markdown")
# END_BLOCK: async referral_command


# START_BLOCK: async button_callback — handle inline button callbacks, dispatch to command handlers
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "config":
        # Simulate /config command
        context.args = []
        await config_command(update, context)
    elif data == "subscription":
        await status_command(update, context)
    elif data == "plans":
        await plans_command(update, context)
    elif data == "referral":
        await referral_command(update, context)
# END_BLOCK: async button_callback


# START_BLOCK: def main — entry point, configure and run bot (webhook or polling)
def main():
    """Run the bot."""
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        return

    # Create application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("config", config_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("plans", plans_command))
    application.add_handler(CommandHandler("referral", referral_command))
    application.add_handler(MessageHandler(filters.CallbackQuery, button_callback))

    # Run bot
    if WEBHOOK_URL:
        # Webhook mode (for production)
        logger.info(f"[BOT] Starting webhook on {WEBHOOK_URL}")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
        )
    else:
        # Polling mode (for development)
        logger.info("[BOT] Starting polling...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
# END_BLOCK: def main


if __name__ == "__main__":
    main()

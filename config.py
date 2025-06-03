import os
from telethon import types as telethon_types

# Telegram API
TOKEN = os.getenv("TOKEN", "Ваш_Токен_Бота")  # Токен бота
CRYPTO = os.getenv("CRYPTO", "Ваш_Токен_CryptoPay")  # Токен для CryptoPay API
API_ID = os.getenv("API_ID", "24565698")  # ID API для Telethon
API_HASH = os.getenv("API_HASH", "5a084b434f8505ace703485b9da85040")  # Hash API для Telethon

# Информация о боте
bot_name = os.getenv("BOT_NAME", "BotNet")
bot_admin = os.getenv("BOT_ADMIN", "@username_admin")
bot_channel_link = os.getenv("BOT_CHANNEL_LINK", "https://t.me/channel")
bot_documentation = os.getenv("BOT_DOCUMENTATION", "https://t.me/docs")
bot_reviews = os.getenv("BOT_REVIEWS", "https://t.me/reviews")
bot_works = os.getenv("BOT_WORKS", "https://t.me/works")
bot_logs = int(os.getenv("BOT_LOGS", "-1001234567890"))  # ID канала для логов

# Администраторы
ADMINS_STR = os.getenv("ADMINS", "123456789,987654321")
ADMINS = [int(admin_id.strip()) for admin_id in ADMINS_STR.split(",") if admin_id.strip()]

# Цены подписок (в USD)
subscribe_1_day = float(os.getenv("SUBSCRIBE_1_DAY", "5"))
subscribe_7_days = float(os.getenv("SUBSCRIBE_7_DAYS", "20"))
subscribe_14_days = float(os.getenv("SUBSCRIBE_14_DAYS", "35"))
subscribe_30_days = float(os.getenv("SUBSCRIBE_30_DAYS", "50"))
subscribe_365_days = float(os.getenv("SUBSCRIBE_365_DAYS", "150"))
subscribe_infinity_days = float(os.getenv("SUBSCRIBE_INFINITY_DAYS", "300"))

# Настройки базы данных
DB_NAME = os.getenv("DB_NAME", "users.db")

# Папка с сессиями
SESSION_FOLDER = os.getenv("SESSION_FOLDER", "sessions")

# Типы жалоб (отчетов)
REPORT_REASONS = [
    telethon_types.InputReportReasonSpam(),
    telethon_types.InputReportReasonViolence(),
    telethon_types.InputReportReasonPornography(),
    telethon_types.InputReportReasonChildAbuse(),
    telethon_types.InputReportReasonIllegalDrugs(),
    telethon_types.InputReportReasonPersonalDetails(),
]

# Настройки задержки между жалобами
COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", "5"))  # Время ожидания между отправками жалоб

# Системная версия для Telegram клиента
SYSTEM_VERSION = os.getenv("SYSTEM_VERSION", "4.16.30-vxCUSTOM")

# Настройка по умолчанию для новых пользователей
DEFAULT_SUBSCRIBE_DATE = os.getenv("DEFAULT_SUBSCRIBE_DATE", "1999-01-01 20:00:00") 
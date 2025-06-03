"""
Конфигурационный файл бота
"""
import os
import logging
from datetime import datetime
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Базовые настройки бота
bot_token = os.getenv('BOT_TOKEN')
bot_name = "BotNet"
bot_admin = "@admin"  # Имя администратора
bot_logs = os.getenv('LOG_CHANNEL_ID')  # ID канала для логов
bot_channel_link = "https://t.me/botnet_channel"  # Ссылка на канал бота
bot_reviews = "https://t.me/botnet_reviews"  # Ссылка на отзывы
bot_works = "https://t.me/botnet_works"  # Ссылка на примеры работ
bot_documentation = "https://t.me/botnet_docs"  # Ссылка на документацию

# Админы и уровни доступа
ADMIN_LEVEL_OBSERVER = 1  # Наблюдатель (просмотр статистики)
ADMIN_LEVEL_MODERATOR = 2  # Модератор (выдача/отзыв подписок)
ADMIN_LEVEL_FULL = 3  # Полный админ (все функции)

# Словарь администраторов в формате {user_id: уровень_доступа}
ADMINS = {
    123456789: ADMIN_LEVEL_FULL,
    # Добавьте сюда ID администраторов и их уровни доступа
}

# Настройки базы данных
DB_NAME = "database.db"
DEFAULT_SUBSCRIBE_DATE = "2000-01-01 00:00:00"

# Настройки сессий
SESSION_FOLDER = "sessions"
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
SYSTEM_VERSION = os.getenv('SYSTEM_VERSION', 'Windows 10')

# Настройки API платежей
PAYMENT_TOKEN = os.getenv('PAYMENT_TOKEN')
PAYMENT_URL = os.getenv('PAYMENT_URL')
PAYMENT_API_KEY = os.getenv('PAYMENT_API_KEY')

# API ключи для разных платежных систем
CRYPTO_PAY_API_KEY = os.getenv('CRYPTO_PAY_API_KEY')
QIWI_API_KEY = os.getenv('QIWI_API_KEY')
YOOMONEY_API_KEY = os.getenv('YOOMONEY_API_KEY')
PAYPAL_CLIENT_ID = os.getenv('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.getenv('PAYPAL_SECRET')

# Настройки криптовалютных платежей
SUPPORTED_CRYPTO = {
    "USDT": {"name": "Tether USDT", "network": "TRC20", "enabled": True},
    "BTC": {"name": "Bitcoin", "enabled": True},
    "ETH": {"name": "Ethereum", "enabled": True},
    "TON": {"name": "Toncoin", "enabled": True},
    "BNB": {"name": "Binance Coin", "enabled": False}
}

# Настройки тарифных планов
SUBSCRIPTION_PLANS = {
    "basic": {
        "name": "Базовый",
        "description": "Доступ к основным функциям бота",
        "prices": {
            "1": 3,    # 1 день - $3
            "7": 15,   # 7 дней - $15
            "30": 45,  # 30 дней - $45
            "365": 350 # 365 дней - $350
        },
        "features": ["mass_reports"],
        "max_sessions_per_request": 50,
        "cooldown_minutes": 5
    },
    "premium": {
        "name": "Премиум",
        "description": "Расширенный доступ с приоритетной обработкой",
        "prices": {
            "1": 5,     # 1 день - $5
            "7": 25,    # 7 дней - $25
            "30": 70,   # 30 дней - $70
            "365": 500  # 365 дней - $500
        },
        "features": ["mass_reports", "priority_processing", "advanced_analytics"],
        "max_sessions_per_request": 100,
        "cooldown_minutes": 2
    },
    "vip": {
        "name": "VIP",
        "description": "Максимальный доступ ко всем функциям",
        "prices": {
            "1": 10,     # 1 день - $10
            "7": 50,     # 7 дней - $50
            "30": 150,   # 30 дней - $150
            "365": 1000, # 365 дней - $1000
            "lifetime": 2500  # Пожизненная подписка - $2500
        },
        "features": ["mass_reports", "priority_processing", "advanced_analytics", "custom_reporting", "api_access", "scheduled_tasks"],
        "max_sessions_per_request": 200,
        "cooldown_minutes": 0
    }
}

# Настройки реферальной системы
REFERRAL_SYSTEM = {
    "enabled": True,
    "reward_type": "subscription_days",  # subscription_days, discount, balance
    "first_level_reward": 3,    # 3 дня подписки за реферала первого уровня
    "second_level_reward": 1,   # 1 день подписки за реферала второго уровня
    "min_purchase_required": True,  # Требуется ли покупка для начисления вознаграждения
    "levels": 2  # Количество уровней в реферальной программе
}

# Настройки промокодов
PROMO_SYSTEM = {
    "enabled": True,
    "max_usage_per_code": 100,  # Максимальное использование одного промокода
    "max_discount_percent": 50, # Максимальная скидка в процентах
    "default_expiry_days": 30   # Срок действия промокода по умолчанию в днях
}

# Настройки планировщика задач
TASK_SCHEDULER = {
    "enabled": True,
    "max_tasks_per_user": {
        "basic": 3,      # Максимальное количество задач для базового плана
        "premium": 10,   # Максимальное количество задач для премиум плана
        "vip": 30        # Максимальное количество задач для VIP плана
    },
    "min_interval_minutes": {
        "basic": 60,     # Минимальный интервал между задачами для базового плана (1 час)
        "premium": 30,   # Минимальный интервал для премиум плана (30 минут)
        "vip": 5         # Минимальный интервал для VIP плана (5 минут)
    },
    "max_repeats": {
        "basic": 3,      # Максимальное количество повторений для базового плана
        "premium": 10,   # Максимальное количество повторений для премиум плана
        "vip": 0         # Неограниченное количество повторений для VIP плана (0 = без ограничений)
    }
}

# Настройки пользовательского интерфейса
UI_SETTINGS = {
    "theme": {
        "primary_color": "#2C3E50",
        "secondary_color": "#3498DB",
        "success_color": "#2ECC71",
        "warning_color": "#F39C12",
        "danger_color": "#E74C3C",
        "background_color": "#ECF0F1",
        "text_color": "#34495E"
    },
    "charts": {
        "enabled": True,
        "max_points": 100,      # Максимальное количество точек на графике
        "default_dpi": 100,     # Разрешение графиков по умолчанию
        "max_channels": 10      # Максимальное количество каналов для отображения в статистике
    },
    "welcome_messages": {
        "enabled": True,
        "show_features": True,  # Показывать возможности в приветственном сообщении
        "show_stats": True      # Показывать статистику в приветственном сообщении
    }
}

# Стоимость подписок (для обратной совместимости)
subscribe_1_day = SUBSCRIPTION_PLANS["basic"]["prices"]["1"]
subscribe_7_days = SUBSCRIPTION_PLANS["basic"]["prices"]["7"]
subscribe_14_days = 25  # Для обратной совместимости
subscribe_30_days = SUBSCRIPTION_PLANS["basic"]["prices"]["30"]
subscribe_365_days = SUBSCRIPTION_PLANS["basic"]["prices"]["365"]
subscribe_infinity_days = SUBSCRIPTION_PLANS["vip"]["prices"]["lifetime"]

# Причины жалоб
REPORT_REASONS = [
    "pornography",
    "spam",
    "copyright",
    "violence",
    "child_abuse",
    "illegal_drugs",
    "personal_details",
    "other"
]

# Соответствие причин жалоб и их названия
REPORT_REASON_NAMES = {
    "pornography": "Порнография",
    "spam": "Спам",
    "copyright": "Нарушение авторских прав",
    "violence": "Насилие",
    "child_abuse": "Детское насилие",
    "illegal_drugs": "Незаконные товары",
    "personal_details": "Личная информация",
    "other": "Другое"
}

# Настройки параллельной обработки жалоб
MAX_CONCURRENT_SESSIONS = 10      # Максимальное количество параллельных сессий на пользователя
PROGRESS_UPDATE_INTERVAL = 1.0    # Интервал обновления прогресса в секундах
REPORT_INTENSITY_LEVELS = {
    "max": 1.0,     # Максимальная интенсивность - все сессии
    "high": 0.75,   # Высокая интенсивность - 75% сессий
    "medium": 0.5,  # Средняя интенсивность - 50% сессий
    "low": 0.25     # Низкая интенсивность - 25% сессий
}

# Настройки кулдауна
COOLDOWN_MINUTES = 3

# Настройки логирования
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Время запуска бота (устанавливается в main.py)
START_TIME = datetime.now() 
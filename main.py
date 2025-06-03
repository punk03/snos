"""
Основной файл бота для массовой отправки жалоб на сообщения
"""
import os
import asyncio
import logging
from datetime import datetime

from dotenv import load_dotenv
from telebot.async_telebot import AsyncTeleBot

import config
from app.database.db import db
from app.handlers import register_user_handlers, register_admin_handlers

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Проверяем и создаем необходимые директории
os.makedirs("logs", exist_ok=True)
os.makedirs(config.SESSION_FOLDER, exist_ok=True)

# Устанавливаем время запуска
config.START_TIME = datetime.now()

async def main():
    """Основная функция запуска бота"""
    logger.info("Запуск бота...")

    # Инициализируем бота
    bot = AsyncTeleBot(config.bot_token)
    
    try:
        # Регистрируем обработчики команд
        await register_user_handlers(bot)
        await register_admin_handlers(bot)
        
        logger.info("Бот успешно запущен!")
        
        # Запускаем бота
        await bot.infinity_polling(timeout=10, long_polling_timeout=5)
        
    except Exception as e:
        logger.critical(f"Ошибка при запуске бота: {e}")
    finally:
        # Закрываем соединения с БД
        db.close()
        logger.info("Бот остановлен")

if __name__ == "__main__":
    # Запускаем асинхронное приложение
    asyncio.run(main()) 
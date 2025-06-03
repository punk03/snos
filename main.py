import logging
import time
import os
from dotenv import load_dotenv

import telebot

import config
from app.handlers import register_user_handlers, register_admin_handlers

# Загрузка переменных окружения (если есть .env файл)
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """
    Основная функция запуска бота
    """
    logger.info("Запуск бота...")
    
    # Проверяем наличие папки для сессий
    if not os.path.exists(config.SESSION_FOLDER):
        os.makedirs(config.SESSION_FOLDER)
        logger.info(f"Создана папка для сессий: {config.SESSION_FOLDER}")
    
    # Основной цикл бота с обработкой ошибок
    while True:
        try:
            # Инициализация бота
            bot = telebot.TeleBot(config.TOKEN)
            logger.info("Бот инициализирован")
            
            # Регистрация обработчиков
            register_user_handlers(bot)
            register_admin_handlers(bot)
            logger.info("Обработчики зарегистрированы")
            
            # Запуск бота
            logger.info("Бот запущен")
            bot.polling(none_stop=True, interval=0)
            
        except Exception as e:
            logger.error(f"Произошла ошибка при работе бота: {e}")
            time.sleep(3)
            logger.info("Перезапуск бота...")

if __name__ == "__main__":
    main() 
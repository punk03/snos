import os
import random
import asyncio
import logging
from typing import Tuple, Dict, List

from telethon import TelegramClient
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from telethon.tl.functions.messages import ReportRequest

import config
from app.keyboards import create_user_markup, create_back_button

# Настройка логирования
logger = logging.getLogger(__name__)

def extract_username_and_message_id(message_url: str) -> Tuple[str, int]:
    """
    Извлекает имя пользователя и ID сообщения из URL
    
    Args:
        message_url: URL сообщения в формате https://t.me/username/123
    
    Returns:
        Tuple[str, int]: (имя пользователя, ID сообщения)
    
    Raises:
        ValueError: Если URL неверного формата
    """
    if not message_url.startswith('https://t.me/'):
        raise ValueError("Неверная ссылка! Нужна ссылка на сообщение (https://t.me/XXX/YYY)")
    
    path = message_url[len('https://t.me/'):].split('/')
    if len(path) == 2:
        chat_username = path[0]
        try:
            message_id = int(path[1])
            return chat_username, message_id
        except ValueError:
            raise ValueError("Неверный формат ID сообщения")
    
    raise ValueError("Неверная ссылка! Нужна ссылка на сообщение (https://t.me/XXX/YYY)")

async def report_message(bot, chat_username: str, message_id: int, user_id: int) -> None:
    """
    Отправляет жалобы на сообщение с использованием всех доступных сессий
    
    Args:
        bot: Экземпляр телеграм бота
        chat_username: Имя пользователя или канала
        message_id: ID сообщения
        user_id: ID пользователя, который запросил отправку жалоб
    """
    sessions = [f.replace('.session', '') for f in os.listdir(config.SESSION_FOLDER) if f.endswith('.session')]
    
    if not sessions:
        bot.send_message(
            user_id, 
            "❌ *Нет доступных сессий для отправки жалоб!*", 
            parse_mode="Markdown", 
            reply_markup=create_back_button()
        )
        return
    
    valid = 0
    ne_valid = 0
    flood = 0
    
    for session_name in sessions:
        try:
            client = TelegramClient(
                f"./{config.SESSION_FOLDER}/{session_name}", 
                int(config.API_ID), 
                config.API_HASH, 
                system_version=config.SYSTEM_VERSION
            )
            
            random_reason = random.choice(config.REPORT_REASONS)
            
            await client.connect()
            
            if not await client.is_user_authorized():
                logger.warning(f"Сессия {session_name} не авторизована")
                ne_valid += 1
                await client.disconnect()
                continue

            await client.start()
            chat = await client.get_entity(chat_username)

            await client(ReportRequest(
                peer=chat,
                id=[message_id],
                reason=random_reason,
                message=""
            ))
            
            valid += 1
            logger.info(f"Жалоба успешно отправлена через сессию {session_name}")
            
        except FloodWaitError as e:
            flood += 1
            logger.warning(f'Flood wait error ({session_name}): {e}')
            
        except Exception as e:
            if "chat not found" in str(e):
                bot.send_message(
                    user_id, 
                    "❌ *Произошла ошибка при получении сообщения!*", 
                    parse_mode="Markdown", 
                    reply_markup=create_back_button()
                )
                logger.error(f"Ошибка при получении чата: {e}")
                return
                
            elif "object has no attribute 'from_id'" in str(e):
                bot.send_message(
                    user_id, 
                    "❌ *Произошла ошибка при получении сообщения!*", 
                    parse_mode="Markdown", 
                    reply_markup=create_back_button()
                )
                logger.error(f"Ошибка при получении сообщения: {e}")
                return
                
            else:
                ne_valid += 1
                logger.error(f'Ошибка при отправке жалобы ({session_name}): {e}')
                
        finally:
            try:
                await client.disconnect()
            except:
                pass
    
    # Отправляем результат пользователю
    bot.send_message(
        user_id, 
        f"🟩 *Жалобы успешно отправлены!*  \n\n🟢 *Валидные:* `{valid}`  \n🔴 *Не валидные:* `{ne_valid}`\n\n🌟 _Спасибо за вашу активность!_", 
        parse_mode="Markdown", 
        reply_markup=create_back_button()
    )
    
    # Отправляем информацию в лог-канал
    user_markup = create_user_markup(user_id)
    bot.send_message(
        config.bot_logs, 
        f"⚡️ *Произошел запуск бота:*\n\n*ID:* `{user_id}`\n*Ссылка: https://t.me/{chat_username}/{message_id}*\n\n🔔 *Информация о сессиях:*\n⚡️ Валидные: *{valid}*\n⚡️ *Не валидные: {ne_valid}*\n⚡️ *FloodError: {flood}*", 
        parse_mode="Markdown", 
        disable_web_page_preview=True, 
        reply_markup=user_markup
    ) 
import logging
from abc import ABC, abstractmethod
import json
from typing import Any, Dict, Optional, List, Union, Callable

from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message, CallbackQuery

from app.database.db import db
from app.utils.validators import sanitize_input

logger = logging.getLogger(__name__)

class BaseHandler(ABC):
    """Базовый класс для обработчиков команд и сообщений"""
    
    def __init__(self, bot: AsyncTeleBot):
        """
        Инициализация базового обработчика
        
        Args:
            bot: Экземпляр бота
        """
        self.bot = bot
    
    @abstractmethod
    async def register_handlers(self):
        """
        Регистрация обработчиков
        
        Этот метод должен быть реализован в каждом наследнике
        """
        pass
    
    async def check_user(self, user_id: int, message: Optional[Message] = None) -> bool:
        """
        Проверка существования пользователя и обновление активности
        
        Args:
            user_id: ID пользователя
            message: Объект сообщения (опционально)
            
        Returns:
            bool: Существует ли пользователь
        """
        # Проверяем существование пользователя
        exists = db.user_exists(user_id)
        
        if exists:
            # Обновляем время активности
            db.update_user_activity(
                user_id=user_id,
                update_info=message is not None,
                message=message
            )
            return True
        
        # Если пользователя нет в базе и есть сообщение,
        # добавляем его с информацией из сообщения
        if message and message.from_user:
            from_user = message.from_user
            db.add_user(
                user_id=user_id,
                username=from_user.username,
                first_name=from_user.first_name,
                last_name=from_user.last_name,
                language_code=from_user.language_code,
                is_bot=from_user.is_bot
            )
            return True
        
        # Если нет информации о пользователе, добавляем только ID
        db.add_user(user_id=user_id)
        return True
    
    async def log_command(self, user_id: int, command: str, params: Optional[str] = None) -> None:
        """
        Логирование выполнения команды
        
        Args:
            user_id: ID пользователя
            command: Название команды
            params: Параметры команды (опционально)
        """
        db.log_operation(
            user_id=user_id,
            operation_type="command",
            target=command,
            params=params
        )
    
    async def log_callback(self, user_id: int, callback_data: str) -> None:
        """
        Логирование вызова callback
        
        Args:
            user_id: ID пользователя
            callback_data: Данные callback
        """
        db.log_operation(
            user_id=user_id,
            operation_type="callback",
            target=callback_data
        )
    
    async def safe_send_message(self, chat_id: int, text: str, **kwargs) -> Optional[Message]:
        """
        Безопасная отправка сообщения с обработкой ошибок
        
        Args:
            chat_id: ID чата
            text: Текст сообщения
            **kwargs: Дополнительные параметры для отправки
            
        Returns:
            Optional[Message]: Отправленное сообщение или None
        """
        try:
            # Проверяем размер сообщения
            if len(text) > 4096:
                # Если сообщение слишком большое, разбиваем его на части
                parts = []
                for i in range(0, len(text), 4000):
                    parts.append(text[i:i+4000])
                
                # Отправляем первую часть с заданными параметрами
                first_msg = await self.bot.send_message(
                    chat_id=chat_id,
                    text=parts[0],
                    **kwargs
                )
                
                # Отправляем остальные части без дополнительных параметров
                for part in parts[1:]:
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=part
                    )
                    
                return first_msg
            
            # Отправляем обычное сообщение
            return await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения пользователю {chat_id}: {e}")
            return None
    
    async def safe_edit_message(self, chat_id: int, message_id: int, text: str, **kwargs) -> bool:
        """
        Безопасное редактирование сообщения с обработкой ошибок
        
        Args:
            chat_id: ID чата
            message_id: ID сообщения
            text: Новый текст
            **kwargs: Дополнительные параметры
            
        Returns:
            bool: Успешность операции
        """
        try:
            # Проверяем, что текст не слишком большой
            if len(text) > 4096:
                text = text[:4093] + "..."
                
            await self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                **kwargs
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения {message_id} в чате {chat_id}: {e}")
            return False
    
    async def process_callback(self, call: CallbackQuery, handlers: Dict[str, Callable]) -> None:
        """
        Обработка callback-запроса
        
        Args:
            call: Объект callback
            handlers: Словарь обработчиков {callback_prefix: handler_func}
        """
        if not call.data:
            return
            
        # Логируем callback
        await self.log_callback(call.from_user.id, call.data)
        
        # Проверяем пользователя
        await self.check_user(call.from_user.id)
        
        # Ищем обработчик для данного callback
        for prefix, handler in handlers.items():
            if call.data.startswith(prefix):
                try:
                    await handler(call)
                    # Отвечаем на callback, чтобы убрать индикатор загрузки
                    await self.bot.answer_callback_query(call.id)
                    return
                except Exception as e:
                    logger.error(f"Ошибка при обработке callback {call.data}: {e}")
                    await self.bot.answer_callback_query(
                        call.id,
                        text="Произошла ошибка при обработке запроса"
                    )
                    return
        
        # Если обработчик не найден
        await self.bot.answer_callback_query(
            call.id,
            text="Неизвестный запрос"
        )

    async def is_admin(self, user_id: int, min_level: int = 1) -> bool:
        """
        Проверка, является ли пользователь администратором
        
        Args:
            user_id: ID пользователя
            min_level: Минимальный уровень доступа
            
        Returns:
            bool: Является ли пользователь администратором с нужным уровнем
        """
        from config import ADMINS
        
        # Проверяем наличие пользователя в списке администраторов
        admin_level = ADMINS.get(user_id, 0)
        
        # Проверяем уровень доступа
        return admin_level >= min_level 
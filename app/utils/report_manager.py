"""
Менеджер для улучшенной отправки жалоб с асинхронной обработкой и прогресс-индикатором
"""
import os
import logging
import asyncio
import random
import json
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any, Set, Callable, Union

from telethon import TelegramClient
from telethon.errors import FloodWaitError, SessionPasswordNeededError, PhoneNumberInvalidError
from telethon.tl.functions.messages import ReportRequest
from telebot.async_telebot import AsyncTeleBot

import config
from app.utils.validators import validate_message_url
from app.utils.session_manager import session_manager
from app.database.db import db
from app.utils.localization import i18n

logger = logging.getLogger(__name__)

class ReportProgressCallback:
    """Класс для отслеживания прогресса отправки жалоб"""
    
    def __init__(self, total_sessions: int, bot: AsyncTeleBot, chat_id: int, message_id: int, lang: str):
        """
        Инициализация колбэка прогресса
        
        Args:
            total_sessions: Общее количество сессий
            bot: Экземпляр бота
            chat_id: ID чата для обновления прогресса
            message_id: ID сообщения для обновления
            lang: Код языка пользователя
        """
        self.total = total_sessions
        self.processed = 0
        self.valid = 0
        self.invalid = 0
        self.flood = 0
        self.bot = bot
        self.chat_id = chat_id
        self.message_id = message_id
        self.lang = lang
        self.last_update = datetime.now()
        self.update_interval = config.PROGRESS_UPDATE_INTERVAL
        self.is_active = True
        self.lock = asyncio.Lock()
    
    async def update(self, result_type: str) -> None:
        """
        Обновление прогресса
        
        Args:
            result_type: Тип результата (valid, invalid, flood)
        """
        async with self.lock:
            self.processed += 1
            
            if result_type == "valid":
                self.valid += 1
            elif result_type == "invalid":
                self.invalid += 1
            elif result_type == "flood":
                self.flood += 1
                
            # Обновляем прогресс не чаще, чем раз в интервал
            if (datetime.now() - self.last_update).total_seconds() >= self.update_interval:
                await self.update_progress()
                self.last_update = datetime.now()
    
    async def update_progress(self) -> None:
        """Обновление сообщения с прогрессом"""
        if not self.is_active:
            return
            
        percent = int(self.processed / self.total * 100) if self.total > 0 else 0
        progress_bar = self.get_progress_bar(percent)
        
        try:
            await self.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=self.message_id,
                text=f"⏳ *{i18n.get_text('botnet_processing', self.lang)}*\n\n"
                     f"{progress_bar} {percent}%\n\n"
                     f"🟢 *{i18n.get_text('active_subscribe', self.lang)}:* `{self.valid}`\n"
                     f"🔴 *{i18n.get_text('inactive_subscribe', self.lang)}:* `{self.invalid}`\n"
                     f"🟡 *FloodError:* `{self.flood}`\n\n"
                     f"_Обработано {self.processed} из {self.total}_",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ошибка при обновлении прогресса: {e}")
    
    def get_progress_bar(self, percent: int) -> str:
        """
        Создание визуального прогресс-бара
        
        Args:
            percent: Процент выполнения
            
        Returns:
            str: Строка с прогресс-баром
        """
        filled = int(percent / 10)
        return "▓" * filled + "░" * (10 - filled)
    
    async def finalize(self) -> Dict[str, int]:
        """
        Завершение процесса и возврат итоговой статистики
        
        Returns:
            Dict[str, int]: Статистика результатов
        """
        self.is_active = False
        await self.update_progress()
        return {
            "valid": self.valid,
            "invalid": self.invalid,
            "flood": self.flood,
            "total": self.processed
        }

class ReportManager:
    """Менеджер для улучшенной отправки жалоб"""
    
    def __init__(self):
        """Инициализация менеджера отправки жалоб"""
        self.active_tasks = {}  # user_id -> task
        self._task_lock = asyncio.Lock()
        self.max_concurrent_sessions = config.MAX_CONCURRENT_SESSIONS
    
    async def report_message(
        self, 
        message_url: str, 
        user_id: int, 
        bot: AsyncTeleBot, 
        message_id: int,
        report_reason: str = None,
        max_sessions: int = None
    ) -> Dict[str, int]:
        """
        Отправка жалоб на сообщение с улучшенной обработкой
        
        Args:
            message_url: URL сообщения в формате https://t.me/username/123
            user_id: ID пользователя, инициировавшего операцию
            bot: Экземпляр бота для обновления прогресса
            message_id: ID сообщения с прогрессом
            report_reason: Причина жалобы (если не указана, выбирается случайная)
            max_sessions: Максимальное количество сессий для использования
            
        Returns:
            Dict[str, int]: Статистика результатов (valid, invalid, flood, total)
        """
        # Проверяем, есть ли уже активная задача для этого пользователя
        async with self._task_lock:
            if user_id in self.active_tasks:
                # Если задача существует и не завершена, отменяем запрос
                if not self.active_tasks[user_id].done():
                    logger.warning(f"Пользователь {user_id} уже запустил отправку жалоб")
                    return {"error": "already_running"}
            
        # Валидация URL сообщения
        is_valid, message_info = validate_message_url(message_url)
        if not is_valid or message_info is None:
            logger.warning(f"Некорректный URL сообщения: {message_url}")
            return {"valid": 0, "invalid": 0, "flood": 0, "total": 0, "error": "invalid_url"}
        
        chat_username, message_id_target = message_info
        
        # Получаем список валидных сессий
        valid_sessions = await session_manager.get_valid_sessions()
        
        if not valid_sessions:
            logger.warning("Нет доступных валидных сессий для отправки жалоб")
            return {"valid": 0, "invalid": 0, "flood": 0, "total": 0, "error": "no_sessions"}
        
        # Если указано ограничение на количество сессий
        if max_sessions and max_sessions > 0 and max_sessions < len(valid_sessions):
            # Перемешиваем и ограничиваем количество сессий
            random.shuffle(valid_sessions)
            valid_sessions = valid_sessions[:max_sessions]
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Создаем объект для отслеживания прогресса
        progress = ReportProgressCallback(
            total_sessions=len(valid_sessions),
            bot=bot,
            chat_id=user_id,
            message_id=message_id,
            lang=lang
        )
        
        # Формируем имя причины для логирования
        reason_name = "random"
        if report_reason:
            reason_name = config.REPORT_REASON_NAMES.get(report_reason, report_reason)
        
        # Логируем операцию начала отправки жалоб
        db.log_operation(
            user_id=user_id,
            operation_type="report",
            target=message_url,
            params=json.dumps({
                "chat": chat_username,
                "message_id": message_id_target,
                "sessions_count": len(valid_sessions),
                "reason": reason_name,
                "max_sessions": max_sessions
            })
        )
        
        # Создаем и запускаем задачу
        task = asyncio.create_task(
            self._process_report_task(
                valid_sessions=valid_sessions,
                chat_username=chat_username,
                message_id=message_id_target,
                progress=progress,
                report_reason=report_reason
            )
        )
        
        # Сохраняем задачу
        async with self._task_lock:
            self.active_tasks[user_id] = task
        
        # Ожидаем завершения и получаем результаты
        try:
            stats = await task
            
            # Обновляем статистику операции
            db.log_operation(
                user_id=user_id,
                operation_type="report_result",
                target=message_url,
                result=json.dumps(stats)
            )
            
            # Удаляем задачу из активных
            async with self._task_lock:
                if user_id in self.active_tasks:
                    self.active_tasks.pop(user_id)
            
            return stats
            
        except asyncio.CancelledError:
            logger.warning(f"Задача отправки жалоб отменена для пользователя {user_id}")
            
            # Обновляем статистику операции
            db.log_operation(
                user_id=user_id,
                operation_type="report_cancelled",
                target=message_url
            )
            
            # Удаляем задачу из активных
            async with self._task_lock:
                if user_id in self.active_tasks:
                    self.active_tasks.pop(user_id)
            
            return {"valid": 0, "invalid": 0, "flood": 0, "total": 0, "error": "cancelled"}
        except Exception as e:
            logger.error(f"Ошибка при выполнении задачи отправки жалоб: {e}")
            
            # Обновляем статистику операции
            db.log_operation(
                user_id=user_id,
                operation_type="report_error",
                target=message_url,
                params=json.dumps({"error": str(e)})
            )
            
            # Удаляем задачу из активных
            async with self._task_lock:
                if user_id in self.active_tasks:
                    self.active_tasks.pop(user_id)
            
            return {"valid": 0, "invalid": 0, "flood": 0, "total": 0, "error": "unknown_error"}
    
    async def _process_report_task(
        self,
        valid_sessions: List[str],
        chat_username: str,
        message_id: int,
        progress: ReportProgressCallback,
        report_reason: str = None
    ) -> Dict[str, int]:
        """
        Обработка задачи отправки жалоб с использованием асинхронности
        
        Args:
            valid_sessions: Список валидных сессий
            chat_username: Имя пользователя или канала
            message_id: ID сообщения
            progress: Объект для отслеживания прогресса
            report_reason: Причина жалобы (если не указана, выбирается случайная)
            
        Returns:
            Dict[str, int]: Статистика результатов
        """
        # Создаем семафор для ограничения параллельных задач
        semaphore = asyncio.Semaphore(self.max_concurrent_sessions)
        
        # Создаем список задач
        tasks = []
        
        # Создаем задачи для каждой сессии
        for session in valid_sessions:
            task = asyncio.create_task(
                self._report_with_session(
                    session=session,
                    chat_username=chat_username,
                    message_id=message_id,
                    progress=progress,
                    semaphore=semaphore,
                    report_reason=report_reason
                )
            )
            tasks.append(task)
        
        try:
            # Ожидаем завершения всех задач
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Ошибка при выполнении задач отправки жалоб: {e}")
        
        # Получаем итоговую статистику
        stats = await progress.finalize()
        return stats
    
    async def _report_with_session(
        self,
        session: str,
        chat_username: str,
        message_id: int,
        progress: ReportProgressCallback,
        semaphore: asyncio.Semaphore,
        report_reason: str = None
    ) -> None:
        """
        Отправка жалобы через одну сессию
        
        Args:
            session: Имя сессии
            chat_username: Имя пользователя или канала
            message_id: ID сообщения
            progress: Объект для отслеживания прогресса
            semaphore: Семафор для ограничения параллельных задач
            report_reason: Причина жалобы
        """
        client = None
        
        async with semaphore:
            try:
                # Создаем клиент и подключаемся
                client = TelegramClient(
                    f"./{session_manager.session_folder}/{session}", 
                    int(config.API_ID), 
                    config.API_HASH, 
                    system_version=config.SYSTEM_VERSION
                )
                
                # Выбираем причину жалобы
                if not report_reason:
                    reason = random.choice(config.REPORT_REASONS)
                else:
                    reason = report_reason
                
                await client.connect()
                
                # Проверяем авторизацию
                if not await client.is_user_authorized():
                    logger.info(f"Сессия {session} недействительна")
                    await progress.update("invalid")
                    await client.disconnect()
                    await session_manager.mark_session_invalid(session)
                    return
                    
                # Отправляем жалобу
                await client.start()
                chat = await client.get_entity(chat_username)
                
                await client(ReportRequest(
                    peer=chat,
                    id=[message_id],
                    reason=reason,
                    message=""
                ))
                
                await progress.update("valid")
                # Обновляем время последнего использования
                await session_manager.update_session_usage(session)
                await client.disconnect()
                
            except FloodWaitError as e:
                await progress.update("flood")
                logger.warning(f'Flood wait error ({session}): {e}')
                await session_manager.mark_session_flood(session, e.seconds)
                
                if client:
                    try:
                        await client.disconnect()
                    except:
                        pass
                
            except Exception as e:
                logger.error(f'Ошибка сессии {session}: {e}')
                await progress.update("invalid")
                await session_manager.increment_session_error(session)
                
                if client:
                    try:
                        await client.disconnect()
                    except:
                        pass
    
    async def cancel_report(self, user_id: int) -> bool:
        """
        Отмена текущей задачи отправки жалоб
        
        Args:
            user_id: ID пользователя
            
        Returns:
            bool: Успешность отмены
        """
        async with self._task_lock:
            if user_id in self.active_tasks and not self.active_tasks[user_id].done():
                # Отменяем задачу
                self.active_tasks[user_id].cancel()
                logger.info(f"Отменена задача отправки жалоб для пользователя {user_id}")
                return True
        
        return False
    
    async def get_active_tasks_count(self) -> int:
        """
        Получение количества активных задач
        
        Returns:
            int: Количество активных задач
        """
        count = 0
        
        async with self._task_lock:
            for task in self.active_tasks.values():
                if not task.done():
                    count += 1
        
        return count

# Создаем экземпляр для удобного импорта
report_manager = ReportManager() 
import os
import logging
import asyncio
import random
import json
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any, Set

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError, PhoneNumberInvalidError
from telethon.tl.functions.messages import ReportRequest

import config
from app.utils.validators import validate_message_url
from app.database.db import db

logger = logging.getLogger(__name__)

class SessionManager:
    """Менеджер сессий для работы с Telegram API"""
    
    def __init__(self, session_folder: str = None):
        """
        Инициализация менеджера сессий
        
        Args:
            session_folder: Папка с сессиями
        """
        self.session_folder = session_folder or config.SESSION_FOLDER
        self._sessions_cache = {}
        self._last_used = {}
        self._session_lock = asyncio.Lock()
        
    def get_sessions_list(self) -> List[str]:
        """
        Получение списка доступных сессий
        
        Returns:
            List[str]: Список имен сессий
        """
        if not os.path.exists(self.session_folder):
            logger.warning(f"Папка с сессиями не существует: {self.session_folder}")
            try:
                os.makedirs(self.session_folder)
                logger.info(f"Создана папка для сессий: {self.session_folder}")
            except Exception as e:
                logger.error(f"Ошибка при создании папки для сессий: {e}")
                return []
                
        return [f.replace('.session', '') for f in os.listdir(self.session_folder) if f.endswith('.session')]
        
    async def report_message(self, message_url: str, user_id: int) -> Dict[str, int]:
        """
        Отправка жалоб на сообщение через все доступные сессии
        
        Args:
            message_url: URL сообщения в формате https://t.me/username/123
            user_id: ID пользователя, инициировавшего операцию
            
        Returns:
            Dict[str, int]: Статистика результатов (valid, invalid, flood)
        """
        # Валидация URL сообщения
        is_valid, message_info = validate_message_url(message_url)
        if not is_valid or message_info is None:
            logger.warning(f"Некорректный URL сообщения: {message_url}")
            return {"valid": 0, "invalid": 0, "flood": 0}
            
        chat_username, message_id = message_info
        
        # Получаем список валидных сессий
        valid_sessions = await self.get_valid_sessions()
        
        if not valid_sessions:
            logger.warning("Нет доступных валидных сессий для отправки жалоб")
            return {"valid": 0, "invalid": 0, "flood": 0}
            
        stats = {"valid": 0, "invalid": 0, "flood": 0}
        
        # Логируем операцию
        db.log_operation(
            user_id=user_id,
            operation_type="report",
            target=message_url,
            params=json.dumps({
                "chat": chat_username,
                "message_id": message_id,
                "sessions_count": len(valid_sessions)
            })
        )
        
        async with self._session_lock:
            for session in valid_sessions:
                try:
                    # Создаем клиент и подключаемся
                    client = TelegramClient(
                        f"./{self.session_folder}/{session}", 
                        int(config.API_ID), 
                        config.API_HASH, 
                        system_version=config.SYSTEM_VERSION
                    )
                    
                    random_reason = random.choice(config.REPORT_REASONS)
                    
                    await client.connect()
                    
                    # Проверяем авторизацию
                    if not await client.is_user_authorized():
                        logger.info(f"Сессия {session} недействительна")
                        stats["invalid"] += 1
                        await client.disconnect()
                        await self.mark_session_invalid(session)
                        continue
                        
                    # Отправляем жалобу
                    await client.start()
                    chat = await client.get_entity(chat_username)
                    
                    await client(ReportRequest(
                        peer=chat,
                        id=[message_id],
                        reason=random_reason,
                        message=""
                    ))
                    
                    stats["valid"] += 1
                    # Обновляем время последнего использования
                    await self.update_session_usage(session)
                    await client.disconnect()
                    
                except FloodWaitError as e:
                    stats["flood"] += 1
                    logger.warning(f'Flood wait error ({session}): {e}')
                    await self.mark_session_flood(session, e.seconds)
                    await client.disconnect()
                    
                except Exception as e:
                    if "chat not found" in str(e) or "object has no attribute 'from_id'" in str(e):
                        logger.error(f"Ошибка при получении сообщения: {e}")
                        await client.disconnect()
                        return stats
                        
                    stats["invalid"] += 1
                    logger.error(f'Ошибка сессии {session}: {e}')
                    await self.increment_session_error(session)
                    
                    try:
                        await client.disconnect()
                    except:
                        pass
        
        # Обновляем статистику операции
        db.log_operation(
            user_id=user_id,
            operation_type="report_result",
            target=message_url,
            result=json.dumps(stats)
        )
            
        return stats
        
    async def validate_sessions(self) -> Tuple[List[str], List[str]]:
        """
        Проверка валидности всех сессий
        
        Returns:
            Tuple[List[str], List[str]]: (валидные сессии, невалидные сессии)
        """
        valid_sessions = []
        invalid_sessions = []
        sessions = self.get_sessions_list()
        
        for session in sessions:
            try:
                client = TelegramClient(
                    f"./{self.session_folder}/{session}", 
                    int(config.API_ID), 
                    config.API_HASH,
                    system_version=config.SYSTEM_VERSION
                )
                
                await client.connect()
                
                if await client.is_user_authorized():
                    valid_sessions.append(session)
                    await self.mark_session_valid(session)
                else:
                    invalid_sessions.append(session)
                    await self.mark_session_invalid(session)
                    
                await client.disconnect()
                
            except Exception as e:
                logger.error(f"Ошибка при проверке сессии {session}: {e}")
                invalid_sessions.append(session)
                await self.mark_session_invalid(session)
        
        return valid_sessions, invalid_sessions

    async def get_valid_sessions(self) -> List[str]:
        """
        Получение списка валидных сессий
        
        Returns:
            List[str]: Список валидных сессий
        """
        conn = db.pool.get_connection()
        if not conn:
            return self.get_sessions_list()  # Если нет соединения с БД, возвращаем все сессии
            
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT session_id FROM sessions 
                WHERE is_valid = 1
                ORDER BY last_used ASC
                """
            )
            
            results = cursor.fetchall()
            if results:
                return [row['session_id'] for row in results]
            
            # Если в БД нет записей, запускаем валидацию и возвращаем результат
            valid, _ = await self.validate_sessions()
            return valid
        
        except Exception as e:
            logger.error(f"Ошибка при получении валидных сессий: {e}")
            return self.get_sessions_list()
        finally:
            db.pool.release_connection(conn)

    async def mark_session_valid(self, session_id: str) -> bool:
        """
        Отметка сессии как валидной
        
        Args:
            session_id: ID сессии
            
        Returns:
            bool: Успешность операции
        """
        conn = db.pool.get_connection()
        if not conn:
            return False
            
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO sessions 
                (session_id, is_valid, last_check, error_count)
                VALUES (?, 1, CURRENT_TIMESTAMP, 0)
                """,
                (session_id,)
            )
            conn.commit()
            return True
        
        except Exception as e:
            logger.error(f"Ошибка при отметке сессии {session_id} как валидной: {e}")
            return False
        finally:
            db.pool.release_connection(conn)

    async def mark_session_invalid(self, session_id: str) -> bool:
        """
        Отметка сессии как невалидной
        
        Args:
            session_id: ID сессии
            
        Returns:
            bool: Успешность операции
        """
        conn = db.pool.get_connection()
        if not conn:
            return False
            
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO sessions 
                (session_id, is_valid, last_check, notes)
                VALUES (?, 0, CURRENT_TIMESTAMP, 'Недействительная сессия')
                """,
                (session_id,)
            )
            conn.commit()
            return True
        
        except Exception as e:
            logger.error(f"Ошибка при отметке сессии {session_id} как невалидной: {e}")
            return False
        finally:
            db.pool.release_connection(conn)

    async def update_session_usage(self, session_id: str) -> bool:
        """
        Обновление времени последнего использования сессии
        
        Args:
            session_id: ID сессии
            
        Returns:
            bool: Успешность операции
        """
        conn = db.pool.get_connection()
        if not conn:
            return False
            
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE sessions 
                SET last_used = CURRENT_TIMESTAMP
                WHERE session_id = ?
                """,
                (session_id,)
            )
            conn.commit()
            return True
        
        except Exception as e:
            logger.error(f"Ошибка при обновлении времени использования сессии {session_id}: {e}")
            return False
        finally:
            db.pool.release_connection(conn)

    async def mark_session_flood(self, session_id: str, seconds: int) -> bool:
        """
        Отметка сессии с ошибкой флуда
        
        Args:
            session_id: ID сессии
            seconds: Количество секунд ожидания
            
        Returns:
            bool: Успешность операции
        """
        conn = db.pool.get_connection()
        if not conn:
            return False
            
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO sessions 
                (session_id, is_valid, last_check, notes)
                VALUES (?, 0, CURRENT_TIMESTAMP, ?)
                """,
                (session_id, f"Flood Wait: {seconds} seconds")
            )
            conn.commit()
            return True
        
        except Exception as e:
            logger.error(f"Ошибка при отметке сессии {session_id} с флудом: {e}")
            return False
        finally:
            db.pool.release_connection(conn)

    async def increment_session_error(self, session_id: str) -> bool:
        """
        Увеличение счетчика ошибок сессии
        
        Args:
            session_id: ID сессии
            
        Returns:
            bool: Успешность операции
        """
        conn = db.pool.get_connection()
        if not conn:
            return False
            
        try:
            cursor = conn.cursor()
            
            # Получаем текущее количество ошибок
            cursor.execute(
                "SELECT error_count FROM sessions WHERE session_id = ?",
                (session_id,)
            )
            result = cursor.fetchone()
            
            error_count = 1
            if result:
                error_count = result['error_count'] + 1
                
            # Обновляем количество ошибок
            cursor.execute(
                """
                INSERT OR REPLACE INTO sessions 
                (session_id, is_valid, last_check, error_count, notes)
                VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?)
                """,
                (session_id, 1 if error_count < 5 else 0, error_count, 
                 f"Ошибок: {error_count}" if error_count < 5 else "Слишком много ошибок")
            )
            conn.commit()
            return True
        
        except Exception as e:
            logger.error(f"Ошибка при увеличении счетчика ошибок сессии {session_id}: {e}")
            return False
        finally:
            db.pool.release_connection(conn)

    async def get_sessions_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Получение статуса всех сессий
        
        Returns:
            Dict[str, Dict[str, Any]]: Статус сессий
        """
        conn = db.pool.get_connection()
        if not conn:
            return {}
            
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions")
            results = cursor.fetchall()
            
            sessions_status = {}
            for row in results:
                sessions_status[row['session_id']] = dict(row)
                
            return sessions_status
        
        except Exception as e:
            logger.error(f"Ошибка при получении статуса сессий: {e}")
            return {}
        finally:
            db.pool.release_connection(conn)

    async def check_all_sessions(self) -> Dict[str, int]:
        """
        Проверка статуса всех сессий и обновление информации в БД
        
        Returns:
            Dict[str, int]: Статистика проверки (valid, invalid, total)
        """
        valid, invalid = await self.validate_sessions()
        
        return {
            "valid": len(valid),
            "invalid": len(invalid),
            "total": len(valid) + len(invalid)
        }

# Создаем экземпляр менеджера сессий для использования в других модулях
session_manager = SessionManager() 
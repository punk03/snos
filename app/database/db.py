import sqlite3
from datetime import datetime
import logging
from typing import Optional, List, Tuple, Any

from config import DB_NAME, DEFAULT_SUBSCRIBE_DATE

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

class DatabaseManager:
    def __init__(self, db_name: str = DB_NAME):
        self.db_name = db_name
        self._create_tables()
    
    def _create_tables(self):
        """Создание необходимых таблиц, если они не существуют"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users(
                    user_id INTEGER PRIMARY KEY,
                    subscribe DATETIME
                )
            """)
            conn.commit()
    
    def _get_connection(self):
        """Получение соединения с базой данных"""
        try:
            conn = sqlite3.connect(self.db_name)
            return conn
        except sqlite3.Error as e:
            logger.error(f"Ошибка соединения с базой данных: {e}")
            raise
    
    def add_user(self, user_id: int) -> bool:
        """Добавление нового пользователя в базу данных"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR IGNORE INTO users VALUES(?, ?)",
                    (user_id, DEFAULT_SUBSCRIBE_DATE)
                )
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Ошибка при добавлении пользователя {user_id}: {e}")
            return False
    
    def get_user(self, user_id: int) -> Optional[Tuple[int, str]]:
        """Получение данных пользователя по ID"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                return cursor.fetchone()
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении пользователя {user_id}: {e}")
            return None
    
    def user_exists(self, user_id: int) -> bool:
        """Проверка существования пользователя в базе данных"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
                return cursor.fetchone() is not None
        except sqlite3.Error as e:
            logger.error(f"Ошибка при проверке пользователя {user_id}: {e}")
            return False
    
    def update_subscription(self, user_id: int, new_date: str) -> bool:
        """Обновление даты подписки пользователя"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET subscribe = ? WHERE user_id = ?",
                    (new_date, user_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Ошибка при обновлении подписки пользователя {user_id}: {e}")
            return False
    
    def get_all_users(self) -> List[Tuple[int]]:
        """Получение списка всех пользователей"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM users")
                return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении списка пользователей: {e}")
            return []
    
    def get_subscription_date(self, user_id: int) -> Optional[str]:
        """Получение даты подписки пользователя"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT subscribe FROM users WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                return result[0] if result else None
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении даты подписки пользователя {user_id}: {e}")
            return None

# Создаем экземпляр для использования в других модулях
db = DatabaseManager() 
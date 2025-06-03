import sqlite3
import os
import threading
from datetime import datetime
import logging
from typing import Optional, List, Tuple, Dict, Any, Union
import queue

from config import DB_NAME, DEFAULT_SUBSCRIBE_DATE

# Настройка логирования
logger = logging.getLogger(__name__)

# Версия схемы базы данных
SCHEMA_VERSION = 4

class ConnectionPool:
    """Пул соединений с базой данных для оптимизации работы"""
    
    def __init__(self, db_path: str, max_connections: int = 5):
        """
        Инициализация пула соединений
        
        Args:
            db_path: Путь к файлу базы данных
            max_connections: Максимальное количество соединений в пуле
        """
        self.db_path = db_path
        self.max_connections = max_connections
        self.connection_queue = queue.Queue(maxsize=max_connections)
        self.active_connections = 0
        self._lock = threading.RLock()
        
        # Предварительное создание соединений
        for _ in range(max_connections // 2):  # Создаем половину пула заранее
            self._create_connection()
    
    def _create_connection(self) -> Optional[sqlite3.Connection]:
        """Создание нового соединения с БД"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Возвращать строки как словари
            
            # Включаем внешние ключи
            conn.execute("PRAGMA foreign_keys = ON")
            
            # Увеличиваем счетчик активных соединений
            with self._lock:
                self.active_connections += 1
                
            # Добавляем соединение в очередь
            self.connection_queue.put(conn)
            return conn
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при создании соединения с БД: {e}")
            return None
    
    def get_connection(self) -> Optional[sqlite3.Connection]:
        """Получение соединения из пула"""
        try:
            # Пробуем получить соединение из очереди без блокировки
            conn = self.connection_queue.get(block=False)
            return conn
        except queue.Empty:
            # Если очередь пуста, проверяем, можно ли создать новое соединение
            with self._lock:
                if self.active_connections < self.max_connections:
                    return self._create_connection()
                else:
                    # Если достигнут лимит соединений, ждем освобождения
                    try:
                        conn = self.connection_queue.get(block=True, timeout=5)
                        return conn
                    except queue.Empty:
                        logger.error("Тайм-аут ожидания соединения с БД")
                        return None
    
    def release_connection(self, conn: sqlite3.Connection):
        """Возврат соединения в пул"""
        try:
            # Проверяем, что соединение активно
            conn.execute("SELECT 1")
            # Возвращаем в пул
            self.connection_queue.put(conn)
        except sqlite3.Error:
            # Если соединение повреждено, закрываем его и создаем новое
            with self._lock:
                self.active_connections -= 1
            try:
                conn.close()
            except:
                pass
            # Создаем новое соединение
            self._create_connection()
    
    def close_all(self):
        """Закрытие всех соединений в пуле"""
        while not self.connection_queue.empty():
            try:
                conn = self.connection_queue.get(block=False)
                conn.close()
                with self._lock:
                    self.active_connections -= 1
            except:
                pass

class DatabaseManager:
    """Менеджер для работы с базой данных"""
    
    def __init__(self, db_name: str = DB_NAME):
        """
        Инициализация менеджера БД
        
        Args:
            db_name: Имя файла базы данных
        """
        self.db_name = db_name
        self.pool = ConnectionPool(db_name)
        self._init_database()
    
    def _init_database(self):
        """Инициализация базы данных и выполнение миграций"""
        try:
            # Проверяем, существует ли файл БД
            db_exists = os.path.exists(self.db_name)
            
            # Получаем соединение
            conn = self.pool.get_connection()
            if not conn:
                logger.critical("Не удалось инициализировать БД: ошибка соединения")
                return
                
            try:
                cursor = conn.cursor()
                
                # Если БД новая - создаем все с нуля
                if not db_exists:
                    self._create_tables(cursor)
                    self._set_schema_version(cursor, SCHEMA_VERSION)
                    conn.commit()
                else:
                    # Если БД существует, проверяем версию схемы
                    current_version = self._get_schema_version(cursor)
                    
                    # Если версия отличается, выполняем миграции
                    if current_version < SCHEMA_VERSION:
                        self._migrate_database(cursor, current_version, SCHEMA_VERSION)
                        conn.commit()
            finally:
                self.pool.release_connection(conn)
                
        except Exception as e:
            logger.critical(f"Ошибка при инициализации БД: {e}")
            raise
    
    def _create_tables(self, cursor: sqlite3.Cursor):
        """Создание всех таблиц базы данных"""
        # Таблица версий схемы
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version(
                version INTEGER PRIMARY KEY
            )
        """)
        
        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users(
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language_code TEXT,
                is_bot BOOLEAN DEFAULT 0,
                subscribe_date DATETIME,
                registration_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_activity DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица сессий
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions(
                session_id TEXT PRIMARY KEY,
                is_valid BOOLEAN DEFAULT 1,
                last_used DATETIME,
                last_check DATETIME,
                error_count INTEGER DEFAULT 0,
                notes TEXT
            )
        """)
        
        # Таблица платежей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments(
                payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                invoice_id TEXT,
                amount REAL,
                currency TEXT,
                status TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                subscription_days INTEGER,
                payment_method TEXT DEFAULT 'crypto',
                subscription_plan TEXT DEFAULT 'basic',
                promo_code TEXT,
                referral_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (referral_id) REFERENCES users(user_id) ON DELETE SET NULL
            )
        """)
        
        # Таблица операций (логи действий пользователей)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS operations(
                operation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                operation_type TEXT,
                target TEXT,
                params TEXT,
                result TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        
        # Таблица реферальной системы
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS referrals(
                referral_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                referrer_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                reward_paid BOOLEAN DEFAULT 0,
                level INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (referrer_id) REFERENCES users(user_id) ON DELETE SET NULL
            )
        """)
        
        # Таблица промокодов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes(
                promo_code TEXT PRIMARY KEY,
                discount_percent INTEGER,
                discount_fixed REAL,
                subscription_days INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME,
                max_usages INTEGER DEFAULT 1,
                current_usages INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                created_by_admin_id INTEGER,
                restricted_to_user_id INTEGER,
                subscription_plan TEXT,
                reports_count INTEGER DEFAULT 0,
                reports_left INTEGER DEFAULT 0
            )
        """)
        
        # Таблица использованных промокодов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS promo_usages(
                usage_id INTEGER PRIMARY KEY AUTOINCREMENT,
                promo_code TEXT,
                user_id INTEGER,
                used_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                payment_id INTEGER,
                reports_used INTEGER DEFAULT 0,
                FOREIGN KEY (promo_code) REFERENCES promo_codes(promo_code) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (payment_id) REFERENCES payments(payment_id) ON DELETE SET NULL
            )
        """)
        
        # Таблица подписок пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_subscriptions(
                subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                subscription_plan TEXT DEFAULT 'basic',
                starts_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME,
                is_active BOOLEAN DEFAULT 1,
                payment_id INTEGER,
                auto_renew BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (payment_id) REFERENCES payments(payment_id) ON DELETE SET NULL
            )
        """)
        
        # Таблица запланированных задач
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_tasks(
                task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                task_type TEXT,
                target TEXT,
                params TEXT,
                scheduled_time DATETIME,
                repeat_interval INTEGER DEFAULT 0,
                last_run DATETIME,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        
        logger.info("Созданы таблицы базы данных")
    
    def _get_schema_version(self, cursor: sqlite3.Cursor) -> int:
        """Получение текущей версии схемы БД"""
        try:
            # Проверяем существование таблицы schema_version
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'")
            if not cursor.fetchone():
                # Если таблицы нет, это старая версия
                return 1
                
            cursor.execute("SELECT version FROM schema_version LIMIT 1")
            result = cursor.fetchone()
            return result[0] if result else 1
        except:
            # В случае ошибки, считаем что версия 1
            return 1
    
    def _set_schema_version(self, cursor: sqlite3.Cursor, version: int):
        """Установка версии схемы БД"""
        cursor.execute("DELETE FROM schema_version")
        cursor.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
    
    def _migrate_database(self, cursor: sqlite3.Cursor, from_version: int, to_version: int):
        """
        Выполнение миграций базы данных
        
        Args:
            cursor: Курсор БД
            from_version: Текущая версия схемы
            to_version: Целевая версия схемы
        """
        logger.info(f"Выполняется миграция БД с версии {from_version} до {to_version}")
        
        try:
            # Миграция с версии 1 до 2
            if from_version == 1 and to_version >= 2:
                # Проверяем структуру таблицы users
                cursor.execute("PRAGMA table_info(users)")
                columns = {col[1]: col for col in cursor.fetchall()}
                
                # Если старая структура, создаем временную таблицу и переносим данные
                if len(columns) <= 2:  # Только user_id и subscribe
                    # Переименовываем старую таблицу
                    cursor.execute("ALTER TABLE users RENAME TO users_old")
                    
                    # Создаем новую таблицу с расширенной структурой
                    cursor.execute("""
                        CREATE TABLE users(
                            user_id INTEGER PRIMARY KEY,
                            username TEXT,
                            first_name TEXT,
                            last_name TEXT,
                            language_code TEXT,
                            is_bot BOOLEAN DEFAULT 0,
                            subscribe_date DATETIME,
                            registration_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                            last_activity DATETIME DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    
                    # Переносим данные из старой таблицы
                    cursor.execute("""
                        INSERT INTO users (user_id, subscribe_date)
                        SELECT user_id, subscribe FROM users_old
                    """)
                    
                    # Создаем остальные таблицы
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS sessions(
                            session_id TEXT PRIMARY KEY,
                            is_valid BOOLEAN DEFAULT 1,
                            last_used DATETIME,
                            last_check DATETIME,
                            error_count INTEGER DEFAULT 0,
                            notes TEXT
                        )
                    """)
                    
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS payments(
                            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER,
                            invoice_id TEXT,
                            amount REAL,
                            currency TEXT,
                            status TEXT,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            subscription_days INTEGER,
                            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                        )
                    """)
                    
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS operations(
                            operation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER,
                            operation_type TEXT,
                            target TEXT,
                            params TEXT,
                            result TEXT,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                        )
                    """)
                    
                    # Удаляем старую таблицу
                    cursor.execute("DROP TABLE users_old")
                
                # Обновляем версию схемы
                self._set_schema_version(cursor, 2)
                logger.info("Миграция до версии 2 выполнена успешно")
                
            # Миграция до версии 3
            if from_version < 3 and to_version >= 3:
                logger.info("Выполняется миграция до версии 3...")
                
                # Расширение таблицы payments
                try:
                    # Проверяем наличие новых колонок
                    cursor.execute("PRAGMA table_info(payments)")
                    columns = [col['name'] for col in cursor.fetchall()]
                    
                    # Добавляем новые колонки если их нет
                    if 'payment_method' not in columns:
                        cursor.execute("ALTER TABLE payments ADD COLUMN payment_method TEXT DEFAULT 'crypto'")
                    
                    if 'subscription_plan' not in columns:
                        cursor.execute("ALTER TABLE payments ADD COLUMN subscription_plan TEXT DEFAULT 'basic'")
                    
                    if 'promo_code' not in columns:
                        cursor.execute("ALTER TABLE payments ADD COLUMN promo_code TEXT")
                    
                    if 'referral_id' not in columns:
                        cursor.execute("ALTER TABLE payments ADD COLUMN referral_id INTEGER")
                    
                    # Создаем новые таблицы
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS referrals(
                            referral_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER,
                            referrer_id INTEGER,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            reward_paid BOOLEAN DEFAULT 0,
                            level INTEGER DEFAULT 1,
                            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                            FOREIGN KEY (referrer_id) REFERENCES users(user_id) ON DELETE SET NULL
                        )
                    """)
                    
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS promo_codes(
                            promo_code TEXT PRIMARY KEY,
                            discount_percent INTEGER,
                            discount_fixed REAL,
                            subscription_days INTEGER DEFAULT 0,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            expires_at DATETIME,
                            max_usages INTEGER DEFAULT 1,
                            current_usages INTEGER DEFAULT 0,
                            is_active BOOLEAN DEFAULT 1,
                            created_by_admin_id INTEGER,
                            restricted_to_user_id INTEGER,
                            subscription_plan TEXT
                        )
                    """)
                    
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS promo_usages(
                            usage_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            promo_code TEXT,
                            user_id INTEGER,
                            used_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            payment_id INTEGER,
                            FOREIGN KEY (promo_code) REFERENCES promo_codes(promo_code) ON DELETE CASCADE,
                            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                            FOREIGN KEY (payment_id) REFERENCES payments(payment_id) ON DELETE SET NULL
                        )
                    """)
                    
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS user_subscriptions(
                            subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER,
                            subscription_plan TEXT DEFAULT 'basic',
                            starts_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            expires_at DATETIME,
                            is_active BOOLEAN DEFAULT 1,
                            payment_id INTEGER,
                            auto_renew BOOLEAN DEFAULT 0,
                            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                            FOREIGN KEY (payment_id) REFERENCES payments(payment_id) ON DELETE SET NULL
                        )
                    """)
                    
                    # Создаем индексы для оптимизации
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_referrals_user_id ON referrals(user_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_referrals_referrer_id ON referrals(referrer_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_promo_usages_user_id ON promo_usages(user_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id ON user_subscriptions(user_id)")
                    
                    # Обновляем версию схемы
                    self._set_schema_version(cursor, 3)
                    logger.info("Миграция до версии 3 выполнена успешно")
                    
                except Exception as e:
                    logger.error(f"Ошибка при миграции до версии 3: {e}")
                    raise
            
            # Миграция до версии 4
            if from_version < 4 and to_version >= 4:
                logger.info("Выполняется миграция до версии 4...")
                
                # Создаем таблицу запланированных задач
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS scheduled_tasks(
                        task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        task_type TEXT,
                        target TEXT,
                        params TEXT,
                        scheduled_time DATETIME,
                        repeat_interval INTEGER DEFAULT 0,
                        last_run DATETIME,
                        status TEXT DEFAULT 'pending',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    )
                """)
                
                # Создаем индексы для оптимизации
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_user_id ON scheduled_tasks(user_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_status ON scheduled_tasks(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_scheduled_time ON scheduled_tasks(scheduled_time)")
                
                # Обновляем версию схемы
                self._set_schema_version(cursor, 4)
                logger.info("Миграция до версии 4 выполнена успешно")
            
            # Сюда можно добавить миграции на будущие версии
            
        except Exception as e:
            logger.error(f"Ошибка при выполнении миграции: {e}")
            raise
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None, 
                last_name: str = None, language_code: str = None, is_bot: bool = False) -> bool:
        """
        Добавление нового пользователя в базу данных
        
        Args:
            user_id: ID пользователя Telegram
            username: Имя пользователя
            first_name: Имя
            last_name: Фамилия
            language_code: Код языка
            is_bot: Является ли пользователь ботом
            
        Returns:
            bool: Успешно ли добавлен пользователь
        """
        conn = self.pool.get_connection()
        if not conn:
            return False
            
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO users 
                (user_id, username, first_name, last_name, language_code, is_bot, subscribe_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, username, first_name, last_name, language_code, 
                 1 if is_bot else 0, DEFAULT_SUBSCRIBE_DATE)
            )
            conn.commit()
            success = cursor.rowcount > 0
            
            if success:
                logger.info(f"Добавлен новый пользователь: {user_id}, {username}")
            
            return success
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при добавлении пользователя {user_id}: {e}")
            return False
        finally:
            self.pool.release_connection(conn)
    
    def update_user_activity(self, user_id: int, update_info: bool = False, 
                           message = None) -> bool:
        """
        Обновление информации о последней активности пользователя
        
        Args:
            user_id: ID пользователя
            update_info: Обновить информацию о пользователе из сообщения
            message: Объект сообщения от пользователя
            
        Returns:
            bool: Успешно ли обновлена информация
        """
        conn = self.pool.get_connection()
        if not conn:
            return False
            
        try:
            cursor = conn.cursor()
            
            # Обновляем время последней активности
            cursor.execute(
                "UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ?",
                (user_id,)
            )
            
            # Если нужно, обновляем информацию о пользователе
            if update_info and message:
                from_user = message.from_user
                cursor.execute(
                    """
                    UPDATE users SET 
                    username = ?, 
                    first_name = ?, 
                    last_name = ?, 
                    language_code = ?
                    WHERE user_id = ?
                    """,
                    (from_user.username, from_user.first_name, 
                     from_user.last_name, from_user.language_code, user_id)
                )
            
            conn.commit()
            return cursor.rowcount > 0
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при обновлении активности пользователя {user_id}: {e}")
            return False
        finally:
            self.pool.release_connection(conn)
    
    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получение данных пользователя по ID
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Optional[Dict[str, Any]]: Данные пользователя или None
        """
        conn = self.pool.get_connection()
        if not conn:
            return None
            
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            
            if result:
                return dict(result)
            return None
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении пользователя {user_id}: {e}")
            return None
        finally:
            self.pool.release_connection(conn)
    
    def user_exists(self, user_id: int) -> bool:
        """
        Проверка существования пользователя в базе данных
        
        Args:
            user_id: ID пользователя
            
        Returns:
            bool: Существует ли пользователь
        """
        conn = self.pool.get_connection()
        if not conn:
            return False
            
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM users WHERE user_id = ? LIMIT 1", (user_id,))
            return cursor.fetchone() is not None
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при проверке пользователя {user_id}: {e}")
            return False
        finally:
            self.pool.release_connection(conn)
    
    def update_subscription(self, user_id: int, new_date: str) -> bool:
        """
        Обновление даты подписки пользователя
        
        Args:
            user_id: ID пользователя
            new_date: Новая дата подписки
            
        Returns:
            bool: Успешно ли обновлена подписка
        """
        conn = self.pool.get_connection()
        if not conn:
            return False
            
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET subscribe_date = ? WHERE user_id = ?",
                (new_date, user_id)
            )
            conn.commit()
            success = cursor.rowcount > 0
            
            if success:
                logger.info(f"Обновлена подписка пользователя {user_id} до {new_date}")
                
            return success
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при обновлении подписки пользователя {user_id}: {e}")
            return False
        finally:
            self.pool.release_connection(conn)
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """
        Получение списка всех пользователей
        
        Returns:
            List[Dict[str, Any]]: Список пользователей
        """
        conn = self.pool.get_connection()
        if not conn:
            return []
            
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            results = cursor.fetchall()
            
            return [dict(row) for row in results]
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении списка пользователей: {e}")
            return []
        finally:
            self.pool.release_connection(conn)
    
    def get_subscription_date(self, user_id: int) -> Optional[str]:
        """
        Получение даты подписки пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Optional[str]: Дата подписки или None
        """
        conn = self.pool.get_connection()
        if not conn:
            return None
            
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT subscribe_date FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            
            return result['subscribe_date'] if result else None
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении даты подписки пользователя {user_id}: {e}")
            return None
        finally:
            self.pool.release_connection(conn)
    
    def log_operation(self, user_id: int, operation_type: str, target: str = None, 
                     params: str = None, result: str = None) -> bool:
        """
        Логирование операции пользователя
        
        Args:
            user_id: ID пользователя
            operation_type: Тип операции
            target: Цель операции
            params: Параметры операции
            result: Результат операции
            
        Returns:
            bool: Успешно ли залогирована операция
        """
        conn = self.pool.get_connection()
        if not conn:
            return False
            
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO operations 
                (user_id, operation_type, target, params, result)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, operation_type, target, params, result)
            )
            conn.commit()
            
            return cursor.rowcount > 0
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при логировании операции {operation_type} пользователя {user_id}: {e}")
            return False
        finally:
            self.pool.release_connection(conn)
    
    def record_payment(self, user_id: int, invoice_id: str, amount: float,
                      currency: str, status: str, subscription_days: int,
                      payment_method: str = 'crypto', subscription_plan: str = 'basic',
                      promo_code: str = None, referral_id: int = None) -> int:
        """
        Запись информации о платеже
        
        Args:
            user_id: ID пользователя
            invoice_id: ID инвойса
            amount: Сумма платежа
            currency: Валюта
            status: Статус платежа
            subscription_days: Количество дней подписки
            payment_method: Метод оплаты (crypto, card, qiwi, etc)
            subscription_plan: Тарифный план (basic, premium, vip)
            promo_code: Использованный промокод
            referral_id: ID реферала, если платеж был по реферальной программе
            
        Returns:
            int: ID платежа или 0 в случае ошибки
        """
        conn = self.pool.get_connection()
        if not conn:
            return 0
            
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO payments 
                (user_id, invoice_id, amount, currency, status, subscription_days, 
                payment_method, subscription_plan, promo_code, referral_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, invoice_id, amount, currency, status, subscription_days, 
                payment_method, subscription_plan, promo_code, referral_id)
            )
            conn.commit()
            
            payment_id = cursor.lastrowid
            logger.info(f"Записан платеж #{payment_id} пользователя {user_id}, инвойс {invoice_id}")
            return payment_id
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при записи платежа инвойс {invoice_id}, пользователь {user_id}: {e}")
            return 0
        finally:
            self.pool.release_connection(conn)
    
    def update_payment_status(self, invoice_id: str, status: str) -> bool:
        """
        Обновление статуса платежа
        
        Args:
            invoice_id: ID инвойса
            status: Новый статус
            
        Returns:
            bool: Успешно ли обновлен статус
        """
        conn = self.pool.get_connection()
        if not conn:
            return False
            
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE payments 
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE invoice_id = ?
                """,
                (status, invoice_id)
            )
            conn.commit()
            
            return cursor.rowcount > 0
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка при обновлении статуса платежа {invoice_id}: {e}")
            return False
        finally:
            self.pool.release_connection(conn)
    
    def close(self):
        """Закрытие всех соединений и освобождение ресурсов"""
        try:
            self.pool.close_all()
            logger.info("Закрыты все соединения с БД")
        except Exception as e:
            logger.error(f"Ошибка при закрытии соединений с БД: {e}")

# Создаем экземпляр для использования в других модулях
db = DatabaseManager() 
"""
Модуль для планирования и выполнения отложенных задач
"""
import logging
import json
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
import queue

import config
from app.database.db import db
from app.utils.report_manager import report_manager

logger = logging.getLogger(__name__)

class Task:
    """Класс для представления запланированной задачи"""
    
    def __init__(self, task_id: int, user_id: int, task_type: str, 
                 target: str, params: Dict[str, Any], scheduled_time: datetime,
                 repeat_interval: int = 0, last_run: datetime = None, 
                 status: str = "pending"):
        """
        Инициализация задачи
        
        Args:
            task_id: ID задачи
            user_id: ID пользователя
            task_type: Тип задачи (report, message, etc)
            target: Цель задачи (URL, user_id, etc)
            params: Параметры задачи
            scheduled_time: Запланированное время выполнения
            repeat_interval: Интервал повторения в минутах (0 - без повторения)
            last_run: Время последнего выполнения
            status: Статус задачи (pending, running, completed, failed)
        """
        self.task_id = task_id
        self.user_id = user_id
        self.task_type = task_type
        self.target = target
        self.params = params
        self.scheduled_time = scheduled_time
        self.repeat_interval = repeat_interval
        self.last_run = last_run
        self.status = status
    
    @classmethod
    def from_dict(cls, task_dict: Dict[str, Any]) -> 'Task':
        """
        Создание задачи из словаря
        
        Args:
            task_dict: Словарь с данными задачи
            
        Returns:
            Task: Объект задачи
        """
        # Конвертируем строки с датами в объекты datetime
        scheduled_time = datetime.strptime(task_dict['scheduled_time'], "%Y-%m-%d %H:%M:%S") if task_dict.get('scheduled_time') else None
        last_run = datetime.strptime(task_dict['last_run'], "%Y-%m-%d %H:%M:%S") if task_dict.get('last_run') else None
        
        # Конвертируем строку с параметрами в словарь
        params = {}
        if task_dict.get('params'):
            try:
                params = json.loads(task_dict['params'])
            except:
                logger.error(f"Ошибка при парсинге параметров задачи {task_dict.get('task_id')}")
        
        return cls(
            task_id=task_dict.get('task_id', 0),
            user_id=task_dict.get('user_id', 0),
            task_type=task_dict.get('task_type', ''),
            target=task_dict.get('target', ''),
            params=params,
            scheduled_time=scheduled_time,
            repeat_interval=task_dict.get('repeat_interval', 0),
            last_run=last_run,
            status=task_dict.get('status', 'pending')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразование задачи в словарь
        
        Returns:
            Dict[str, Any]: Словарь с данными задачи
        """
        return {
            'task_id': self.task_id,
            'user_id': self.user_id,
            'task_type': self.task_type,
            'target': self.target,
            'params': json.dumps(self.params) if isinstance(self.params, dict) else self.params,
            'scheduled_time': self.scheduled_time.strftime("%Y-%m-%d %H:%M:%S") if self.scheduled_time else None,
            'repeat_interval': self.repeat_interval,
            'last_run': self.last_run.strftime("%Y-%m-%d %H:%M:%S") if self.last_run else None,
            'status': self.status
        }
    
    def should_run(self) -> bool:
        """
        Проверка, должна ли задача быть выполнена сейчас
        
        Returns:
            bool: True, если задача должна быть выполнена
        """
        # Если задача уже завершена или отменена, не выполняем
        if self.status in ['completed', 'cancelled']:
            return False
            
        # Если время выполнения наступило и задача в статусе pending или failed
        return (self.scheduled_time <= datetime.now() and 
                self.status in ['pending', 'failed'])
    
    def update_after_run(self, success: bool, next_run: bool = True) -> None:
        """
        Обновление задачи после выполнения
        
        Args:
            success: Успешно ли выполнена задача
            next_run: Планировать ли следующее выполнение
        """
        self.last_run = datetime.now()
        
        # Если задача с повторением и нужно запланировать следующее выполнение
        if self.repeat_interval > 0 and next_run:
            self.scheduled_time = datetime.now() + timedelta(minutes=self.repeat_interval)
            self.status = 'pending'
        else:
            # Задача без повторения или не нужно планировать следующее выполнение
            self.status = 'completed' if success else 'failed'

class TaskScheduler:
    """Планировщик задач"""
    
    def __init__(self):
        """Инициализация планировщика задач"""
        self.tasks = {}  # task_id -> Task
        self.task_queue = queue.PriorityQueue()  # (scheduled_time, task_id)
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.worker_thread = None
        
        logger.info("Инициализирован TaskScheduler")
    
    def start(self):
        """Запуск планировщика задач в отдельном потоке"""
        self.stop_event.clear()
        self.load_tasks_from_db()
        
        if not self.worker_thread or not self.worker_thread.is_alive():
            self.worker_thread = threading.Thread(target=self._worker, daemon=True)
            self.worker_thread.start()
            logger.info("Запущен поток планировщика задач")
    
    def stop(self):
        """Остановка планировщика задач"""
        self.stop_event.set()
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)
            logger.info("Остановлен поток планировщика задач")
    
    def load_tasks_from_db(self):
        """Загрузка задач из базы данных"""
        try:
            # Получаем соединение с БД
            conn = db.pool.get_connection()
            if not conn:
                logger.error("Ошибка соединения с БД при загрузке задач")
                return
                
            cursor = conn.cursor()
            
            # Получаем все задачи, которые не выполнены и не отменены
            cursor.execute(
                """
                SELECT * FROM scheduled_tasks
                WHERE status IN ('pending', 'failed')
                """
            )
            
            results = cursor.fetchall()
            db.pool.release_connection(conn)
            
            # Очищаем существующие задачи
            with self.lock:
                self.tasks.clear()
                
                # Загружаем задачи
                for row in results:
                    task = Task.from_dict(dict(row))
                    self.tasks[task.task_id] = task
                    
                    # Добавляем в очередь задачи, которые должны выполниться в будущем
                    if task.scheduled_time > datetime.now():
                        self.task_queue.put((task.scheduled_time, task.task_id))
            
            logger.info(f"Загружено {len(self.tasks)} задач из БД")
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке задач из БД: {e}")
    
    def add_task(self, user_id: int, task_type: str, target: str, 
                params: Dict[str, Any], scheduled_time: datetime,
                repeat_interval: int = 0) -> Optional[int]:
        """
        Добавление новой задачи
        
        Args:
            user_id: ID пользователя
            task_type: Тип задачи
            target: Цель задачи
            params: Параметры задачи
            scheduled_time: Запланированное время выполнения
            repeat_interval: Интервал повторения в минутах
            
        Returns:
            Optional[int]: ID задачи или None в случае ошибки
        """
        try:
            # Проверяем права пользователя
            subscription = db.get_user_subscription(user_id)
            if not subscription or not subscription.get("is_active"):
                logger.warning(f"Пользователь {user_id} не имеет активной подписки для планирования задач")
                return None
                
            # Проверяем, поддерживает ли план пользователя планирование задач
            plan_id = subscription.get("subscription_plan", "basic")
            plan_features = config.SUBSCRIPTION_PLANS.get(plan_id, {}).get("features", [])
            
            if "scheduled_tasks" not in plan_features:
                logger.warning(f"Тарифный план пользователя {user_id} не поддерживает планирование задач")
                return None
                
            # Получаем соединение с БД
            conn = db.pool.get_connection()
            if not conn:
                logger.error(f"Ошибка соединения с БД при добавлении задачи для пользователя {user_id}")
                return None
                
            cursor = conn.cursor()
            
            # Сериализуем параметры в JSON
            params_json = json.dumps(params) if isinstance(params, dict) else params
            
            # Форматируем запланированное время
            scheduled_time_str = scheduled_time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Добавляем задачу в БД
            cursor.execute(
                """
                INSERT INTO scheduled_tasks
                (user_id, task_type, target, params, scheduled_time, repeat_interval, status)
                VALUES (?, ?, ?, ?, ?, ?, 'pending')
                """,
                (user_id, task_type, target, params_json, scheduled_time_str, repeat_interval)
            )
            
            conn.commit()
            task_id = cursor.lastrowid
            db.pool.release_connection(conn)
            
            # Создаем объект задачи
            task = Task(
                task_id=task_id,
                user_id=user_id,
                task_type=task_type,
                target=target,
                params=params,
                scheduled_time=scheduled_time,
                repeat_interval=repeat_interval,
                status='pending'
            )
            
            # Добавляем задачу в коллекцию и очередь
            with self.lock:
                self.tasks[task_id] = task
                self.task_queue.put((scheduled_time, task_id))
            
            logger.info(f"Добавлена новая задача #{task_id} для пользователя {user_id}, тип: {task_type}")
            
            return task_id
            
        except Exception as e:
            logger.error(f"Ошибка при добавлении задачи для пользователя {user_id}: {e}")
            return None
    
    def cancel_task(self, task_id: int, user_id: int = None) -> bool:
        """
        Отмена задачи
        
        Args:
            task_id: ID задачи
            user_id: ID пользователя (для проверки прав)
            
        Returns:
            bool: Успешно ли отменена задача
        """
        try:
            # Получаем задачу
            with self.lock:
                task = self.tasks.get(task_id)
                
                # Если задача не найдена, пробуем получить из БД
                if not task:
                    conn = db.pool.get_connection()
                    if not conn:
                        return False
                        
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM scheduled_tasks WHERE task_id = ?", (task_id,))
                    result = cursor.fetchone()
                    db.pool.release_connection(conn)
                    
                    if not result:
                        logger.warning(f"Задача #{task_id} не найдена при отмене")
                        return False
                        
                    task = Task.from_dict(dict(result))
                
                # Проверяем права пользователя
                if user_id is not None and task.user_id != user_id:
                    # Проверяем, является ли пользователь администратором
                    admin_level = config.ADMINS.get(user_id, 0)
                    if admin_level < config.ADMIN_LEVEL_MODERATOR:
                        logger.warning(f"Пользователь {user_id} не имеет прав на отмену задачи #{task_id}")
                        return False
                
                # Отменяем задачу
                task.status = 'cancelled'
                
                # Обновляем в БД
                conn = db.pool.get_connection()
                if not conn:
                    return False
                    
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE scheduled_tasks
                    SET status = 'cancelled'
                    WHERE task_id = ?
                    """,
                    (task_id,)
                )
                conn.commit()
                db.pool.release_connection(conn)
                
                # Удаляем из коллекции
                if task_id in self.tasks:
                    del self.tasks[task_id]
                
                logger.info(f"Отменена задача #{task_id}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при отмене задачи #{task_id}: {e}")
            return False
    
    def get_user_tasks(self, user_id: int) -> List[Task]:
        """
        Получение списка задач пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            List[Task]: Список задач
        """
        try:
            # Получаем соединение с БД
            conn = db.pool.get_connection()
            if not conn:
                logger.error(f"Ошибка соединения с БД при получении задач пользователя {user_id}")
                return []
                
            cursor = conn.cursor()
            
            # Получаем задачи пользователя, которые не отменены
            cursor.execute(
                """
                SELECT * FROM scheduled_tasks
                WHERE user_id = ? AND status != 'cancelled'
                ORDER BY scheduled_time ASC
                """,
                (user_id,)
            )
            
            results = cursor.fetchall()
            db.pool.release_connection(conn)
            
            # Преобразуем результаты в объекты Task
            tasks = [Task.from_dict(dict(row)) for row in results]
            
            return tasks
            
        except Exception as e:
            logger.error(f"Ошибка при получении задач пользователя {user_id}: {e}")
            return []
    
    def get_task(self, task_id: int) -> Optional[Task]:
        """
        Получение задачи по ID
        
        Args:
            task_id: ID задачи
            
        Returns:
            Optional[Task]: Задача или None
        """
        # Проверяем, есть ли задача в коллекции
        with self.lock:
            task = self.tasks.get(task_id)
            if task:
                return task
        
        try:
            # Получаем задачу из БД
            conn = db.pool.get_connection()
            if not conn:
                return None
                
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scheduled_tasks WHERE task_id = ?", (task_id,))
            result = cursor.fetchone()
            db.pool.release_connection(conn)
            
            if not result:
                return None
                
            # Создаем объект задачи
            task = Task.from_dict(dict(result))
            
            # Добавляем в коллекцию, если задача не отменена и не выполнена
            if task.status not in ['cancelled', 'completed']:
                with self.lock:
                    self.tasks[task_id] = task
                    
                    # Если задача должна выполниться в будущем, добавляем в очередь
                    if task.scheduled_time > datetime.now():
                        self.task_queue.put((task.scheduled_time, task_id))
            
            return task
            
        except Exception as e:
            logger.error(f"Ошибка при получении задачи #{task_id}: {e}")
            return None
    
    def _worker(self):
        """Рабочий поток для выполнения задач"""
        logger.info("Запущен рабочий поток планировщика задач")
        
        while not self.stop_event.is_set():
            try:
                # Получаем следующую задачу из очереди с таймаутом
                try:
                    # Проверяем, есть ли задачи, которые должны выполниться сейчас
                    with self.lock:
                        current_tasks = []
                        
                        for task_id, task in self.tasks.items():
                            if task.should_run():
                                current_tasks.append(task)
                        
                        # Если есть задачи для выполнения сейчас, обрабатываем их
                        if current_tasks:
                            for task in current_tasks:
                                self._execute_task(task)
                                
                    # Проверяем очередь на предмет задач, которые должны выполниться в ближайшее время
                    if not self.task_queue.empty():
                        next_time, task_id = self.task_queue.get(block=False)
                        
                        # Если время выполнения задачи наступило или она должна быть выполнена сейчас
                        if next_time <= datetime.now():
                            task = self.tasks.get(task_id)
                            if task and task.should_run():
                                self._execute_task(task)
                        else:
                            # Если время еще не наступило, возвращаем задачу в очередь
                            self.task_queue.put((next_time, task_id))
                            
                            # Ждем до следующего запланированного времени, но не более 5 секунд
                            wait_time = (next_time - datetime.now()).total_seconds()
                            self.stop_event.wait(min(wait_time, 5.0))
                    else:
                        # Если очередь пуста, проверяем каждые 5 секунд
                        self.stop_event.wait(5.0)
                
                except queue.Empty:
                    # Если очередь пуста, проверяем каждые 5 секунд
                    self.stop_event.wait(5.0)
                    
            except Exception as e:
                logger.error(f"Ошибка в рабочем потоке планировщика задач: {e}")
                self.stop_event.wait(5.0)  # Ждем 5 секунд перед следующей попыткой
        
        logger.info("Остановлен рабочий поток планировщика задач")
    
    def _execute_task(self, task: Task):
        """
        Выполнение задачи
        
        Args:
            task: Задача для выполнения
        """
        logger.info(f"Выполнение задачи #{task.task_id}, тип: {task.task_type}, пользователь: {task.user_id}")
        
        try:
            # Обновляем статус задачи в БД
            conn = db.pool.get_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE scheduled_tasks
                    SET status = 'running', last_run = CURRENT_TIMESTAMP
                    WHERE task_id = ?
                    """,
                    (task.task_id,)
                )
                conn.commit()
                db.pool.release_connection(conn)
            
            # Выполняем задачу в зависимости от типа
            success = False
            
            if task.task_type == 'report':
                success = self._execute_report_task(task)
            elif task.task_type == 'message':
                # TODO: Реализовать отправку сообщений
                success = False
            else:
                logger.warning(f"Неизвестный тип задачи: {task.task_type}")
                success = False
            
            # Обновляем статус задачи после выполнения
            task.update_after_run(success)
            
            # Обновляем задачу в БД
            conn = db.pool.get_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE scheduled_tasks
                    SET status = ?, last_run = ?, scheduled_time = ?
                    WHERE task_id = ?
                    """,
                    (
                        task.status,
                        task.last_run.strftime("%Y-%m-%d %H:%M:%S") if task.last_run else None,
                        task.scheduled_time.strftime("%Y-%m-%d %H:%M:%S") if task.scheduled_time else None,
                        task.task_id
                    )
                )
                conn.commit()
                db.pool.release_connection(conn)
            
            # Если задача должна повторяться и запланировано следующее выполнение,
            # добавляем ее обратно в очередь
            if task.status == 'pending' and task.scheduled_time > datetime.now():
                with self.lock:
                    self.task_queue.put((task.scheduled_time, task.task_id))
            
            logger.info(f"Выполнена задача #{task.task_id}, результат: {'успешно' if success else 'ошибка'}")
            
        except Exception as e:
            logger.error(f"Ошибка при выполнении задачи #{task.task_id}: {e}")
            
            # В случае ошибки обновляем статус задачи
            task.status = 'failed'
            task.last_run = datetime.now()
            
            # Обновляем задачу в БД
            conn = db.pool.get_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE scheduled_tasks
                    SET status = 'failed', last_run = CURRENT_TIMESTAMP
                    WHERE task_id = ?
                    """,
                    (task.task_id,)
                )
                conn.commit()
                db.pool.release_connection(conn)
    
    def _execute_report_task(self, task: Task) -> bool:
        """
        Выполнение задачи отправки жалобы
        
        Args:
            task: Задача для выполнения
            
        Returns:
            bool: Успешно ли выполнена задача
        """
        try:
            # Извлекаем параметры
            reason = task.params.get('reason', 'spam')
            user_id = task.user_id
            target_url = task.target
            
            # Проверяем валидность цели
            if not target_url or 't.me/' not in target_url:
                logger.warning(f"Невалидная цель для задачи #{task.task_id}: {target_url}")
                return False
            
            # Извлекаем имя пользователя и ID сообщения
            from app.utils.report import extract_username_and_message_id
            username, message_id = extract_username_and_message_id(target_url)
            
            if not username or not message_id:
                logger.warning(f"Не удалось извлечь username и message_id для задачи #{task.task_id}: {target_url}")
                return False
            
            # Получаем настройки интенсивности
            intensity = task.params.get('intensity', 'medium')
            intensity_value = config.REPORT_INTENSITY_LEVELS.get(intensity, 0.5)
            
            # Получаем сессии пользователя
            sessions = task.params.get('sessions', [])
            
            # Если сессии не указаны, получаем все сессии пользователя
            if not sessions:
                from app.utils.session_manager import session_manager
                sessions = session_manager.get_valid_sessions()
                
                # Ограничиваем количество сессий в зависимости от плана
                subscription = db.get_user_subscription(user_id)
                if subscription:
                    plan_id = subscription.get("subscription_plan", "basic")
                    max_sessions = config.SUBSCRIPTION_PLANS.get(plan_id, {}).get("max_sessions_per_request", 50)
                    sessions = sessions[:max_sessions]
            
            # Отправляем жалобы
            from app.utils.report_manager import report_manager
            result = report_manager.send_reports_in_parallel(
                username=username,
                message_id=message_id,
                reason=reason,
                user_id=user_id,
                session_ids=sessions,
                intensity=intensity_value
            )
            
            # Логируем результат
            if result:
                logger.info(f"Успешно выполнена задача отправки жалоб #{task.task_id}: {result}")
                return True
            else:
                logger.warning(f"Ошибка при выполнении задачи отправки жалоб #{task.task_id}")
                return False
            
        except Exception as e:
            logger.error(f"Ошибка при выполнении задачи отправки жалоб #{task.task_id}: {e}")
            return False

# Создаем экземпляр для удобного импорта
task_scheduler = TaskScheduler() 
"""
Модуль для работы с промокодами
"""
import logging
import string
import secrets
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union

import config
from app.database.db import db

logger = logging.getLogger(__name__)

class PromoCodeManager:
    """Менеджер для работы с промокодами"""
    
    def __init__(self):
        """Инициализация менеджера промокодов"""
        self.enabled = config.PROMO_SYSTEM.get("enabled", False)
        self.max_usage_per_code = config.PROMO_SYSTEM.get("max_usage_per_code", 100)
        self.max_discount_percent = config.PROMO_SYSTEM.get("max_discount_percent", 50)
        self.default_expiry_days = config.PROMO_SYSTEM.get("default_expiry_days", 30)
        self.promo_only_mode = config.PROMO_SYSTEM.get("promo_only_mode", False)
        self.disable_payment_system = config.PROMO_SYSTEM.get("disable_payment_system", False)
        self.default_reports_count = config.PROMO_SYSTEM.get("reports_per_promo", {}).get("default", 100)
        self.min_reports_count = config.PROMO_SYSTEM.get("reports_per_promo", {}).get("min", 10)
        self.max_reports_count = config.PROMO_SYSTEM.get("reports_per_promo", {}).get("max", 10000)
        
        logger.info(f"Инициализирован PromoCodeManager (enabled: {self.enabled}, promo_only_mode: {self.promo_only_mode})")
    
    def generate_promo_code(self, 
                         length: int = 8, 
                         discount_percent: int = 10, 
                         discount_fixed: float = 0, 
                         subscription_days: int = 0,
                         expires_days: int = None,
                         max_usages: int = None,
                         created_by_admin_id: int = None,
                         restricted_to_user_id: int = None,
                         subscription_plan: str = None,
                         reports_count: int = None) -> str:
        """
        Генерация нового промокода
        
        Args:
            length: Длина промокода
            discount_percent: Скидка в процентах
            discount_fixed: Фиксированная скидка
            subscription_days: Количество дней подписки
            expires_days: Срок действия в днях
            max_usages: Максимальное количество использований
            created_by_admin_id: ID администратора, создавшего промокод
            restricted_to_user_id: ID пользователя, для которого ограничен промокод
            subscription_plan: Тарифный план, для которого действует промокод
            reports_count: Количество сносов для промокода
            
        Returns:
            str: Сгенерированный промокод
        """
        if not self.enabled:
            logger.warning("Система промокодов отключена")
            return None
            
        # Проверяем параметры
        if discount_percent > self.max_discount_percent:
            discount_percent = self.max_discount_percent
            
        if max_usages is None:
            max_usages = self.max_usage_per_code
            
        if expires_days is None:
            expires_days = self.default_expiry_days
            
        # Проверяем количество сносов
        if reports_count is not None:
            if reports_count < self.min_reports_count:
                reports_count = self.min_reports_count
            elif reports_count > self.max_reports_count:
                reports_count = self.max_reports_count
        elif self.promo_only_mode:
            # В режиме только промокодов, задаем значение по умолчанию
            reports_count = self.default_reports_count
            
        # Генерируем случайный код
        alphabet = string.ascii_uppercase + string.digits
        promo_code = ''.join(secrets.choice(alphabet) for _ in range(length))
        
        # Рассчитываем дату истечения
        expires_at = None
        if expires_days > 0:
            expires_at = (datetime.now() + timedelta(days=expires_days)).strftime("%Y-%m-%d %H:%M:%S")
            
        # Сохраняем промокод в БД
        conn = db.pool.get_connection()
        if not conn:
            return None
            
        try:
            cursor = conn.cursor()
            
            # Проверяем, не существует ли уже такой промокод
            cursor.execute("SELECT 1 FROM promo_codes WHERE promo_code = ?", (promo_code,))
            if cursor.fetchone():
                # Если промокод уже существует, генерируем новый
                logger.warning(f"Промокод {promo_code} уже существует, генерируем новый")
                self.pool.release_connection(conn)
                return self.generate_promo_code(
                    length, discount_percent, discount_fixed, subscription_days,
                    expires_days, max_usages, created_by_admin_id, 
                    restricted_to_user_id, subscription_plan, reports_count
                )
                
            # Вставляем промокод в БД
            cursor.execute(
                """
                INSERT INTO promo_codes 
                (promo_code, discount_percent, discount_fixed, subscription_days, 
                expires_at, max_usages, is_active, created_by_admin_id, 
                restricted_to_user_id, subscription_plan, reports_count, reports_left)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
                """,
                (
                    promo_code, discount_percent, discount_fixed, subscription_days,
                    expires_at, max_usages, created_by_admin_id, 
                    restricted_to_user_id, subscription_plan, 
                    reports_count, reports_count if reports_count is not None else None
                )
            )
            conn.commit()
            
            logger.info(
                f"Создан новый промокод {promo_code} "
                f"(скидка: {discount_percent}%, {discount_fixed}$, "
                f"дней: {subscription_days}, сносы: {reports_count})"
            )
            
            return promo_code
            
        except Exception as e:
            logger.error(f"Ошибка при создании промокода: {e}")
            return None
        finally:
            db.pool.release_connection(conn)
    
    def check_promo_code(self, promo_code: str, user_id: int = None) -> Dict[str, Any]:
        """
        Проверка валидности промокода
        
        Args:
            promo_code: Промокод
            user_id: ID пользователя
            
        Returns:
            Dict[str, Any]: Результат проверки
        """
        if not self.enabled:
            return {"valid": False, "error": "promo_system_disabled"}
            
        # Проверяем промокод через базу данных
        promo_info = db.check_promo_code(promo_code, user_id)
        
        if not promo_info.get("valid", False):
            logger.warning(f"Неверный промокод {promo_code} для пользователя {user_id}: {promo_info.get('error')}")
            return promo_info
            
        logger.info(f"Проверен промокод {promo_code} для пользователя {user_id}: действителен")
        return promo_info
    
    def apply_promo_code(self, promo_code: str, user_id: int, 
                       original_price: float, subscription_plan: str = None) -> Dict[str, Any]:
        """
        Применение промокода к цене
        
        Args:
            promo_code: Промокод
            user_id: ID пользователя
            original_price: Исходная цена
            subscription_plan: Тарифный план
            
        Returns:
            Dict[str, Any]: Результат применения промокода
        """
        # Проверяем промокод
        promo_check = self.check_promo_code(promo_code, user_id)
        
        if not promo_check.get("valid", False):
            return {
                "valid": False,
                "error": promo_check.get("error"),
                "original_price": original_price,
                "final_price": original_price,
                "discount_amount": 0,
                "discount_percent": 0
            }
            
        promo_data = promo_check.get("promo_data", {})
        
        # Проверяем ограничение по плану подписки
        if subscription_plan and promo_data.get("subscription_plan") and promo_data.get("subscription_plan") != subscription_plan:
            return {
                "valid": False,
                "error": "wrong_subscription_plan",
                "original_price": original_price,
                "final_price": original_price,
                "discount_amount": 0,
                "discount_percent": 0
            }
            
        # Рассчитываем скидку
        discount_amount = 0
        
        # Применяем процентную скидку
        if promo_data.get("discount_percent"):
            discount_amount = original_price * (promo_data.get("discount_percent", 0) / 100)
            
        # Применяем фиксированную скидку (если она больше процентной)
        if promo_data.get("discount_fixed"):
            discount_amount = max(discount_amount, promo_data.get("discount_fixed", 0))
            
        # Ограничиваем скидку, чтобы она не превышала 95% от цены
        max_discount = original_price * 0.95
        if discount_amount > max_discount:
            discount_amount = max_discount
            
        # Рассчитываем итоговую цену
        final_price = original_price - discount_amount
        
        # Рассчитываем процент скидки для отображения
        discount_percent = int(round((discount_amount / original_price) * 100)) if original_price > 0 else 0
        
        return {
            "valid": True,
            "original_price": original_price,
            "final_price": final_price,
            "discount_amount": discount_amount,
            "discount_percent": discount_percent,
            "subscription_days_bonus": promo_data.get("subscription_days", 0),
            "promo_data": promo_data
        }
    
    def use_promo_code(self, promo_code: str, user_id: int, payment_id: int = None) -> bool:
        """
        Отметка об использовании промокода
        
        Args:
            promo_code: Промокод
            user_id: ID пользователя
            payment_id: ID платежа
            
        Returns:
            bool: Успешно ли использован промокод
        """
        if not self.enabled:
            return False
            
        # Отмечаем использование промокода
        result = db.use_promo_code(promo_code, user_id, payment_id)
        
        if result:
            logger.info(f"Использован промокод {promo_code} пользователем {user_id}")
        else:
            logger.warning(f"Ошибка при использовании промокода {promo_code} пользователем {user_id}")
            
        return result
    
    def get_active_promo_codes(self, admin_id: int = None) -> List[Dict[str, Any]]:
        """
        Получение списка активных промокодов
        
        Args:
            admin_id: ID администратора (для фильтрации по создателю)
            
        Returns:
            List[Dict[str, Any]]: Список промокодов
        """
        if not self.enabled:
            return []
            
        conn = db.pool.get_connection()
        if not conn:
            return []
            
        try:
            cursor = conn.cursor()
            
            # Формируем запрос в зависимости от наличия admin_id
            if admin_id:
                cursor.execute(
                    """
                    SELECT * FROM promo_codes
                    WHERE is_active = 1 AND created_by_admin_id = ?
                    ORDER BY created_at DESC
                    """,
                    (admin_id,)
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM promo_codes
                    WHERE is_active = 1
                    ORDER BY created_at DESC
                    """
                )
                
            results = cursor.fetchall()
            
            # Преобразуем результаты в список словарей
            promo_codes = []
            for row in results:
                promo_code = dict(row)
                
                # Добавляем статистику использования
                cursor.execute(
                    """
                    SELECT COUNT(*) as usage_count FROM promo_usages
                    WHERE promo_code = ?
                    """,
                    (promo_code.get("promo_code"),)
                )
                usage_stat = cursor.fetchone()
                promo_code["usage_count"] = usage_stat.get("usage_count", 0) if usage_stat else 0
                
                promo_codes.append(promo_code)
                
            return promo_codes
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка промокодов: {e}")
            return []
        finally:
            db.pool.release_connection(conn)
    
    def deactivate_promo_code(self, promo_code: str, admin_id: int = None) -> bool:
        """
        Деактивация промокода
        
        Args:
            promo_code: Промокод
            admin_id: ID администратора (для проверки прав)
            
        Returns:
            bool: Успешно ли деактивирован промокод
        """
        if not self.enabled:
            return False
            
        conn = db.pool.get_connection()
        if not conn:
            return False
            
        try:
            cursor = conn.cursor()
            
            # Проверяем права, если указан admin_id
            if admin_id:
                cursor.execute(
                    """
                    SELECT created_by_admin_id FROM promo_codes
                    WHERE promo_code = ?
                    """,
                    (promo_code,)
                )
                result = cursor.fetchone()
                
                # Если промокод создан другим админом, проверяем уровень доступа
                if result and result.get("created_by_admin_id") != admin_id:
                    # Проверяем, является ли админ суперадмином
                    admin_level = config.ADMINS.get(admin_id, 0)
                    if admin_level < config.ADMIN_LEVEL_FULL:
                        logger.warning(f"Администратор {admin_id} не имеет прав на деактивацию промокода {promo_code}")
                        return False
            
            # Деактивируем промокод
            cursor.execute(
                """
                UPDATE promo_codes
                SET is_active = 0
                WHERE promo_code = ?
                """,
                (promo_code,)
            )
            conn.commit()
            
            success = cursor.rowcount > 0
            
            if success:
                logger.info(f"Деактивирован промокод {promo_code}")
            else:
                logger.warning(f"Промокод {promo_code} не найден")
                
            return success
            
        except Exception as e:
            logger.error(f"Ошибка при деактивации промокода {promo_code}: {e}")
            return False
        finally:
            db.pool.release_connection(conn)

    def generate_reports_promo(self, reports_count: int, max_usages: int = 1, 
                           expires_days: int = 30, created_by_admin_id: int = None,
                           restricted_to_user_id: int = None) -> str:
        """
        Генерация промокода с количеством сносов
        
        Args:
            reports_count: Количество сносов
            max_usages: Максимальное количество использований
            expires_days: Срок действия в днях
            created_by_admin_id: ID администратора, создавшего промокод
            restricted_to_user_id: ID пользователя, для которого ограничен промокод
            
        Returns:
            str: Сгенерированный промокод
        """
        return self.generate_promo_code(
            length=10,
            discount_percent=0,
            discount_fixed=0,
            subscription_days=0,
            expires_days=expires_days,
            max_usages=max_usages,
            created_by_admin_id=created_by_admin_id,
            restricted_to_user_id=restricted_to_user_id,
            reports_count=reports_count
        )

    def check_reports_left(self, user_id: int) -> int:
        """
        Проверка оставшегося количества сносов у пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            int: Количество оставшихся сносов
        """
        if not self.enabled:
            return 0
            
        conn = db.pool.get_connection()
        if not conn:
            return 0
            
        try:
            cursor = conn.cursor()
            
            # Получаем активные промокоды пользователя с количеством сносов
            cursor.execute(
                """
                SELECT p.promo_code, p.reports_left
                FROM promo_codes p
                JOIN promo_usages u ON p.promo_code = u.promo_code
                WHERE u.user_id = ? AND p.is_active = 1 AND p.reports_left > 0
                """,
                (user_id,)
            )
            
            results = cursor.fetchall()
            
            # Суммируем количество оставшихся сносов
            total_reports_left = sum(row['reports_left'] for row in results if row['reports_left'])
            
            return total_reports_left
            
        except Exception as e:
            logger.error(f"Ошибка при проверке оставшихся сносов для пользователя {user_id}: {e}")
            return 0
        finally:
            db.pool.release_connection(conn)
            
    def use_reports(self, user_id: int, reports_count: int = 1) -> bool:
        """
        Использование определенного количества сносов пользователем
        
        Args:
            user_id: ID пользователя
            reports_count: Количество используемых сносов
            
        Returns:
            bool: Успешно ли использованы сносы
        """
        if not self.enabled:
            return False
            
        # Проверяем, есть ли у пользователя достаточное количество сносов
        available_reports = self.check_reports_left(user_id)
        
        if available_reports < reports_count:
            logger.warning(f"У пользователя {user_id} недостаточно сносов: {available_reports} < {reports_count}")
            return False
            
        conn = db.pool.get_connection()
        if not conn:
            return False
            
        try:
            cursor = conn.cursor()
            
            # Получаем активные промокоды пользователя с количеством сносов
            cursor.execute(
                """
                SELECT p.promo_code, p.reports_left
                FROM promo_codes p
                JOIN promo_usages u ON p.promo_code = u.promo_code
                WHERE u.user_id = ? AND p.is_active = 1 AND p.reports_left > 0
                ORDER BY u.used_at ASC
                """,
                (user_id,)
            )
            
            promo_codes = cursor.fetchall()
            
            # Используем сносы, начиная с самых старых промокодов
            remaining_to_use = reports_count
            
            for promo in promo_codes:
                if remaining_to_use <= 0:
                    break
                    
                promo_code = promo['promo_code']
                reports_left = promo['reports_left']
                
                # Определяем, сколько сносов использовать из текущего промокода
                to_use = min(remaining_to_use, reports_left)
                
                # Обновляем количество оставшихся сносов
                cursor.execute(
                    """
                    UPDATE promo_codes
                    SET reports_left = reports_left - ?
                    WHERE promo_code = ?
                    """,
                    (to_use, promo_code)
                )
                
                # Обновляем использование промокода
                cursor.execute(
                    """
                    UPDATE promo_usages
                    SET reports_used = reports_used + ?
                    WHERE promo_code = ? AND user_id = ?
                    """,
                    (to_use, promo_code, user_id)
                )
                
                # Уменьшаем оставшееся количество для использования
                remaining_to_use -= to_use
                
                # Если промокод исчерпан, деактивируем его
                if reports_left - to_use <= 0:
                    cursor.execute(
                        """
                        UPDATE promo_codes
                        SET is_active = 0
                        WHERE promo_code = ?
                        """,
                        (promo_code,)
                    )
                    
            conn.commit()
            
            # Проверяем, все ли сносы были использованы
            success = remaining_to_use == 0
            
            if success:
                logger.info(f"Пользователь {user_id} использовал {reports_count} сносов")
            else:
                logger.warning(f"Не удалось использовать все сносы для пользователя {user_id}: осталось {remaining_to_use}")
                
            return success
            
        except Exception as e:
            logger.error(f"Ошибка при использовании сносов для пользователя {user_id}: {e}")
            return False
        finally:
            db.pool.release_connection(conn)
            
    def is_payment_disabled(self) -> bool:
        """
        Проверка, отключена ли система оплаты подписки
        
        Returns:
            bool: True если система оплаты отключена
        """
        return self.disable_payment_system
        
    def is_promo_only_mode(self) -> bool:
        """
        Проверка, работает ли система только через промокоды
        
        Returns:
            bool: True если система работает только через промокоды
        """
        return self.promo_only_mode

# Создаем экземпляр для удобного импорта
promo_manager = PromoCodeManager() 
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
        
        logger.info(f"Инициализирован PromoCodeManager (enabled: {self.enabled})")
    
    def generate_promo_code(self, 
                         length: int = 8, 
                         discount_percent: int = 10, 
                         discount_fixed: float = 0, 
                         subscription_days: int = 0,
                         expires_days: int = None,
                         max_usages: int = None,
                         created_by_admin_id: int = None,
                         restricted_to_user_id: int = None,
                         subscription_plan: str = None) -> str:
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
            
        # Генерируем случайный код
        alphabet = string.ascii_uppercase + string.digits
        promo_code = ''.join(secrets.choice(alphabet) for _ in range(length))
        
        # Рассчитываем дату истечения срока действия
        expires_at = (datetime.now() + timedelta(days=expires_days)).strftime("%Y-%m-%d %H:%M:%S")
        
        # Создаем промокод в БД
        success = db.create_promo_code(
            promo_code=promo_code,
            discount_percent=discount_percent,
            discount_fixed=discount_fixed,
            subscription_days=subscription_days,
            expires_at=expires_at,
            max_usages=max_usages,
            created_by_admin_id=created_by_admin_id,
            restricted_to_user_id=restricted_to_user_id,
            subscription_plan=subscription_plan
        )
        
        if success:
            logger.info(f"Создан промокод {promo_code} со скидкой {discount_percent}% и {discount_fixed}$")
            return promo_code
        else:
            logger.error(f"Ошибка при создании промокода")
            return None
    
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

# Создаем экземпляр для удобного импорта
promo_manager = PromoCodeManager() 
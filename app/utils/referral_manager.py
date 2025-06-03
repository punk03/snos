"""
Модуль для работы с реферальной системой
"""
import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

import config
from app.database.db import db

logger = logging.getLogger(__name__)

class ReferralManager:
    """Менеджер для работы с реферальной системой"""
    
    def __init__(self):
        """Инициализация менеджера реферальной системы"""
        self.enabled = config.REFERRAL_SYSTEM.get("enabled", False)
        self.reward_type = config.REFERRAL_SYSTEM.get("reward_type", "subscription_days")
        self.levels = config.REFERRAL_SYSTEM.get("levels", 2)
        self.first_level_reward = config.REFERRAL_SYSTEM.get("first_level_reward", 3)
        self.second_level_reward = config.REFERRAL_SYSTEM.get("second_level_reward", 1)
        self.min_purchase_required = config.REFERRAL_SYSTEM.get("min_purchase_required", True)
        
        logger.info(f"Инициализирован ReferralManager (enabled: {self.enabled})")
    
    def generate_ref_link(self, user_id: int, bot_username: str) -> str:
        """
        Генерация реферальной ссылки для пользователя
        
        Args:
            user_id: ID пользователя
            bot_username: Имя бота
            
        Returns:
            str: Реферальная ссылка
        """
        return f"https://t.me/{bot_username}?start=ref{user_id}"
    
    def parse_ref_link(self, start_param: str) -> Optional[int]:
        """
        Извлечение ID реферера из параметра старта
        
        Args:
            start_param: Параметр start из ссылки
            
        Returns:
            Optional[int]: ID реферера или None
        """
        if not start_param:
            return None
            
        if start_param.startswith('ref'):
            try:
                return int(start_param[3:])
            except ValueError:
                return None
                
        return None
    
    def add_referral(self, user_id: int, referrer_id: int) -> bool:
        """
        Добавление реферальной связи между пользователями
        
        Args:
            user_id: ID нового пользователя
            referrer_id: ID пользователя-реферера
            
        Returns:
            bool: Успешно ли добавлен реферал
        """
        if not self.enabled:
            logger.warning("Реферальная система отключена")
            return False
            
        # Проверяем, что пользователи не совпадают
        if user_id == referrer_id:
            logger.warning(f"Попытка добавить самого себя в качестве реферала (user_id: {user_id})")
            return False
            
        # Проверяем существование пользователя-реферера
        if not db.get_user(referrer_id):
            logger.warning(f"Пользователь-реферер {referrer_id} не существует")
            return False
            
        # Проверяем, что пользователь еще не является рефералом
        referrer = db.get_referrer(user_id)
        if referrer:
            logger.warning(f"Пользователь {user_id} уже является рефералом {referrer.get('referrer_id')}")
            return False
            
        # Добавляем реферальную связь первого уровня
        success = db.add_referral(user_id, referrer_id, level=1)
        
        if success:
            logger.info(f"Добавлен реферал {user_id} для пользователя {referrer_id}")
            
            # Проверяем наличие реферера у реферера (для второго уровня)
            if self.levels >= 2:
                referrer_of_referrer = db.get_referrer(referrer_id)
                if referrer_of_referrer:
                    second_level_referrer_id = referrer_of_referrer.get('referrer_id')
                    # Добавляем реферальную связь второго уровня
                    db.add_referral(user_id, second_level_referrer_id, level=2)
                    logger.info(f"Добавлен реферал второго уровня {user_id} для пользователя {second_level_referrer_id}")
            
        return success
    
    def process_reward_for_payment(self, user_id: int, payment_amount: float) -> List[Dict[str, Any]]:
        """
        Обработка реферальных вознаграждений при оплате
        
        Args:
            user_id: ID пользователя, совершившего оплату
            payment_amount: Сумма оплаты
            
        Returns:
            List[Dict[str, Any]]: Информация о начисленных вознаграждениях
        """
        if not self.enabled or not user_id:
            return []
            
        results = []
        
        # Получаем реферера первого уровня
        referrer = db.get_referrer(user_id)
        if referrer and referrer.get('level') == 1:
            referrer_id = referrer.get('referrer_id')
            # Проверяем, не выплачивалось ли уже вознаграждение
            if not referrer.get('reward_paid'):
                # Выплачиваем вознаграждение в зависимости от типа
                if self.reward_type == "subscription_days":
                    # Начисляем дни подписки
                    reward_result = self._add_subscription_days(referrer_id, self.first_level_reward)
                    if reward_result:
                        # Отмечаем выплату вознаграждения
                        db.pay_referral_reward(referrer.get('referral_id'))
                        results.append({
                            "referrer_id": referrer_id,
                            "level": 1,
                            "reward_type": "subscription_days",
                            "reward_value": self.first_level_reward
                        })
        
        # Обрабатываем реферера второго уровня, если включено
        if self.levels >= 2:
            # Ищем реферальную запись второго уровня
            conn = db.pool.get_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT * FROM referrals
                        WHERE user_id = ? AND level = 2
                        """,
                        (user_id,)
                    )
                    second_level_referrer = cursor.fetchone()
                    
                    if second_level_referrer:
                        second_level_referrer_id = second_level_referrer.get('referrer_id')
                        # Проверяем, не выплачивалось ли уже вознаграждение
                        if not second_level_referrer.get('reward_paid'):
                            # Выплачиваем вознаграждение второго уровня
                            if self.reward_type == "subscription_days":
                                reward_result = self._add_subscription_days(second_level_referrer_id, self.second_level_reward)
                                if reward_result:
                                    # Отмечаем выплату вознаграждения
                                    db.pay_referral_reward(second_level_referrer.get('referral_id'))
                                    results.append({
                                        "referrer_id": second_level_referrer_id,
                                        "level": 2,
                                        "reward_type": "subscription_days",
                                        "reward_value": self.second_level_reward
                                    })
                finally:
                    db.pool.release_connection(conn)
        
        return results
    
    def _add_subscription_days(self, user_id: int, days: int) -> bool:
        """
        Добавление дней подписки пользователю
        
        Args:
            user_id: ID пользователя
            days: Количество дней
            
        Returns:
            bool: Успешно ли начислены дни
        """
        # Получаем текущую дату подписки
        current_date = db.get_subscription_date(user_id)
        
        if current_date:
            try:
                # Парсим текущую дату
                date_obj = datetime.strptime(current_date, "%Y-%m-%d %H:%M:%S")
                
                # Если дата в прошлом, начинаем отсчет от текущего момента
                if date_obj < datetime.now():
                    date_obj = datetime.now()
                    
                # Добавляем дни
                from datetime import timedelta
                new_date = date_obj + timedelta(days=days)
                new_date_str = new_date.strftime("%Y-%m-%d %H:%M:%S")
                
                # Обновляем дату в БД
                success = db.update_subscription(user_id, new_date_str)
                
                if success:
                    logger.info(f"Добавлено {days} дней подписки пользователю {user_id}")
                    
                    # Логируем операцию
                    db.log_operation(
                        user_id=user_id,
                        operation_type="referral_reward",
                        target="subscription_days",
                        params=json.dumps({"days": days}),
                        result=new_date_str
                    )
                    
                return success
                
            except Exception as e:
                logger.error(f"Ошибка при добавлении дней подписки пользователю {user_id}: {e}")
                return False
        else:
            # Если у пользователя нет подписки, создаем новую от текущей даты
            new_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            success = db.update_subscription(user_id, new_date)
            
            if success:
                logger.info(f"Создана новая подписка на {days} дней для пользователя {user_id}")
                
                # Логируем операцию
                db.log_operation(
                    user_id=user_id,
                    operation_type="referral_reward",
                    target="subscription_days",
                    params=json.dumps({"days": days}),
                    result=new_date
                )
                
            return success
    
    def get_user_referrals(self, user_id: int) -> Dict[str, Any]:
        """
        Получение статистики рефералов пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Dict[str, Any]: Статистика рефералов
        """
        # Получаем список рефералов первого уровня
        referrals = db.get_user_referrals(user_id)
        
        # Фильтруем по уровням
        first_level = [r for r in referrals if r.get('level') == 1]
        second_level = [r for r in referrals if r.get('level') == 2]
        
        # Считаем выплаченные вознаграждения
        rewarded_first = sum(1 for r in first_level if r.get('reward_paid'))
        rewarded_second = sum(1 for r in second_level if r.get('reward_paid'))
        
        # Формируем общую статистику
        return {
            "total_referrals": len(referrals),
            "first_level": {
                "count": len(first_level),
                "rewarded": rewarded_first,
                "reward_value": self.first_level_reward,
                "reward_type": self.reward_type,
                "referrals": first_level
            },
            "second_level": {
                "count": len(second_level),
                "rewarded": rewarded_second,
                "reward_value": self.second_level_reward,
                "reward_type": self.reward_type,
                "referrals": second_level
            }
        }

# Создаем экземпляр для удобного импорта
referral_manager = ReferralManager() 
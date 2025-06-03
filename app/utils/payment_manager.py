import logging
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any, List, Union
import secrets
import string

from pyCryptoPayAPI import pyCryptoPayAPI

import config
from app.database.db import db

logger = logging.getLogger(__name__)

class PaymentManager:
    """Расширенный менеджер платежей для работы с различными платежными системами"""
    
    def __init__(self, crypto_api_token: str = None):
        """
        Инициализация менеджера платежей
        
        Args:
            crypto_api_token: Токен API CryptoPay
        """
        self.crypto_api_token = crypto_api_token or config.CRYPTO_PAY_API_KEY
        self.payment_systems = {}
        self.initialized_systems = set()
        
        # Инициализируем доступные платежные системы
        self._init_crypto_pay()
        self._init_other_payment_systems()
        
        logger.info(f"Инициализирован расширенный PaymentManager. Доступны системы: {', '.join(self.initialized_systems)}")
    
    def _init_crypto_pay(self):
        """Инициализация CryptoPay API"""
        if not self.crypto_api_token:
            logger.warning("Отсутствует API токен для CryptoPay")
            return
            
        try:
            self.payment_systems['crypto'] = {
                'client': pyCryptoPayAPI(api_token=self.crypto_api_token),
                'name': 'CryptoPay',
                'enabled': True,
                'currencies': [k for k, v in config.SUPPORTED_CRYPTO.items() if v.get('enabled', False)]
            }
            self.initialized_systems.add('crypto')
            logger.info("Инициализирована платежная система CryptoPay")
        except Exception as e:
            logger.error(f"Ошибка инициализации CryptoPay API: {e}")
    
    def _init_other_payment_systems(self):
        """Инициализация других платежных систем"""
        # Инициализация QIWI
        if config.QIWI_API_KEY:
            self.payment_systems['qiwi'] = {
                'name': 'QIWI',
                'enabled': True,
                'currencies': ['RUB', 'USD', 'EUR'],
                'api_key': config.QIWI_API_KEY
            }
            self.initialized_systems.add('qiwi')
            logger.info("Инициализирована платежная система QIWI")
            
        # Инициализация YooMoney
        if config.YOOMONEY_API_KEY:
            self.payment_systems['yoomoney'] = {
                'name': 'YooMoney',
                'enabled': True,
                'currencies': ['RUB'],
                'api_key': config.YOOMONEY_API_KEY
            }
            self.initialized_systems.add('yoomoney')
            logger.info("Инициализирована платежная система YooMoney")
            
        # Инициализация PayPal
        if config.PAYPAL_CLIENT_ID and config.PAYPAL_SECRET:
            self.payment_systems['paypal'] = {
                'name': 'PayPal',
                'enabled': True,
                'currencies': ['USD', 'EUR'],
                'client_id': config.PAYPAL_CLIENT_ID,
                'secret': config.PAYPAL_SECRET
            }
            self.initialized_systems.add('paypal')
            logger.info("Инициализирована платежная система PayPal")
    
    def get_available_payment_methods(self) -> List[Dict[str, Any]]:
        """
        Получение списка доступных методов оплаты
        
        Returns:
            List[Dict[str, Any]]: Список методов оплаты
        """
        result = []
        
        for system_id, system_info in self.payment_systems.items():
            if system_info.get('enabled', False):
                result.append({
                    'id': system_id,
                    'name': system_info.get('name', system_id.capitalize()),
                    'currencies': system_info.get('currencies', [])
                })
                
        return result
    
    def create_invoice(self, amount: float, asset: str = "USDT", 
                      payment_method: str = "crypto", 
                      subscription_plan: str = "basic",
                      user_id: int = None,
                      promo_code: str = None,
                      subscription_days: int = None,
                      description: str = None) -> Dict[str, Any]:
        """
        Создание инвойса для оплаты подписки
        
        Args:
            amount: Сумма платежа
            asset: Валюта платежа (по умолчанию USDT)
            payment_method: Метод оплаты (crypto, qiwi, yoomoney, paypal)
            subscription_plan: Тарифный план (basic, premium, vip)
            user_id: ID пользователя
            promo_code: Промокод
            subscription_days: Количество дней подписки
            description: Описание платежа
            
        Returns:
            Dict[str, Any]: Информация об инвойсе
        """
        # Проверяем доступность метода оплаты
        if payment_method not in self.initialized_systems:
            logger.warning(f"Метод оплаты {payment_method} недоступен")
            return {
                "error": f"Метод оплаты {payment_method} недоступен",
                "pay_url": None,
                "invoice_id": None
            }
            
        # Проверяем валидность валюты для метода оплаты
        payment_system = self.payment_systems.get(payment_method)
        if asset not in payment_system.get('currencies', []):
            logger.warning(f"Валюта {asset} недоступна для метода оплаты {payment_method}")
            return {
                "error": f"Валюта {asset} недоступна для метода оплаты {payment_method}",
                "pay_url": None,
                "invoice_id": None
            }
        
        # Проверяем и применяем промокод
        discount_amount = 0
        referral_id = None
        
        if promo_code and user_id:
            promo_check = db.check_promo_code(promo_code, user_id)
            if promo_check.get("valid", False):
                promo_data = promo_check.get("promo_data", {})
                
                # Применяем процентную скидку
                if promo_data.get("discount_percent"):
                    discount_percent = min(promo_data.get("discount_percent", 0), config.PROMO_SYSTEM.get("max_discount_percent", 50))
                    discount_amount = amount * (discount_percent / 100)
                
                # Применяем фиксированную скидку
                if promo_data.get("discount_fixed"):
                    discount_amount = max(discount_amount, promo_data.get("discount_fixed", 0))
                
                # Проверяем, чтобы скидка не превышала сумму платежа
                discount_amount = min(discount_amount, amount * 0.95)  # Максимальная скидка 95%
                
                # Применяем скидку
                amount = amount - discount_amount
        
        # Проверяем наличие реферала
        if user_id:
            referrer = db.get_referrer(user_id)
            if referrer:
                referral_id = referrer.get("referrer_id")
        
        # Создаем инвойс в зависимости от метода оплаты
        try:
            result = {}
            
            if payment_method == 'crypto':
                client = payment_system.get('client')
                invoice = client.create_invoice(asset=asset, amount=amount, description=description)
                
                result = {
                    "invoice_id": str(invoice.get('invoice_id')),
                    "pay_url": invoice.get('pay_url'),
                    "amount": amount,
                    "asset": asset,
                    "payment_method": payment_method,
                    "subscription_plan": subscription_plan,
                    "promo_code": promo_code,
                    "discount_amount": discount_amount,
                    "referral_id": referral_id
                }
            
            elif payment_method in ['qiwi', 'yoomoney', 'paypal']:
                # Заглушка для других платежных систем
                # В реальном коде здесь была бы интеграция с соответствующими API
                
                # Генерируем уникальный ID инвойса
                invoice_id = f"{payment_method}_{secrets.token_hex(8)}"
                
                result = {
                    "invoice_id": invoice_id,
                    "pay_url": f"https://example.com/pay/{invoice_id}",
                    "amount": amount,
                    "asset": asset,
                    "payment_method": payment_method,
                    "subscription_plan": subscription_plan,
                    "promo_code": promo_code,
                    "discount_amount": discount_amount,
                    "referral_id": referral_id
                }
            
            # Если указан пользователь, записываем платеж в БД
            if user_id and subscription_days:
                payment_id = db.record_payment(
                    user_id=user_id,
                    invoice_id=result.get("invoice_id"),
                    amount=amount,
                    currency=asset,
                    status="pending",
                    subscription_days=subscription_days,
                    payment_method=payment_method,
                    subscription_plan=subscription_plan,
                    promo_code=promo_code,
                    referral_id=referral_id
                )
                result["payment_id"] = payment_id
                
                # Если был использован промокод, отмечаем его использование
                if promo_code and promo_check.get("valid", False):
                    db.use_promo_code(promo_code, user_id, payment_id)
            
            logger.info(f"Создан инвойс на сумму {amount} {asset}, ID: {result.get('invoice_id')}")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка создания инвойса: {e}")
            return {
                "error": str(e),
                "pay_url": None,
                "invoice_id": None
            }
    
    def check_invoice(self, invoice_id: str, payment_method: str = "crypto") -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Проверка статуса инвойса
        
        Args:
            invoice_id: ID инвойса
            payment_method: Метод оплаты
            
        Returns:
            Tuple[bool, Optional[Dict[str, Any]]]: (оплачен, информация об инвойсе)
        """
        # Проверяем доступность метода оплаты
        if payment_method not in self.initialized_systems:
            logger.warning(f"Метод оплаты {payment_method} недоступен")
            return False, None
        
        try:
            # Проверяем статус в зависимости от метода оплаты
            if payment_method == 'crypto':
                client = self.payment_systems.get('crypto', {}).get('client')
                if not client:
                    return False, None
                    
                invoice = client.get_invoice(int(invoice_id))
                is_paid = invoice.get("status") == "paid"
                
                logger.info(f"Проверка инвойса {invoice_id}, статус: {invoice.get('status')}")
                
                if is_paid:
                    # Обновляем статус платежа в БД
                    db.update_payment_status(invoice_id, "paid")
                    
                return is_paid, invoice
                
            elif payment_method in ['qiwi', 'yoomoney', 'paypal']:
                # Заглушка для других платежных систем
                # В реальном коде здесь была бы проверка через соответствующие API
                
                # Для демонстрации предполагаем, что платеж не оплачен
                return False, {"status": "pending", "invoice_id": invoice_id}
                
            return False, None
            
        except Exception as e:
            logger.error(f"Ошибка проверки инвойса {invoice_id}: {e}")
            return False, None
    
    def process_successful_payment(self, invoice_id: str, user_id: int) -> Dict[str, Any]:
        """
        Обработка успешного платежа
        
        Args:
            invoice_id: ID инвойса
            user_id: ID пользователя
            
        Returns:
            Dict[str, Any]: Результат обработки
        """
        try:
            # Получаем информацию о платеже из БД
            conn = db.pool.get_connection()
            if not conn:
                return {"success": False, "error": "database_error"}
                
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM payments
                WHERE invoice_id = ? AND user_id = ?
                """,
                (invoice_id, user_id)
            )
            payment = cursor.fetchone()
            db.pool.release_connection(conn)
            
            if not payment:
                logger.warning(f"Платеж {invoice_id} для пользователя {user_id} не найден")
                return {"success": False, "error": "payment_not_found"}
                
            # Если платеж уже обработан, возвращаем успех
            if payment.get("status") == "processed":
                return {"success": True, "already_processed": True}
                
            # Получаем план подписки
            subscription_plan = payment.get("subscription_plan", "basic")
            subscription_days = payment.get("subscription_days", 0)
            
            # Рассчитываем дату окончания подписки
            end_date = self.calculate_subscription_end_date(subscription_days)
            
            # Создаем подписку
            db.create_user_subscription(
                user_id=user_id,
                subscription_plan=subscription_plan,
                expires_at=end_date,
                payment_id=payment.get("payment_id"),
                auto_renew=False  # По умолчанию без автопродления
            )
            
            # Обновляем статус платежа
            db.update_payment_status(invoice_id, "processed")
            
            # Обрабатываем реферальное вознаграждение
            if payment.get("referral_id") and config.REFERRAL_SYSTEM.get("enabled", False):
                self._process_referral_reward(payment.get("referral_id"), user_id)
            
            logger.info(f"Обработан успешный платеж {invoice_id} для пользователя {user_id}")
            
            return {
                "success": True, 
                "subscription_plan": subscription_plan,
                "subscription_days": subscription_days,
                "expires_at": end_date
            }
            
        except Exception as e:
            logger.error(f"Ошибка при обработке платежа {invoice_id} для пользователя {user_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def _process_referral_reward(self, referrer_id: int, referred_user_id: int) -> bool:
        """
        Обработка реферального вознаграждения
        
        Args:
            referrer_id: ID реферера
            referred_user_id: ID приглашенного пользователя
            
        Returns:
            bool: Успех операции
        """
        try:
            # Получаем информацию о реферальной записи
            conn = db.pool.get_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM referrals
                WHERE user_id = ? AND referrer_id = ?
                """,
                (referred_user_id, referrer_id)
            )
            referral = cursor.fetchone()
            db.pool.release_connection(conn)
            
            if not referral:
                logger.warning(f"Реферальная запись для пользователя {referred_user_id} и реферера {referrer_id} не найдена")
                return False
                
            # Если вознаграждение уже выплачено, пропускаем
            if referral.get("reward_paid", 0):
                return True
                
            # Определяем размер вознаграждения в зависимости от уровня
            reward_days = config.REFERRAL_SYSTEM.get("first_level_reward", 3)
            if referral.get("level", 1) > 1:
                reward_days = config.REFERRAL_SYSTEM.get("second_level_reward", 1)
            
            # Рассчитываем новую дату окончания подписки
            current_subscription = db.get_subscription_date(referrer_id)
            if current_subscription:
                try:
                    current_date = datetime.strptime(current_subscription, "%Y-%m-%d %H:%M:%S")
                    # Если подписка активна, добавляем дни к ней
                    if current_date > datetime.now():
                        new_date = (current_date + timedelta(days=reward_days)).strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        # Если подписка неактивна, считаем от текущего момента
                        new_date = (datetime.now() + timedelta(days=reward_days)).strftime("%Y-%m-%d %H:%M:%S")
                except:
                    # В случае ошибки формата даты, начинаем с текущего момента
                    new_date = (datetime.now() + timedelta(days=reward_days)).strftime("%Y-%m-%d %H:%M:%S")
            else:
                # Если подписки нет, начинаем с текущего момента
                new_date = (datetime.now() + timedelta(days=reward_days)).strftime("%Y-%m-%d %H:%M:%S")
            
            # Обновляем подписку
            db.update_subscription(referrer_id, new_date)
            
            # Отмечаем выплату вознаграждения
            db.pay_referral_reward(referral.get("referral_id"))
            
            # Логируем операцию
            db.log_operation(
                user_id=referrer_id,
                operation_type="referral_reward",
                target=str(referred_user_id),
                params=json.dumps({"reward_days": reward_days}),
                result=new_date
            )
            
            logger.info(f"Выплачено реферальное вознаграждение {reward_days} дней для пользователя {referrer_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при обработке реферального вознаграждения: {e}")
            return False
    
    def calculate_subscription_end_date(self, days: int) -> str:
        """
        Расчет даты окончания подписки
        
        Args:
            days: Количество дней подписки
            
        Returns:
            str: Дата окончания подписки в формате "YYYY-MM-DD HH:MM:SS"
        """
        end_date = datetime.now() + timedelta(days=days)
        return end_date.strftime("%Y-%m-%d %H:%M:%S")
    
    def get_subscription_info(self, days: int, plan: str = "basic") -> Dict[str, Any]:
        """
        Получение информации о подписке
        
        Args:
            days: Количество дней подписки
            plan: Тарифный план
            
        Returns:
            Dict[str, Any]: Информация о подписке
        """
        # Получаем план подписки
        subscription_plan = config.SUBSCRIPTION_PLANS.get(plan, config.SUBSCRIPTION_PLANS.get("basic"))
        
        # Получаем стоимость для указанного количества дней
        days_str = str(days)
        if days_str == "3500":
            days_str = "lifetime"
            
        price = subscription_plan.get("prices", {}).get(days_str, 0)
        
        # Формируем информацию о подписке
        subscription_info = {
            "name": f"{subscription_plan.get('name')} ({days} дней)",
            "description": subscription_plan.get('description', ''),
            "price": price,
            "days": days,
            "plan": plan,
            "features": subscription_plan.get('features', [])
        }
        
        return subscription_info
    
    def generate_promo_code(self, discount_percent: int = 10, 
                          discount_fixed: float = 0, 
                          subscription_days: int = 0,
                          expires_days: int = None,
                          max_usages: int = 1,
                          length: int = 8) -> str:
        """
        Генерация случайного промокода
        
        Args:
            discount_percent: Скидка в процентах
            discount_fixed: Фиксированная скидка
            subscription_days: Количество дней подписки
            expires_days: Срок действия в днях
            max_usages: Максимальное количество использований
            length: Длина промокода
            
        Returns:
            str: Сгенерированный промокод
        """
        # Генерируем случайный код
        alphabet = string.ascii_uppercase + string.digits
        promo_code = ''.join(secrets.choice(alphabet) for _ in range(length))
        
        # Устанавливаем срок действия
        if expires_days is None:
            expires_days = config.PROMO_SYSTEM.get("default_expiry_days", 30)
            
        expires_at = (datetime.now() + timedelta(days=expires_days)).strftime("%Y-%m-%d %H:%M:%S")
        
        # Создаем промокод в БД
        db.create_promo_code(
            promo_code=promo_code,
            discount_percent=discount_percent,
            discount_fixed=discount_fixed,
            subscription_days=subscription_days,
            expires_at=expires_at,
            max_usages=max_usages
        )
        
        logger.info(f"Сгенерирован промокод {promo_code} со скидкой {discount_percent}% и {discount_fixed}$")
        
        return promo_code

# Создаем экземпляр менеджера платежей для использования в других модулях
try:
    payment_manager = PaymentManager()
except Exception as e:
    logger.critical(f"Невозможно инициализировать PaymentManager: {e}")
    payment_manager = None 
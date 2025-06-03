import logging
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional

from pyCryptoPayAPI import pyCryptoPayAPI

import config
from app.database import db

# Настройка логирования
logger = logging.getLogger(__name__)

# Инициализация API для работы с криптоплатежами
crypto = pyCryptoPayAPI(api_token=config.CRYPTO)

def get_subscription_params(subscription_type: str) -> Tuple[str, float, int]:
    """
    Получает параметры подписки по ее типу
    
    Args:
        subscription_type: Тип подписки (1, 2, 3, 4, 5, 6)
    
    Returns:
        Tuple[str, float, int]: (строка с днями, сумма, количество дней)
    """
    if subscription_type == "1":
        return "1", config.subscribe_1_day, 1
    elif subscription_type == "2":
        return "7", config.subscribe_7_days, 7
    elif subscription_type == "3":
        return "14", config.subscribe_14_days, 14
    elif subscription_type == "4":
        return "30", config.subscribe_30_days, 30
    elif subscription_type == "5":
        return "365", config.subscribe_365_days, 365
    elif subscription_type == "6":
        return "3500", config.subscribe_infinity_days, 3500
    else:
        raise ValueError("Неизвестный тип подписки")

def create_invoice(subscription_type: str) -> Dict:
    """
    Создает счет для оплаты подписки
    
    Args:
        subscription_type: Тип подписки
    
    Returns:
        Dict: Информация о созданном счете
    """
    try:
        _, amount, _ = get_subscription_params(subscription_type)
        invoice = crypto.create_invoice(asset='USDT', amount=amount)
        return invoice
    except Exception as e:
        logger.error(f"Ошибка при создании счета: {e}")
        raise

def check_payment(invoice_id: str) -> Optional[Dict]:
    """
    Проверяет статус платежа
    
    Args:
        invoice_id: ID счета
    
    Returns:
        Optional[Dict]: Информация о платеже или None в случае ошибки
    """
    try:
        invoice_data = crypto.get_invoices(invoice_ids=invoice_id)
        if 'items' in invoice_data and len(invoice_data['items']) > 0:
            return invoice_data['items'][0]
        return None
    except Exception as e:
        logger.error(f"Ошибка при проверке платежа: {e}")
        return None

def update_subscription(user_id: int, days: int) -> bool:
    """
    Обновляет подписку пользователя
    
    Args:
        user_id: ID пользователя
        days: Количество дней подписки
    
    Returns:
        bool: True если подписка успешно обновлена, иначе False
    """
    try:
        new_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        return db.update_subscription(user_id, new_date)
    except Exception as e:
        logger.error(f"Ошибка при обновлении подписки пользователя {user_id}: {e}")
        return False 
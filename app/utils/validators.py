import re
import logging
from typing import Tuple, Optional, Union

logger = logging.getLogger(__name__)

def validate_message_url(message_url: str) -> Tuple[bool, Optional[Tuple[str, int]]]:
    """
    Проверяет корректность ссылки на сообщение Telegram
    
    Args:
        message_url: Ссылка на сообщение в формате https://t.me/username/123
        
    Returns:
        Tuple[bool, Optional[Tuple[str, int]]]: (успех, (имя_чата, id_сообщения)) или (неудача, None)
    """
    if not message_url:
        logger.warning(f"Пустая ссылка на сообщение")
        return False, None
        
    # Проверка формата URL
    pattern = r'^https?://t\.me/([a-zA-Z][a-zA-Z0-9_]{3,}|joinchat/[a-zA-Z0-9_-]+)/(\d+)$'
    match = re.match(pattern, message_url)
    
    if not match:
        logger.warning(f"Некорректный формат ссылки: {message_url}")
        return False, None
    
    chat_username = match.group(1)
    
    try:
        message_id = int(match.group(2))
    except ValueError:
        logger.warning(f"Некорректный ID сообщения: {match.group(2)}")
        return False, None
    
    return True, (chat_username, message_id)

def validate_user_id(user_id: Union[str, int]) -> Tuple[bool, Optional[int]]:
    """
    Проверяет корректность ID пользователя Telegram
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Tuple[bool, Optional[int]]: (успех, id) или (неудача, None)
    """
    if not user_id:
        logger.warning("Пустой ID пользователя")
        return False, None
    
    try:
        user_id_int = int(user_id)
        if user_id_int <= 0:
            logger.warning(f"ID пользователя должен быть положительным числом: {user_id}")
            return False, None
        return True, user_id_int
    except (ValueError, TypeError):
        logger.warning(f"Некорректный формат ID пользователя: {user_id}")
        return False, None

def validate_subscription_period(period: str) -> Tuple[bool, Optional[int]]:
    """
    Проверяет корректность периода подписки
    
    Args:
        period: Строка с периодом подписки (1, 7, 14, 30, 365 или "infinity")
        
    Returns:
        Tuple[bool, Optional[int]]: (успех, дни) или (неудача, None)
    """
    valid_periods = {"1": 1, "7": 7, "14": 14, "30": 30, "365": 365, "infinity": 3500}
    
    if not period or period not in valid_periods:
        logger.warning(f"Некорректный период подписки: {period}")
        return False, None
    
    return True, valid_periods[period]

def sanitize_input(text: str) -> str:
    """
    Очищает и экранирует входной текст
    
    Args:
        text: Текст для очистки
        
    Returns:
        str: Очищенный текст
    """
    if not text:
        return ""
    
    # Удаляем потенциально опасные HTML и Markdown символы
    text = re.sub(r'[<>&\'"]', '', text)
    
    # Экранируем специальные символы Markdown
    markdown_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in markdown_chars:
        text = text.replace(char, f'\\{char}')
    
    return text.strip() 
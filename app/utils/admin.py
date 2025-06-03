import logging
from typing import Optional

import config

# Настройка логирования
logger = logging.getLogger(__name__)

def get_admin_level(user_id: int) -> Optional[int]:
    """
    Получает уровень доступа администратора
    
    Args:
        user_id: ID пользователя
    
    Returns:
        Optional[int]: Уровень доступа (1-3) или None, если пользователь не администратор
    """
    return config.ADMINS.get(user_id)

def is_admin(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь администратором любого уровня
    
    Args:
        user_id: ID пользователя
    
    Returns:
        bool: True если пользователь имеет права администратора
    """
    return user_id in config.ADMINS

def has_admin_access(user_id: int, required_level: int) -> bool:
    """
    Проверяет, имеет ли пользователь доступ указанного уровня
    
    Args:
        user_id: ID пользователя
        required_level: Требуемый уровень доступа
    
    Returns:
        bool: True если пользователь имеет нужный уровень доступа
    """
    user_level = get_admin_level(user_id)
    return user_level is not None and user_level >= required_level

def full_access_required(func):
    """
    Декоратор для функций, требующих полного доступа администратора
    """
    def wrapper(message, *args, **kwargs):
        user_id = message.from_user.id if hasattr(message, "from_user") else message.chat.id
        if not has_admin_access(user_id, config.ADMIN_LEVEL_FULL):
            logger.warning(f"Пользователь {user_id} пытался получить доступ к функции, требующей полных прав")
            return
        return func(message, *args, **kwargs)
    return wrapper

def moderator_access_required(func):
    """
    Декоратор для функций, требующих доступа модератора
    """
    def wrapper(message, *args, **kwargs):
        user_id = message.from_user.id if hasattr(message, "from_user") else message.chat.id
        if not has_admin_access(user_id, config.ADMIN_LEVEL_MODERATOR):
            logger.warning(f"Пользователь {user_id} пытался получить доступ к функции модератора")
            return
        return func(message, *args, **kwargs)
    return wrapper

def observer_access_required(func):
    """
    Декоратор для функций, требующих доступа наблюдателя
    """
    def wrapper(message, *args, **kwargs):
        user_id = message.from_user.id if hasattr(message, "from_user") else message.chat.id
        if not has_admin_access(user_id, config.ADMIN_LEVEL_OBSERVER):
            logger.warning(f"Пользователь {user_id} пытался получить доступ к функции наблюдателя")
            return
        return func(message, *args, **kwargs)
    return wrapper 
"""
Инициализация обработчиков команд и сообщений
"""

async def register_user_handlers(bot):
    """
    Регистрация обработчиков пользователя
    
    Args:
        bot: Экземпляр бота
    """
    from app.handlers.user_handlers import UserHandlers
    
    handler = UserHandlers(bot)
    await handler.register_handlers()

async def register_admin_handlers(bot):
    """
    Регистрация обработчиков администратора
    
    Args:
        bot: Экземпляр бота
    """
    from app.handlers.admin_handlers import AdminHandlers
    
    handler = AdminHandlers(bot)
    await handler.register_handlers()

__all__ = ['register_user_handlers', 'register_admin_handlers'] 
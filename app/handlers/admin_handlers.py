import logging
from datetime import datetime, timedelta

from telebot import TeleBot
from telebot import types

import config
from app.database import db
from app.keyboards import (
    create_admin_menu,
    create_back_button,
    create_channel_button,
    create_admin_user_markup
)
from app.utils import update_subscription

# Настройка логирования
logger = logging.getLogger(__name__)

def register_admin_handlers(bot: TeleBot):
    """
    Регистрирует обработчики для административных команд
    
    Args:
        bot: Экземпляр бота
    """
    @bot.message_handler(commands=['admin'])
    def admin(message):
        """Обработчик команды /admin"""
        try:
            user_id = message.chat.id
            
            if user_id in config.ADMINS:
                bot.send_message(
                    user_id, 
                    "⚡️ *ADMIN PANEL* ⚡️",
                    reply_markup=create_admin_menu(), 
                    parse_mode="Markdown"
                )
                logger.info(f"Администратор {user_id} открыл админ-панель")
            else:
                bot.send_message(
                    user_id, 
                    "⚡️ *ADMIN PANEL* ⚡️\n\n_У вас нет прав!_", 
                    parse_mode="Markdown"
                )
                logger.warning(f"Пользователь {user_id} попытался получить доступ к админ-панели")
                
        except Exception as e:
            logger.error(f"Ошибка в обработчике /admin: {e}")
    
    @bot.callback_query_handler(lambda c: c.data == 'add_subsribe')
    def add_subscribe_callback(callback_query: types.CallbackQuery):
        """Обработчик кнопки 'Выдать подписку'"""
        try:
            user_id = callback_query.from_user.id
            
            if user_id not in config.ADMINS:
                bot.send_message(
                    user_id, 
                    "⚡️ *У вас нет прав доступа к этой функции!*", 
                    parse_mode="Markdown"
                )
                return
            
            msg = bot.send_message(
                user_id, 
                '*⚡️  ADD SUBSCRIBE  ⚡️*\n\n*Введите ID:*', 
                parse_mode="Markdown"
            )
            bot.register_next_step_handler(msg, add_subscribe_step1)
            
        except Exception as e:
            logger.error(f"Ошибка в обработчике add_subscribe_callback: {e}")
    
    def add_subscribe_step1(message):
        """Обработчик ввода ID пользователя для выдачи подписки"""
        try:
            admin_id = message.chat.id
            
            if admin_id not in config.ADMINS:
                bot.send_message(
                    admin_id, 
                    "⚡️ *У вас нет прав доступа к этой функции!*", 
                    parse_mode="Markdown"
                )
                return
            
            try:
                user_id = int(message.text)
                
                # Проверяем существование пользователя в базе
                if not db.user_exists(user_id):
                    bot.send_message(
                        admin_id, 
                        f'⚡️ *Ошибка!* Пользователь с ID `{user_id}` не найден.', 
                        parse_mode="Markdown", 
                        reply_markup=create_back_button()
                    )
                    return
                
                msg = bot.send_message(
                    admin_id, 
                    '*✞  ADD SUBSCRIBE  ✞*\n\n*Введите количество дней:*', 
                    parse_mode="Markdown"
                )
                bot.register_next_step_handler(msg, add_subscribe_step2, user_id)
                
            except ValueError:
                bot.send_message(
                    admin_id, 
                    "❌ *Ошибка! Введите корректный ID пользователя (целое число).*", 
                    parse_mode="Markdown"
                )
                
        except Exception as e:
            logger.error(f"Ошибка в обработчике add_subscribe_step1: {e}")
    
    def add_subscribe_step2(message, user_id):
        """Обработчик ввода количества дней подписки"""
        try:
            admin_id = message.chat.id
            
            if admin_id not in config.ADMINS:
                bot.send_message(
                    admin_id, 
                    "⚡️ *У вас нет прав доступа к этой функции!*", 
                    parse_mode="Markdown"
                )
                return
            
            try:
                days = int(message.text)
                
                if days <= 0:
                    bot.send_message(
                        admin_id, 
                        "❌ *Ошибка! Количество дней должно быть положительным числом.*", 
                        parse_mode="Markdown"
                    )
                    return
                
                # Обновляем подписку пользователя
                new_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
                success = db.update_subscription(user_id, new_date)
                
                if success:
                    # Отправляем уведомление пользователю
                    try:
                        bot.send_message(
                            user_id, 
                            f'⚡️ *Ваша подписка обновлена!: действует до* `{new_date}`.', 
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.warning(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
                    
                    # Отправляем уведомление администратору
                    bot.send_message(
                        admin_id, 
                        f'⚡️ *Вы обновили подписку* *(теперь действует до* `{new_date}`*) пользователю:* `{user_id}`', 
                        parse_mode="Markdown", 
                        reply_markup=create_back_button()
                    )
                    
                    # Отправляем уведомление в лог-канал
                    admin_user_markup = create_admin_user_markup(admin_id, user_id)
                    bot.send_message(
                        config.bot_logs, 
                        f'⚡️ *Админ* `{admin_id}`*, обновил подписку (теперь действует до* `{new_date}`*) пользователю* `{user_id}`', 
                        parse_mode="Markdown", 
                        reply_markup=admin_user_markup
                    )
                    
                    logger.info(f"Администратор {admin_id} выдал подписку на {days} дней пользователю {user_id}")
                else:
                    bot.send_message(
                        admin_id, 
                        f'⚡️ *Ошибка при обновлении подписки!*', 
                        parse_mode="Markdown", 
                        reply_markup=create_back_button()
                    )
                    
            except ValueError:
                bot.send_message(
                    admin_id, 
                    "❌ *Ошибка! Введите корректное количество дней (целое число).*", 
                    parse_mode="Markdown"
                )
                
        except Exception as e:
            logger.error(f"Ошибка в обработчике add_subscribe_step2: {e}")
            bot.send_message(
                admin_id, 
                f'⚡️ *Произошла ошибка при обновлении подписки!*', 
                parse_mode="Markdown", 
                reply_markup=create_back_button()
            )
    
    @bot.callback_query_handler(lambda c: c.data == 'clear_subscribe')
    def clear_subscribe_callback(callback_query: types.CallbackQuery):
        """Обработчик кнопки 'Забрать подписку'"""
        try:
            user_id = callback_query.from_user.id
            
            if user_id not in config.ADMINS:
                bot.send_message(
                    user_id, 
                    "⚡️ *У вас нет прав доступа к этой функции!*", 
                    parse_mode="Markdown"
                )
                return
            
            msg = bot.send_message(
                user_id, 
                '*⚡️  CLEAR SUBSCRIBE  ⚡️*\n\n*Введите ID:*', 
                parse_mode="Markdown"
            )
            bot.register_next_step_handler(msg, clear_subscribe_step)
            
        except Exception as e:
            logger.error(f"Ошибка в обработчике clear_subscribe_callback: {e}")
    
    def clear_subscribe_step(message):
        """Обработчик ввода ID пользователя для удаления подписки"""
        try:
            admin_id = message.chat.id
            
            if admin_id not in config.ADMINS:
                bot.send_message(
                    admin_id, 
                    "⚡️ *У вас нет прав доступа к этой функции!*", 
                    parse_mode="Markdown"
                )
                return
            
            try:
                user_id = int(message.text)
                
                # Проверяем существование пользователя в базе
                if not db.user_exists(user_id):
                    bot.send_message(
                        admin_id, 
                        f'⚡️ *Ошибка!* Пользователь с ID `{user_id}` не найден.', 
                        parse_mode="Markdown", 
                        reply_markup=create_back_button()
                    )
                    return
                
                # Сбрасываем подписку пользователя
                success = db.update_subscription(user_id, config.DEFAULT_SUBSCRIBE_DATE)
                
                if success:
                    # Отправляем уведомление пользователю
                    try:
                        bot.send_message(
                            user_id, 
                            f'⚡️ *Ваша подписка аннулирована!*', 
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.warning(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
                    
                    # Отправляем уведомление администратору
                    bot.send_message(
                        admin_id, 
                        f'⚡️ *Вы аннулировали подписку пользователю:* `{user_id}`', 
                        parse_mode="Markdown", 
                        reply_markup=create_back_button()
                    )
                    
                    # Отправляем уведомление в лог-канал
                    admin_user_markup = create_admin_user_markup(admin_id, user_id)
                    bot.send_message(
                        config.bot_logs, 
                        f'⚡️ *Админ* `{admin_id}`* обновил подписку (аннулирована) пользователю* `{user_id}`', 
                        parse_mode="Markdown", 
                        reply_markup=admin_user_markup
                    )
                    
                    logger.info(f"Администратор {admin_id} аннулировал подписку пользователю {user_id}")
                else:
                    bot.send_message(
                        admin_id, 
                        f'⚡️ *Ошибка при аннулировании подписки!*', 
                        parse_mode="Markdown", 
                        reply_markup=create_back_button()
                    )
                    
            except ValueError:
                bot.send_message(
                    admin_id, 
                    "❌ *Ошибка! Введите корректный ID пользователя (целое число).*", 
                    parse_mode="Markdown"
                )
                
        except Exception as e:
            logger.error(f"Ошибка в обработчике clear_subscribe_step: {e}")
            bot.send_message(
                admin_id, 
                f'⚡️ *Произошла ошибка при аннулировании подписки!*', 
                parse_mode="Markdown", 
                reply_markup=create_back_button()
            )
    
    @bot.callback_query_handler(lambda c: c.data == 'send_all')
    def send_all_callback(callback_query: types.CallbackQuery):
        """Обработчик кнопки 'Рассылка'"""
        try:
            user_id = callback_query.from_user.id
            
            if user_id not in config.ADMINS:
                bot.send_message(
                    user_id, 
                    "⚡️ *У вас нет прав доступа к этой функции!*", 
                    parse_mode="Markdown"
                )
                return
            
            msg = bot.send_message(
                user_id, 
                '*⚡️  SEND ALL  ⚡️*\n\n*Введите текст (без картинок, эмодзи тг премиум):*', 
                parse_mode="Markdown"
            )
            bot.register_next_step_handler(msg, send_all_step)
            
        except Exception as e:
            logger.error(f"Ошибка в обработчике send_all_callback: {e}")
    
    def send_all_step(message):
        """Обработчик ввода текста для рассылки"""
        try:
            admin_id = message.chat.id
            
            if admin_id not in config.ADMINS:
                bot.send_message(
                    admin_id, 
                    "⚡️ *У вас нет прав доступа к этой функции!*", 
                    parse_mode="Markdown"
                )
                return
            
            text = message.text
            
            if not text:
                bot.send_message(
                    admin_id, 
                    "❌ *Ошибка! Текст сообщения не может быть пустым.*", 
                    parse_mode="Markdown"
                )
                return
            
            # Начинаем рассылку
            bot.send_message(
                admin_id, 
                f'⚡️ *Рассылка началась!*', 
                parse_mode='Markdown'
            )
            
            # Получаем список всех пользователей
            users = db.get_all_users()
            
            sent_count = 0
            error_count = 0
            
            for user in users:
                user_id = user[0]
                
                try:
                    bot.send_message(
                        user_id, 
                        text, 
                        parse_mode='Markdown', 
                        reply_markup=create_channel_button()
                    )
                    sent_count += 1
                except Exception as e:
                    error_count += 1
                    logger.warning(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
            
            # Отправляем отчет о результатах рассылки
            bot.send_message(
                admin_id, 
                f'⚡️ *Рассылка окончена!*\n\n*Пользователи:* {sent_count}\n*Заблокировали бота:* {error_count}', 
                parse_mode='Markdown', 
                reply_markup=create_back_button()
            )
            
            logger.info(f"Администратор {admin_id} выполнил рассылку. Успешно: {sent_count}, ошибок: {error_count}")
            
        except Exception as e:
            logger.error(f"Ошибка в обработчике send_all_step: {e}")
            bot.send_message(
                admin_id, 
                f'⚡️ *Произошла ошибка при выполнении рассылки!*', 
                parse_mode="Markdown", 
                reply_markup=create_back_button()
            ) 
"""
Обработчики команд администратора
"""
import logging
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union, Callable

from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup

import config
from app.handlers.base_handler import BaseHandler
from app.database.db import db
from app.utils.session_manager import session_manager
from app.utils.localization import i18n
from app.keyboards.ui_keyboards import KeyboardBuilder

logger = logging.getLogger(__name__)

class AdminHandlers(BaseHandler):
    """Обработчик команд администратора"""
    
    def __init__(self, bot: AsyncTeleBot):
        """
        Инициализация обработчика администратора
    
    Args:
        bot: Экземпляр бота
    """
        super().__init__(bot)
        # Словарь состояний администраторов
        self.admin_states = {}
        # Временное хранилище данных для многоэтапных операций
        self.admin_data = {}
        
    async def register_handlers(self):
        """Регистрация обработчиков команд администратора"""
        # Обработчик команды /admin
        self.bot.register_message_handler(
            self.cmd_admin,
            commands=['admin'],
            pass_bot=True
        )
        
        # Обработчик текстовых сообщений (для админских команд)
        self.bot.register_message_handler(
            self.admin_process_message,
            content_types=['text'],
            func=lambda message: self.is_admin_in_state(message.from_user.id),
            pass_bot=True
        )
        
        # Обработчик callback-запросов
        self.bot.register_callback_query_handler(
            self.admin_process_callback,
            func=lambda call: call.data.startswith('admin_'),
            pass_bot=True
        )
        
        logger.info("Зарегистрированы обработчики администратора")
    
    def is_admin_in_state(self, user_id: int) -> bool:
        """
        Проверка, находится ли администратор в каком-либо состоянии
        
        Args:
            user_id: ID пользователя
            
        Returns:
            bool: Находится ли пользователь в админском состоянии
        """
        return user_id in self.admin_states
    
    async def cmd_admin(self, message: Message, bot: AsyncTeleBot):
        """
        Обработчик команды /admin
        
        Args:
            message: Объект сообщения
            bot: Экземпляр бота
        """
        user_id = message.from_user.id
        
        # Проверяем/добавляем пользователя
        await self.check_user(user_id, message)
        
        # Проверяем права администратора
        is_admin = await self.is_admin(user_id)
        
        if not is_admin:
            # Если не админ, игнорируем команду
                return
            
        # Логируем команду
        await self.log_command(user_id, 'admin')
        
        # Получаем уровень доступа админа
        admin_level = config.ADMINS.get(user_id, 0)
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Отправляем панель администратора
        await self.safe_send_message(
            chat_id=user_id,
            text=i18n.get_text("admin_title", lang),
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.admin_menu(admin_level)
        )
    
    async def admin_process_message(self, message: Message, bot: AsyncTeleBot):
        """
        Обработчик текстовых сообщений администратора
        
        Args:
            message: Объект сообщения
            bot: Экземпляр бота
        """
        user_id = message.from_user.id
        text = message.text
        
        # Получаем текущее состояние админа
        state = self.admin_states.get(user_id)
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Обрабатываем состояния
        if state == "add_sub_user_id":
            # Выдача подписки - шаг 1 (ввод ID пользователя)
            try:
                target_user_id = int(text)
                
                # Проверяем существование пользователя
                if not db.user_exists(target_user_id):
                    await self.safe_send_message(
                        chat_id=user_id,
                        text=f"❌ Пользователь с ID {target_user_id} не найден в базе данных",
                        parse_mode="Markdown"
                    )
                    return
                
                # Сохраняем ID пользователя
                self.admin_data[user_id] = {"target_user_id": target_user_id}
                
                # Переходим к следующему шагу
                self.admin_states[user_id] = "add_sub_days"
                
                # Запрашиваем количество дней
                await self.safe_send_message(
                    chat_id=user_id,
                    text=i18n.get_text("admin_add_sub_days", lang),
                    parse_mode="Markdown"
                )
            except ValueError:
                await self.safe_send_message(
                    chat_id=user_id,
                    text="❌ Введите корректный ID пользователя (целое число)",
                    parse_mode="Markdown"
                )
                
        elif state == "add_sub_days":
            # Выдача подписки - шаг 2 (ввод количества дней)
            try:
                days = int(text)
                
                if days <= 0:
                    await self.safe_send_message(
                        chat_id=user_id,
                        text="❌ Количество дней должно быть положительным числом",
                        parse_mode="Markdown"
                    )
                    return
                
                # Получаем данные с предыдущего шага
                target_user_id = self.admin_data.get(user_id, {}).get("target_user_id")
                
                if not target_user_id:
                    await self.safe_send_message(
                        chat_id=user_id,
                        text="❌ Ошибка получения данных. Пожалуйста, начните процесс заново",
                        parse_mode="Markdown"
                    )
                    # Сбрасываем состояние
                    self.admin_states.pop(user_id, None)
                    return
                
                # Обновляем подписку
                new_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
                success = db.update_subscription(target_user_id, new_date)
                
                # Сбрасываем состояние
                self.admin_states.pop(user_id, None)
                self.admin_data.pop(user_id, None)
                
                if success:
                    # Логируем операцию
                    db.log_operation(
                        user_id=user_id,
                        operation_type="admin_add_sub",
                        target=str(target_user_id),
                        params=json.dumps({"days": days, "new_date": new_date}),
                        result="success"
                    )
                    
                    # Отправляем сообщение об успехе
                    await self.safe_send_message(
                        chat_id=user_id,
                        text=i18n.get_text("admin_add_sub_success", lang, target_user_id, new_date),
                        parse_mode="Markdown", 
                        reply_markup=KeyboardBuilder.admin_menu(config.ADMINS.get(user_id, 0))
                    )
                    
                    # Уведомляем пользователя о выдаче подписки
                    try:
                        user_lang = i18n.get_user_language(target_user_id)
                        await self.safe_send_message(
                            chat_id=target_user_id,
                            text=i18n.get_text("subscribe_active", user_lang, new_date),
                            parse_mode="Markdown"
                        )
                    except:
                        logger.warning(f"Не удалось отправить уведомление пользователю {target_user_id}")
                else:
                    await self.safe_send_message(
                        chat_id=user_id,
                        text=f"❌ Ошибка при обновлении подписки для пользователя {target_user_id}",
                        parse_mode="Markdown", 
                        reply_markup=KeyboardBuilder.admin_menu(config.ADMINS.get(user_id, 0))
                    )
                    
            except ValueError:
                await self.safe_send_message(
                    chat_id=user_id,
                    text="❌ Введите корректное количество дней (целое число)",
                    parse_mode="Markdown"
                )
                
        elif state == "remove_sub_user_id":
            # Удаление подписки
            try:
                target_user_id = int(text)
                
                # Проверяем существование пользователя
                if not db.user_exists(target_user_id):
                    await self.safe_send_message(
                        chat_id=user_id,
                        text=f"❌ Пользователь с ID {target_user_id} не найден в базе данных",
                        parse_mode="Markdown"
                    )
                    return
                
                # Обновляем подписку на прошедшую дату
                expired_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
                success = db.update_subscription(target_user_id, expired_date)
                
                # Сбрасываем состояние
                self.admin_states.pop(user_id, None)
                
                if success:
                    # Логируем операцию
                    db.log_operation(
                        user_id=user_id,
                        operation_type="admin_remove_sub",
                        target=str(target_user_id),
                        result="success"
                    )
                    
                    # Отправляем сообщение об успехе
                    await self.safe_send_message(
                        chat_id=user_id,
                        text=i18n.get_text("admin_remove_sub_success", lang, target_user_id),
                        parse_mode="Markdown", 
                        reply_markup=KeyboardBuilder.admin_menu(config.ADMINS.get(user_id, 0))
                    )
                    
                    # Уведомляем пользователя об удалении подписки
                    try:
                        user_lang = i18n.get_user_language(target_user_id)
                        await self.safe_send_message(
                            chat_id=target_user_id,
                            text=i18n.get_text("subscribe_inactive", user_lang),
                            parse_mode="Markdown"
                        )
                    except:
                        logger.warning(f"Не удалось отправить уведомление пользователю {target_user_id}")
                else:
                    await self.safe_send_message(
                        chat_id=user_id,
                        text=f"❌ Ошибка при удалении подписки у пользователя {target_user_id}",
                        parse_mode="Markdown", 
                        reply_markup=KeyboardBuilder.admin_menu(config.ADMINS.get(user_id, 0))
                    )
                    
            except ValueError:
                await self.safe_send_message(
                    chat_id=user_id,
                    text="❌ Введите корректный ID пользователя (целое число)",
                    parse_mode="Markdown"
                )
                
        elif state == "broadcast_text":
            # Рассылка сообщений - шаг 1 (ввод текста)
            if not text:
                await self.safe_send_message(
                    chat_id=user_id,
                    text="❌ Текст сообщения не может быть пустым",
                    parse_mode="Markdown"
                )
                return
                
            # Получаем список всех пользователей
            users = db.get_all_users()
            total_users = len(users)
            
            # Сохраняем данные
            self.admin_data[user_id] = {
                "broadcast_text": text,
                "users": users,
                "total_users": total_users
            }
            
            # Переходим к подтверждению
            self.admin_states[user_id] = "broadcast_confirm"
            
            # Формируем текст для предварительного просмотра
            preview_text = text
            if len(preview_text) > 100:
                preview_text = preview_text[:97] + "..."
                
            # Создаем клавиатуру для подтверждения
            markup = InlineKeyboardMarkup(row_width=2)
            confirm_button = KeyboardBuilder.create_inline_keyboard([
                {"text": "Подтвердить", "callback_data": "admin_broadcast_confirm", "icon": "check"},
                {"text": "Отмена", "callback_data": "admin_broadcast_cancel", "icon": "cross"}
            ])
            
            # Отправляем запрос на подтверждение
            await self.safe_send_message(
                chat_id=user_id,
                text=i18n.get_text("admin_broadcast_confirm", lang, preview_text, total_users),
                parse_mode="Markdown", 
                reply_markup=confirm_button
            )
    
    async def admin_process_callback(self, call: CallbackQuery, bot: AsyncTeleBot):
        """
        Обработчик callback-запросов администратора
        
        Args:
            call: Объект callback
            bot: Экземпляр бота
        """
        user_id = call.from_user.id
        
        # Проверяем права администратора
        is_admin = await self.is_admin(user_id)
        
        if not is_admin:
            # Если не админ, игнорируем callback
            await self.bot.answer_callback_query(
                call.id,
                text="У вас нет прав администратора"
            )
            return
        
        # Получаем уровень доступа админа
        admin_level = config.ADMINS.get(user_id, 0)
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Логируем callback
        await self.log_callback(user_id, call.data)
        
        # Обрабатываем различные callback
        if call.data == "admin_stats":
            # Показываем статистику бота
            await self.show_admin_stats(call)
            
        elif call.data == "admin_users":
            # Показываем список пользователей
            await self.show_user_list(call)
            
        elif call.data == "admin_sessions":
            # Показываем статус сессий
            await self.show_sessions_status(call)
            
        elif call.data == "add_subsribe":
            # Проверяем уровень доступа
            if admin_level < config.ADMIN_LEVEL_MODERATOR:
                await self.bot.answer_callback_query(
                    call.id,
                    text="У вас недостаточно прав для этой операции"
                )
                return
                
            # Начинаем процесс выдачи подписки
            self.admin_states[user_id] = "add_sub_user_id"
            
            # Отправляем запрос на ввод ID пользователя
            await self.safe_edit_message(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=i18n.get_text("admin_add_sub_title", lang),
                parse_mode="Markdown"
            )
            
        elif call.data == "clear_subscribe":
            # Проверяем уровень доступа
            if admin_level < config.ADMIN_LEVEL_MODERATOR:
                await self.bot.answer_callback_query(
                    call.id,
                    text="У вас недостаточно прав для этой операции"
                )
                return
            
            # Начинаем процесс удаления подписки
            self.admin_states[user_id] = "remove_sub_user_id"
            
            # Отправляем запрос на ввод ID пользователя
            await self.safe_edit_message(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=i18n.get_text("admin_remove_sub_title", lang),
                    parse_mode="Markdown"
            )
            
        elif call.data == "send_all":
            # Проверяем уровень доступа
            if admin_level < config.ADMIN_LEVEL_FULL:
                await self.bot.answer_callback_query(
                    call.id,
                    text="У вас недостаточно прав для этой операции"
                )
                return
                
            # Начинаем процесс рассылки
            self.admin_states[user_id] = "broadcast_text"
            
            # Отправляем запрос на ввод текста рассылки
            await self.safe_edit_message(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=i18n.get_text("admin_broadcast_title", lang),
                parse_mode="Markdown"
            )
            
        elif call.data == "check_sessions":
            # Проверяем сессии
            await self.check_sessions(call)
            
        elif call.data == "sessions_stats":
            # Показываем подробную статистику сессий
            await self.show_detailed_sessions_stats(call)
            
        elif call.data == "admin_broadcast_confirm":
            # Подтверждение рассылки
            await self.start_broadcast(call)
            
        elif call.data == "admin_broadcast_cancel":
            # Отмена рассылки
            self.admin_states.pop(user_id, None)
            self.admin_data.pop(user_id, None)
            
            await self.safe_edit_message(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=i18n.get_text("admin_broadcast_canceled", lang),
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.admin_menu(admin_level)
            )
            
        else:
            # Неизвестный callback
            await self.bot.answer_callback_query(
                call.id,
                text="Неизвестная команда"
            )
    
    async def show_admin_stats(self, call: CallbackQuery):
        """
        Показать общую статистику бота
        
        Args:
            call: Объект callback
        """
        user_id = call.from_user.id
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Получаем статистику из БД
        conn = db.pool.get_connection()
        stats = {
            "users_total": 0,
            "active_subs": 0,
            "requests_today": 0,
            "income_today": 0,
            "sessions_valid": 0,
            "sessions_total": 0
        }
        
        if conn:
            try:
                cursor = conn.cursor()
                
                # Общее количество пользователей
                cursor.execute("SELECT COUNT(*) FROM users")
                result = cursor.fetchone()
                stats["users_total"] = result[0] if result else 0
                
                # Количество активных подписок
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM users 
                    WHERE subscribe_date > CURRENT_TIMESTAMP
                    """
                )
                result = cursor.fetchone()
                stats["active_subs"] = result[0] if result else 0
                
                # Количество запросов сегодня
                today = datetime.now().strftime("%Y-%m-%d")
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM operations 
                    WHERE created_at >= ? AND operation_type = 'report'
                    """,
                    (today,)
                )
                result = cursor.fetchone()
                stats["requests_today"] = result[0] if result else 0
                
                # Доход сегодня
                cursor.execute(
                    """
                    SELECT SUM(amount) FROM payments 
                    WHERE created_at >= ? AND status = 'paid'
                    """,
                    (today,)
                )
                result = cursor.fetchone()
                stats["income_today"] = result[0] if result else 0
                
                # Статистика сессий
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM sessions
                    """
                )
                result = cursor.fetchone()
                stats["sessions_total"] = result[0] if result else 0
                
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM sessions 
                    WHERE is_valid = 1
                    """
                )
                result = cursor.fetchone()
                stats["sessions_valid"] = result[0] if result else 0
                
            except Exception as e:
                logger.error(f"Ошибка при получении статистики: {e}")
            finally:
                db.pool.release_connection(conn)
        
        # Вычисляем аптайм бота
        uptime_seconds = (datetime.now() - config.START_TIME).total_seconds()
        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m"
        
        # Формируем текст статистики
        stats_text = i18n.get_text(
            "admin_stats_title", 
            lang,
            stats["users_total"],
            stats["active_subs"],
            stats["requests_today"],
            stats["income_today"],
            stats["sessions_valid"],
            stats["sessions_total"],
            uptime_str
        )
        
        # Отправляем статистику
        await self.safe_edit_message(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=stats_text,
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.back_button()
        )
    
    async def show_user_list(self, call: CallbackQuery):
        """
        Показать список пользователей
        
        Args:
            call: Объект callback
        """
        user_id = call.from_user.id
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Получаем список пользователей
            users = db.get_all_users()
        
        # Формируем текст со списком
        user_list_text = ""
        for i, user in enumerate(users[:20], 1):  # Ограничиваем список 20 пользователями
            username = user.get("username", "")
            username_str = f"@{username}" if username else "No username"
            
            subscribe_date = user.get("subscribe_date", "")
            is_active = False
            if subscribe_date:
                try:
                    sub_date = datetime.strptime(subscribe_date, "%Y-%m-%d %H:%M:%S")
                    is_active = sub_date > datetime.now()
                except:
                    pass
            
            status = "✅" if is_active else "❌"
            
            user_list_text += f"{i}. ID: `{user['user_id']}` | {username_str} | {status}\n"
        
        # Если пользователей больше 20, добавляем примечание
        if len(users) > 20:
            user_list_text += f"\n_...и еще {len(users) - 20} пользователей_"
        
        # Отправляем список
        await self.safe_edit_message(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=i18n.get_text("admin_user_list", lang, user_list_text),
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.back_button()
        )
    
    async def show_sessions_status(self, call: CallbackQuery):
        """
        Показать статус сессий
        
        Args:
            call: Объект callback
        """
        user_id = call.from_user.id
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Получаем статистику сессий
        sessions = await session_manager.get_sessions_status()
        
        # Считаем валидные и невалидные сессии
        valid_count = sum(1 for s in sessions.values() if s.get("is_valid"))
        invalid_count = len(sessions) - valid_count
        
        # Формируем текст
        sessions_text = i18n.get_text(
            "admin_sessions_title",
            lang,
            len(sessions),
            valid_count,
            invalid_count
        )
        
        # Отправляем статистику
        await self.safe_edit_message(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=sessions_text,
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.session_status_menu()
        )
    
    async def check_sessions(self, call: CallbackQuery):
        """
        Запустить проверку сессий
        
        Args:
            call: Объект callback
        """
        user_id = call.from_user.id
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Отправляем сообщение о начале проверки
        await self.safe_edit_message(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=i18n.get_text("admin_checking_sessions", lang),
            parse_mode="Markdown"
        )
        
        # Запускаем проверку сессий
        stats = await session_manager.check_all_sessions()
        
        # Формируем текст результата
        result_text = i18n.get_text(
            "admin_sessions_checked",
            lang,
            stats["total"],
            stats["valid"],
            stats["invalid"]
        )
        
        # Отправляем результат
        await self.safe_edit_message(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=result_text,
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.session_status_menu()
        )
    
    async def show_detailed_sessions_stats(self, call: CallbackQuery):
        """
        Показать подробную статистику сессий
        
        Args:
            call: Объект callback
        """
        user_id = call.from_user.id
        
        # Получаем статус сессий
        sessions_status = await session_manager.get_sessions_status()
        
        # Формируем подробный отчет
        valid_sessions = []
        invalid_sessions = []
        
        for session_id, data in sessions_status.items():
            if data.get("is_valid"):
                valid_sessions.append((session_id, data))
            else:
                invalid_sessions.append((session_id, data))
        
        # Формируем текст отчета
        report = f"📊 *Подробная статистика сессий*\n\n"
        report += f"*Общее количество:* {len(sessions_status)}\n"
        report += f"*Валидных:* {len(valid_sessions)}\n"
        report += f"*Невалидных:* {len(invalid_sessions)}\n\n"
        
        # Добавляем информацию о нескольких невалидных сессиях
        if invalid_sessions:
            report += "*Невалидные сессии (до 5):*\n"
            for i, (session_id, data) in enumerate(invalid_sessions[:5], 1):
                notes = data.get("notes", "")
                error_count = data.get("error_count", 0)
                last_check = data.get("last_check", "")
                
                report += f"{i}. `{session_id[:10]}...` - Ошибок: {error_count}\n"
                if notes:
                    report += f"   _Причина: {notes[:30]}_\n"
        
        # Отправляем отчет
        await self.safe_edit_message(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=report,
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.session_status_menu()
        )
    
    async def start_broadcast(self, call: CallbackQuery):
        """
        Запустить рассылку сообщений
        
        Args:
            call: Объект callback
        """
        user_id = call.from_user.id
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Получаем данные для рассылки
        broadcast_data = self.admin_data.get(user_id, {})
        if not broadcast_data:
            await self.safe_edit_message(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="❌ Ошибка: данные для рассылки не найдены",
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.admin_menu(config.ADMINS.get(user_id, 0))
            )
            return
            
        broadcast_text = broadcast_data.get("broadcast_text", "")
        users = broadcast_data.get("users", [])
        total_users = len(users)
        
        # Сбрасываем состояние
        self.admin_states.pop(user_id, None)
        self.admin_data.pop(user_id, None)
        
        # Отправляем сообщение о начале рассылки
        await self.safe_edit_message(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="⏳ *Выполняется рассылка...*\n\n_Пожалуйста, подождите._",
            parse_mode="Markdown"
        )
        
        # Счетчики успешных и неуспешных отправок
            sent_count = 0
            error_count = 0
            
        # Выполняем рассылку
        for user_data in users:
            target_id = user_data.get("user_id")
            if not target_id:
                continue
                
            try:
                await self.safe_send_message(
                    chat_id=target_id,
                    text=broadcast_text,
                    parse_mode="Markdown"
                    )
                    sent_count += 1
                except Exception as e:
                logger.error(f"Ошибка при отправке сообщения пользователю {target_id}: {e}")
                    error_count += 1
            
            # Добавляем задержку, чтобы не превысить лимиты Telegram
            await asyncio.sleep(0.05)
        
        # Логируем операцию
        db.log_operation(
            user_id=user_id,
            operation_type="broadcast",
            params=json.dumps({"total": total_users, "sent": sent_count, "errors": error_count}),
            result="success"
        )
        
        # Отправляем отчет о завершении
        await self.safe_edit_message(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=i18n.get_text("admin_broadcast_success", lang, sent_count, total_users, error_count),
                parse_mode="Markdown", 
            reply_markup=KeyboardBuilder.admin_menu(config.ADMINS.get(user_id, 0))
            ) 
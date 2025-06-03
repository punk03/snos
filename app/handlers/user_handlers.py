"""
Обработчики команд пользователя
"""
import logging
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union, Callable, Tuple

from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message, CallbackQuery

import config
from app.handlers.base_handler import BaseHandler
from app.database.db import db
from app.utils.session_manager import session_manager
from app.utils.report_manager import report_manager
from app.utils.payment_manager import payment_manager
from app.utils.validators import validate_message_url
from app.utils.localization import i18n
from app.keyboards.ui_keyboards import KeyboardBuilder
from app.utils.promo_manager import promo_manager

logger = logging.getLogger(__name__)

class UserHandlers(BaseHandler):
    """Обработчик команд обычного пользователя"""

    def __init__(self, bot: AsyncTeleBot):
    """
        Инициализация обработчика пользователя
    
    Args:
        bot: Экземпляр бота
    """
        super().__init__(bot)
        # Словарь состояний пользователей
        self.user_states = {}
        # Кулдаун для отправки жалоб
        self.cooldowns = {}
        # Настройки пользователей для отправки жалоб
        self.user_report_settings = {}
        
    async def register_handlers(self):
        """Регистрация обработчиков команд пользователя"""
        # Обработчики команд
        self.bot.register_message_handler(
            self.cmd_start,
            commands=['start'],
            pass_bot=True
        )
        
        self.bot.register_message_handler(
            self.cmd_profile,
            commands=['profile'],
            pass_bot=True
        )
        
        self.bot.register_message_handler(
            self.cmd_shop,
            commands=['shop'],
            pass_bot=True
        )
        
        self.bot.register_message_handler(
            self.cmd_help,
            commands=['help'],
            pass_bot=True
        )
        
        self.bot.register_message_handler(
            self.cmd_settings,
            commands=['settings'],
            pass_bot=True
        )
        
        self.bot.register_message_handler(
            self.cmd_stats,
            commands=['stats'],
            pass_bot=True
        )
        
        # Обработчик текстовых сообщений (для BotNet)
        self.bot.register_message_handler(
            self.process_message,
            content_types=['text'],
            pass_bot=True
        )
        
        # Обработчик callback-запросов
        self.bot.register_callback_query_handler(
            self.process_callback_wrapper,
            func=lambda call: True,
            pass_bot=True
        )
        
        logger.info("Зарегистрированы обработчики пользователя")
    
    async def process_callback_wrapper(self, call: CallbackQuery, bot: AsyncTeleBot):
        """
        Обертка для обработки callback-запросов
        
        Args:
            call: Объект callback
            bot: Экземпляр бота
        """
        # Определяем обработчики для разных callback
        handlers = {
            'profile': self.cb_profile,
            'shop': self.cb_shop,
            'back': self.cb_back,
            'snoser': self.cb_botnet,
            'stats': self.cb_stats,
            'settings': self.cb_settings,
            'settings_language': self.cb_language,
            'lang_': self.cb_set_language,
            'sub_': self.cb_subscription,
            'check_status_': self.cb_check_payment,
            'user_stats': self.cb_user_stats,
            'report_reason_': self.cb_report_reason,
            'intensity_': self.cb_report_intensity,
            'cancel_operation': self.cb_cancel_operation
        }
        
        # Обрабатываем callback
        await self.process_callback(call, handlers)
    
    async def cmd_start(self, message: Message, bot: AsyncTeleBot):
        """
        Обработчик команды /start
        
        Args:
            message: Объект сообщения
            bot: Экземпляр бота
        """
        user_id = message.from_user.id
        
        # Проверяем/добавляем пользователя
        await self.check_user(user_id, message)
        
        # Логируем команду
        await self.log_command(user_id, 'start')
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Отправляем приветственное сообщение
        await self.safe_send_message(
            chat_id=user_id,
            text=i18n.get_text("welcome", lang, name=config.bot_name),
                    parse_mode="Markdown"
                )
            
        # Отправляем главное меню
        await self.safe_send_message(
            chat_id=user_id,
            text=f"♨️ *{config.bot_name}* — _инструмент для массовой отправки жалоб на сообщения._\n\n⚡️ *Админ: {config.bot_admin}*\n⭐️ *Отзывы:* [Reviews]({config.bot_reviews})\n🔥 *Работы:* [Works]({config.bot_works})",
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.main_menu(),
            disable_web_page_preview=True
        )
    
    async def cmd_profile(self, message: Message, bot: AsyncTeleBot):
        """
        Обработчик команды /profile
        
        Args:
            message: Объект сообщения
            bot: Экземпляр бота
        """
        user_id = message.from_user.id
        
        # Проверяем/добавляем пользователя
        await self.check_user(user_id, message)
        
        # Логируем команду
        await self.log_command(user_id, 'profile')
        
        # Получаем данные профиля и отправляем
        await self.show_profile(user_id)
    
    async def cmd_shop(self, message: Message, bot: AsyncTeleBot):
        """
        Обработчик команды /shop
        
        Args:
            message: Объект сообщения
            bot: Экземпляр бота
        """
        user_id = message.from_user.id
        
        # Проверяем/добавляем пользователя
        await self.check_user(user_id, message)
        
        # Логируем команду
        await self.log_command(user_id, 'shop')
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Отправляем меню магазина
        await self.safe_send_message(
            chat_id=user_id,
            text=i18n.get_text("shop_title", lang),
                parse_mode="Markdown", 
            reply_markup=KeyboardBuilder.shop_menu()
        )
    
    async def cmd_help(self, message: Message, bot: AsyncTeleBot):
        """
        Обработчик команды /help
        
        Args:
            message: Объект сообщения
            bot: Экземпляр бота
        """
        user_id = message.from_user.id
        
        # Проверяем/добавляем пользователя
        await self.check_user(user_id, message)
        
        # Логируем команду
        await self.log_command(user_id, 'help')
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Отправляем справку
        help_text = f"""*📚 Справка по использованию бота*

1️⃣ *Что такое {config.bot_name}?*
_{config.bot_name}_ - это инструмент для отправки массовых жалоб на сообщения в Telegram.

2️⃣ *Как пользоваться?*
• Приобретите подписку в разделе "Магазин"
• Перейдите в раздел "BotNet"
• Отправьте ссылку на сообщение в формате `https://t.me/username/123`
• Дождитесь результата обработки

3️⃣ *Основные команды:*
/start - Запустить бота
/profile - Просмотр профиля
/shop - Магазин подписок
/help - Справка
/settings - Настройки

*По всем вопросам обращайтесь:* {config.bot_admin}

*📜 Подробная инструкция:* [Documentation]({config.bot_documentation})
"""
        
        await self.safe_send_message(
            chat_id=user_id,
            text=help_text,
            parse_mode="Markdown",
            disable_web_page_preview=True,
            reply_markup=KeyboardBuilder.back_button()
        )
    
    async def cmd_settings(self, message: Message, bot: AsyncTeleBot):
        """
        Обработчик команды /settings
        
        Args:
            message: Объект сообщения
            bot: Экземпляр бота
        """
        user_id = message.from_user.id
        
        # Проверяем/добавляем пользователя
        await self.check_user(user_id, message)
        
        # Логируем команду
        await self.log_command(user_id, 'settings')
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Отправляем меню настроек
        await self.safe_send_message(
            chat_id=user_id,
            text=i18n.get_text("settings_title", lang),
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.settings_menu()
        )
    
    async def cmd_stats(self, message: Message, bot: AsyncTeleBot):
        """
        Обработчик команды /stats
        
        Args:
            message: Объект сообщения
            bot: Экземпляр бота
        """
        user_id = message.from_user.id
        
        # Проверяем/добавляем пользователя
        await self.check_user(user_id, message)
        
        # Логируем команду
        await self.log_command(user_id, 'stats')
        
        # Показываем статистику
        await self.show_user_stats(user_id)
    
    async def process_message(self, message: Message, bot: AsyncTeleBot):
        """
        Обработчик текстовых сообщений от пользователя
        
        Args:
            message: Объект сообщения
            bot: Экземпляр бота
        """
        user_id = message.from_user.id
        text = message.text
        
        # Проверяем/добавляем пользователя и обновляем активность
        await self.check_user(user_id, message, update_info=True)
        
        # Получаем текущее состояние пользователя
        user_state = self.user_states.get(user_id)
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Если пользователь не в состоянии, это обычное сообщение
        if not user_state:
            return
            
        # Если пользователь в режиме BotNet
        if user_state == "botnet":
            # Проверяем доступность функционала (подписка или промокоды)
            has_access, error_message = await self.check_payment_system(user_id)
            if not has_access:
                await self.safe_send_message(
                    chat_id=user_id,
                    text=error_message,
                    parse_mode="Markdown"
                )
                # Сбрасываем состояние
                self.user_states.pop(user_id, None)
                return
            
            # Проверяем кулдаун
            cooldown = self.cooldowns.get(user_id)
            if cooldown and cooldown > datetime.now():
                # Если кулдаун активен, сообщаем пользователю
                minutes_left = int((cooldown - datetime.now()).total_seconds() // 60) + 1
                await self.safe_send_message(
                    chat_id=user_id,
                    text=i18n.get_text("botnet_cooldown", lang, minutes_left),
                    parse_mode="Markdown",
                    reply_markup=KeyboardBuilder.back_button()
                )
                return
            
            # Проверяем ссылку
            is_valid, message_info = validate_message_url(message.text)
            if not is_valid:
                await self.safe_send_message(
                    chat_id=user_id,
                    text=i18n.get_text("botnet_invalid_url", lang),
                    parse_mode="Markdown"
                )
                return
            
            # Отправляем сообщение о начале процесса
            processing_msg = await self.safe_send_message(
                chat_id=user_id,
                text=i18n.get_text("botnet_processing", lang),
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.cancel_operation_button()
            )
            
            # Получаем настройки отправки для этого пользователя
            user_settings = self.user_report_settings.get(user_id, {})
            report_reason = user_settings.get("reason")
            max_sessions = user_settings.get("max_sessions")
            
            # Запускаем процесс отправки жалоб через улучшенный менеджер
            stats = await report_manager.report_message(
                message_url=message.text,
                user_id=user_id,
                bot=self.bot,
                message_id=processing_msg.message_id,
                report_reason=report_reason,
                max_sessions=max_sessions
            )
            
            # Если включен режим только промокодов, списываем 1 снос
            is_promo_only_mode = promo_manager.is_promo_only_mode()
            if is_promo_only_mode:
                # Списываем 1 снос с баланса пользователя
                promo_manager.use_reports(user_id, 1)
            
            # Проверяем результат
            if stats.get("error"):
                error_code = stats.get("error")
                
                if error_code == "invalid_url":
                    await self.safe_edit_message(
                        chat_id=user_id,
                        message_id=processing_msg.message_id,
                        text=i18n.get_text("botnet_invalid_url", lang),
                        parse_mode="Markdown",
                        reply_markup=KeyboardBuilder.back_button()
                    )
                elif error_code == "no_sessions":
                    await self.safe_edit_message(
                        chat_id=user_id,
                        message_id=processing_msg.message_id,
                        text=i18n.get_text("botnet_no_sessions", lang),
                        parse_mode="Markdown",
                        reply_markup=KeyboardBuilder.back_button()
                    )
                else:
                    await self.safe_edit_message(
                        chat_id=user_id,
                        message_id=processing_msg.message_id,
                        text=i18n.get_text("botnet_error", lang),
                        parse_mode="Markdown",
                        reply_markup=KeyboardBuilder.back_button()
                    )
            else:
                # Устанавливаем кулдаун для пользователя
                cooldown_minutes = config.COOLDOWN_MINUTES
                self.cooldowns[user_id] = datetime.now() + timedelta(minutes=cooldown_minutes)
                
                # Получаем подробную статистику
                valid_reports = stats.get("valid", 0)
                invalid_reports = stats.get("invalid", 0)
                flood_reports = stats.get("flood", 0)
                total_reports = stats.get("total", 0)
                
                # Логируем операцию в базу данных
                db.log_operation(
                    user_id=user_id,
                    operation_type="botnet_report",
                    target=message.text,
                    result=json.dumps(stats)
                )
                
                # Отправляем отчет пользователю
                bot_result_text = i18n.get_text("botnet_result", lang, valid_reports, invalid_reports, flood_reports, total_reports)
                
                # Если пользователь в режиме только промокодов, добавляем информацию об оставшихся сносах
                if is_promo_only_mode:
                    reports_left = promo_manager.check_reports_left(user_id)
                    bot_result_text += "\n\n" + i18n.get_text("botnet_reports_left", lang, reports_left)
                
                await self.safe_edit_message(
                    chat_id=user_id,
                    message_id=processing_msg.message_id,
                    text=bot_result_text,
                    parse_mode="Markdown",
                    reply_markup=KeyboardBuilder.back_button()
                )
            
            # Сбрасываем состояние пользователя
            self.user_states.pop(user_id, None)
    
    async def cb_profile(self, call: CallbackQuery):
        """
        Обработчик callback для профиля
        
        Args:
            call: Объект callback
        """
        user_id = call.from_user.id
        
        # Показываем профиль
        await self.show_profile(user_id)
    
    async def cb_shop(self, call: CallbackQuery):
        """
        Обработчик callback для открытия магазина подписок
        
        Args:
            call: Объект callback
        """
        user_id = call.from_user.id
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Проверяем, не отключена ли система оплаты
        is_payment_disabled = promo_manager.is_payment_disabled()
        
        if is_payment_disabled:
            # Если система оплаты отключена, показываем соответствующее сообщение
            await self.safe_edit_message(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=i18n.get_text("payment_disabled", lang),
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.back_button()
            )
            return
        
        # Отправляем магазин
        await self.safe_edit_message(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=i18n.get_text("shop_title", lang),
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.shop_menu()
        )
    
    async def cb_back(self, call: CallbackQuery):
        """
        Обработчик callback для кнопки "Назад"
        
        Args:
            call: Объект callback
        """
        user_id = call.from_user.id
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Сбрасываем состояние пользователя
        self.user_states.pop(user_id, None)
        
        # Возвращаемся в главное меню
        await self.safe_edit_message(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"♨️ *{config.bot_name}* — _инструмент для массовой отправки жалоб на сообщения._\n\n⚡️ *Админ: {config.bot_admin}*\n⭐️ *Отзывы:* [Reviews]({config.bot_reviews})\n🔥 *Работы:* [Works]({config.bot_works})",
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.main_menu(),
            disable_web_page_preview=True
        )
    
    async def cb_botnet(self, call: CallbackQuery):
        """
        Обработчик callback для BotNet
        
        Args:
            call: Объект callback
        """
        user_id = call.from_user.id
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Проверяем подписку
        subscription_date = db.get_subscription_date(user_id)
        if not subscription_date or datetime.strptime(subscription_date, "%Y-%m-%d %H:%M:%S") < datetime.now():
            await self.safe_edit_message(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=i18n.get_text("botnet_no_subscription", lang),
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.shop_menu()
            )
            return
        
        # Проверяем кулдаун
        cooldown = self.cooldowns.get(user_id)
        if cooldown and cooldown > datetime.now():
            # Если кулдаун активен, сообщаем пользователю
            minutes_left = int((cooldown - datetime.now()).total_seconds() // 60) + 1
            await self.safe_edit_message(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=i18n.get_text("botnet_cooldown", lang, minutes_left),
                            parse_mode="Markdown", 
                reply_markup=KeyboardBuilder.back_button()
            )
            return
        
        # Предлагаем выбрать причину жалобы
        await self.safe_edit_message(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=i18n.get_text("botnet_reason_title", lang),
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.report_reasons_menu()
        )
    
    async def cb_report_reason(self, call: CallbackQuery):
        """
        Обработчик callback для выбора причины жалобы
        
        Args:
            call: Объект callback
        """
        user_id = call.from_user.id
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Извлекаем выбранную причину
        reason = call.data.replace("report_reason_", "")
        
        # Соответствие причин и их названий из конфига
        reason_names = config.REPORT_REASON_NAMES
        
        # Если случайная причина, устанавливаем None (будет выбрана случайно)
        if reason == "random":
            self.user_report_settings[user_id] = {"reason": None}
        else:
            self.user_report_settings[user_id] = {"reason": reason}
        
        # Отправляем сообщение с выбранной причиной
        await self.safe_edit_message(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=i18n.get_text("botnet_reason_selected", lang, reason_names.get(reason, reason)),
                            parse_mode="Markdown", 
            reply_markup=KeyboardBuilder.report_intensity_menu()
        )
    
    async def cb_report_intensity(self, call: CallbackQuery):
        """
        Обработчик callback для выбора интенсивности отправки
        
        Args:
            call: Объект callback
        """
        user_id = call.from_user.id
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Извлекаем выбранную интенсивность
        intensity = call.data.replace("intensity_", "")
        
        # Соответствие интенсивности и их названий
        intensity_names = {
            "max": "Максимальная",
            "high": "Высокая",
            "medium": "Средняя",
            "low": "Низкая"
        }
        
        # Если настройки для пользователя еще не созданы
        if user_id not in self.user_report_settings:
            self.user_report_settings[user_id] = {}
            
        # Устанавливаем интенсивность
        intensity_value = config.REPORT_INTENSITY_LEVELS.get(intensity)
        if intensity_value is None or intensity_value == 1.0:
            # Максимальная интенсивность - все сессии
            self.user_report_settings[user_id]["max_sessions"] = None
                    else:
            # Получаем общее количество сессий
            valid_sessions = await session_manager.get_valid_sessions()
            total_sessions = len(valid_sessions)
            
            # Вычисляем количество сессий для использования
            max_sessions = int(total_sessions * intensity_value)
            self.user_report_settings[user_id]["max_sessions"] = max_sessions
        
        # Устанавливаем состояние пользователя
        self.user_states[user_id] = "botnet"
        
        # Отправляем сообщение с инструкцией
        await self.safe_edit_message(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=i18n.get_text("botnet_intensity_selected", lang, intensity_names.get(intensity, intensity)),
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.back_button()
        )
    
    async def cb_cancel_operation(self, call: CallbackQuery):
        """
        Обработчик callback для отмены операции
        
        Args:
            call: Объект callback
        """
        user_id = call.from_user.id
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Пытаемся отменить операцию
        success = await report_manager.cancel_report(user_id)
        
        if success:
            # Если отмена успешна
            await self.safe_edit_message(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=i18n.get_text("botnet_cancel_success", lang),
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.back_button()
            )
            
            # Сбрасываем состояние и настройки
            self.user_states.pop(user_id, None)
            self.user_report_settings.pop(user_id, {})
                else:
            # Если отмена не удалась
            await self.bot.answer_callback_query(
                call.id,
                text=i18n.get_text("botnet_cancel_error", lang),
                show_alert=True
            )
    
    async def cb_stats(self, call: CallbackQuery):
        """
        Обработчик callback для статистики
        
        Args:
            call: Объект callback
        """
        user_id = call.from_user.id
        
        # Показываем статистику
        await self.show_user_stats(user_id, call.message.message_id)
    
    async def cb_settings(self, call: CallbackQuery):
        """
        Обработчик callback для настроек
        
        Args:
            call: Объект callback
        """
        user_id = call.from_user.id
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Показываем настройки
        await self.safe_edit_message(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=i18n.get_text("settings_title", lang),
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.settings_menu()
        )
    
    async def cb_language(self, call: CallbackQuery):
        """
        Обработчик callback для выбора языка
        
        Args:
            call: Объект callback
        """
        user_id = call.from_user.id
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Показываем меню выбора языка
        await self.safe_edit_message(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=i18n.get_text("language_title", lang),
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.language_menu()
        )
    
    async def cb_set_language(self, call: CallbackQuery):
        """
        Обработчик callback для установки языка
        
        Args:
            call: Объект callback
        """
        user_id = call.from_user.id
        
        # Получаем выбранный язык
        lang_code = call.data.split('_')[1]
        
        # Устанавливаем язык пользователя
        i18n.set_user_language(user_id, lang_code)
        
        # Получаем новый язык
        lang = i18n.get_user_language(user_id)
        
        # Показываем сообщение об успешном изменении
        await self.safe_edit_message(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=i18n.get_text("language_changed", lang),
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.settings_menu()
        )
    
    async def cb_subscription(self, call: CallbackQuery):
        """
        Обработчик callback для выбора подписки
        
        Args:
            call: Объект callback
        """
            user_id = call.from_user.id
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Получаем тип подписки
        subscription_type = call.data.split('_')[1]
        
        # Определяем количество дней и стоимость
        if subscription_type == "1":
            sub_days = "1"
            amount = config.subscribe_1_day
        elif subscription_type == "2":
            sub_days = "7"
            amount = config.subscribe_7_days
        elif subscription_type == "3":
            sub_days = "14"
            amount = config.subscribe_14_days
        elif subscription_type == "4":
            sub_days = "30"
            amount = config.subscribe_30_days
        elif subscription_type == "5":
            sub_days = "365"
            amount = config.subscribe_365_days
        elif subscription_type == "6":
            sub_days = "3500"  # Практически бесконечная подписка
            amount = config.subscribe_infinity_days
        else:
            # Неизвестный тип подписки
            await self.bot.answer_callback_query(
                call.id,
                text="Неизвестный тип подписки"
            )
            return
        
        # Создаем инвойс для оплаты
        if payment_manager:
            invoice = payment_manager.create_invoice(amount=amount, asset='USDT')
            
            if invoice.get("error"):
                # Ошибка при создании инвойса
                await self.safe_edit_message(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=i18n.get_text("error", lang, invoice["error"]),
                    parse_mode="Markdown",
                    reply_markup=KeyboardBuilder.back_button()
                )
                return
                
            # Получаем данные инвойса
            pay_url = invoice['pay_url']
            invoice_id = invoice['invoice_id']
            
            # Отправляем информацию об оплате
            await self.safe_edit_message(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=i18n.get_text("payment_title", lang, sub_days, amount),
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.payment_keyboard(
                    pay_url=pay_url,
                    invoice_id=invoice_id,
                    subscription_type=subscription_type,
                    sub_days=sub_days
                )
            )
            
            # Логируем создание инвойса
            db.log_operation(
                user_id=user_id,
                operation_type="create_invoice",
                target=f"sub_{subscription_type}",
                params=json.dumps({
                    "amount": amount,
                    "days": sub_days,
                    "invoice_id": invoice_id
                })
            )
            
            # Записываем информацию о платеже
            db.record_payment(
                user_id=user_id,
                invoice_id=str(invoice_id),
                amount=amount,
                currency="USDT",
                status="pending",
                subscription_days=int(sub_days)
                        )
                    else:
            # Сервис оплаты недоступен
            await self.safe_edit_message(
                                chat_id=call.message.chat.id, 
                                message_id=call.message.message_id,
                text=i18n.get_text("error", lang, "Сервис оплаты временно недоступен"),
                                parse_mode="Markdown", 
                reply_markup=KeyboardBuilder.back_button()
            )
    
    async def cb_check_payment(self, call: CallbackQuery):
        """
        Обработчик callback для проверки оплаты
        
        Args:
            call: Объект callback
        """
        user_id = call.from_user.id
        
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Получаем данные из callback
        parts = call.data.split('_')
        if len(parts) < 5:
            await self.bot.answer_callback_query(
                call.id,
                text="Неверный формат данных"
                            )
                            return
                        
        invoice_id = parts[2]
        subscription_type = parts[3]
        sub_days = parts[4]
        
        # Отправляем сообщение о проверке
        await self.safe_edit_message(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=i18n.get_text("payment_checking", lang),
                            parse_mode="Markdown"
                        )
        
        # Проверяем оплату
        if payment_manager:
            is_paid, invoice_data = payment_manager.check_invoice(int(invoice_id))
            
            if is_paid:
                # Если оплачено, обновляем подписку
                new_date = payment_manager.calculate_subscription_end_date(int(sub_days))
                db.update_subscription(user_id, new_date)
                
                # Обновляем статус платежа
                db.update_payment_status(invoice_id, "paid")
                
                # Логируем успешную оплату
                db.log_operation(
                    user_id=user_id,
                    operation_type="payment_success",
                    target=invoice_id,
                    result=new_date
                )
                
                # Отправляем сообщение об успешной оплате
                await self.safe_edit_message(
                        chat_id=call.message.chat.id, 
                        message_id=call.message.message_id,
                    text=i18n.get_text("payment_success", lang, new_date),
                        parse_mode="Markdown", 
                    reply_markup=KeyboardBuilder.main_menu()
                )
            else:
                # Если не оплачено
                await self.safe_edit_message(
                        chat_id=call.message.chat.id, 
                        message_id=call.message.message_id,
                    text=i18n.get_text("payment_error", lang),
                        parse_mode="Markdown", 
                    reply_markup=KeyboardBuilder.payment_keyboard(
                        pay_url=invoice_data.get('pay_url', '#') if invoice_data else '#',
                        invoice_id=invoice_id,
                        subscription_type=subscription_type,
                        sub_days=sub_days
                    )
                )
        else:
            # Сервис оплаты недоступен
            await self.safe_edit_message(
                        chat_id=call.message.chat.id, 
                        message_id=call.message.message_id, 
                text=i18n.get_text("error", lang, "Сервис оплаты временно недоступен"),
                        parse_mode="Markdown", 
                reply_markup=KeyboardBuilder.back_button()
            )
    
    async def cb_user_stats(self, call: CallbackQuery):
        """
        Обработчик callback для статистики пользователя
        
        Args:
            call: Объект callback
        """
        user_id = call.from_user.id
        
        # Показываем статистику
        await self.show_user_stats(user_id, call.message.message_id)
    
    async def show_profile(self, user_id: int, message_id: Optional[int] = None):
        """
        Показ профиля пользователя
        
        Args:
            user_id: ID пользователя
            message_id: ID сообщения для редактирования (опционально)
        """
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Получаем данные пользователя
        user_data = db.get_user(user_id)
        
        if not user_data:
            # Если пользователь не найден, добавляем его
            db.add_user(user_id)
            user_data = db.get_user(user_id)
        
        # Формируем имя пользователя
        user_name = user_data.get("first_name", "")
        if user_data.get("last_name"):
            user_name += f" {user_data['last_name']}"
        if not user_name and user_data.get("username"):
            user_name = f"@{user_data['username']}"
        if not user_name:
            user_name = str(user_id)
        
        # Проверяем активность подписки
        subscription_date = user_data.get("subscribe_date")
        is_active = False
        
        if subscription_date:
            try:
                sub_date = datetime.strptime(subscription_date, "%Y-%m-%d %H:%M:%S")
                is_active = sub_date > datetime.now()
            except:
                pass
        
        # Формируем статус подписки
        status = i18n.get_text("active_subscribe", lang) if is_active else i18n.get_text("inactive_subscribe", lang)
        
        # Формируем текст профиля
        profile_text = i18n.get_text("profile", lang, 
                                    user_id, user_name, subscription_date, status)
        
        # Добавляем информацию о подписке
        if is_active:
            profile_text += "\n\n" + i18n.get_text("subscribe_active", lang, subscription_date)
        else:
            profile_text += "\n\n" + i18n.get_text("subscribe_inactive", lang)
        
        # Отправляем или редактируем сообщение
        if message_id:
            await self.safe_edit_message(
                chat_id=user_id,
                message_id=message_id,
                text=profile_text,
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.user_profile_menu(is_active)
            )
        else:
            await self.safe_send_message(
                chat_id=user_id,
                text=profile_text,
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.user_profile_menu(is_active)
            )
    
    async def show_user_stats(self, user_id: int, message_id: Optional[int] = None):
        """
        Показ статистики пользователя
        
        Args:
            user_id: ID пользователя
            message_id: ID сообщения для редактирования (опционально)
        """
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Получаем данные пользователя
        user_data = db.get_user(user_id)
        
        if not user_data:
            # Если пользователь не найден
            return
        
        # Получаем статистику операций
        conn = db.pool.get_connection()
        stats = {"views": 0, "reports": 0, "success": 0, "last_activity": user_data.get("last_activity", "")}
        
        if conn:
            try:
                cursor = conn.cursor()
                
                # Получаем количество просмотров
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM operations 
                    WHERE user_id = ? AND operation_type = 'command'
                    """,
                    (user_id,)
                )
                result = cursor.fetchone()
                stats["views"] = result[0] if result else 0
                
                # Получаем количество отправленных жалоб
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM operations 
                    WHERE user_id = ? AND operation_type = 'report'
                    """,
                    (user_id,)
                )
                result = cursor.fetchone()
                stats["reports"] = result[0] if result else 0
                
                # Получаем количество успешных жалоб
                cursor.execute(
                    """
                    SELECT result FROM operations 
                    WHERE user_id = ? AND operation_type = 'report_result'
                    """,
                    (user_id,)
                )
                results = cursor.fetchall()
                
                for row in results:
                    try:
                        result_data = json.loads(row[0])
                        stats["success"] += result_data.get("valid", 0)
                    except:
                        pass
                
        except Exception as e:
                logger.error(f"Ошибка при получении статистики пользователя {user_id}: {e}")
            finally:
                db.pool.release_connection(conn)
        
        # Формируем текст статистики
        stats_text = i18n.get_text("stats_title", lang, 
                                  stats["views"], stats["reports"], 
                                  stats["success"], stats["last_activity"])
        
        # Отправляем или редактируем сообщение
        if message_id:
            await self.safe_edit_message(
                chat_id=user_id,
                message_id=message_id,
                text=stats_text,
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.back_button()
            )
        else:
            await self.safe_send_message(
                chat_id=user_id,
                text=stats_text,
                parse_mode="Markdown", 
                reply_markup=KeyboardBuilder.back_button()
            )

    async def check_user_subscription(self, user_id: int) -> bool:
        """
        Проверка подписки пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            bool: Активна ли подписка
        """
        # Получаем дату подписки
        subscription_date = db.get_subscription_date(user_id)
        if not subscription_date:
            return False
            
        # Проверяем, не истекла ли подписка
        try:
            sub_date = datetime.strptime(subscription_date, "%Y-%m-%d %H:%M:%S")
            return sub_date > datetime.now()
        except:
            return False

    async def check_payment_system(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """
        Проверка доступа к функционалу в зависимости от режима работы системы
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Tuple[bool, Optional[str]]: (Есть ли доступ, Сообщение об ошибке)
        """
        # Получаем язык пользователя
        lang = i18n.get_user_language(user_id)
        
        # Проверяем режим работы системы - только через промокоды
        is_promo_only_mode = promo_manager.is_promo_only_mode()
        
        if is_promo_only_mode:
            # Проверяем количество доступных сносов у пользователя
            reports_left = promo_manager.check_reports_left(user_id)
            
            if reports_left <= 0:
                # У пользователя нет доступных сносов
                return False, i18n.get_text("botnet_no_reports_left", lang)
            
            return True, None
        else:
            # Проверяем подписку в обычном режиме
            has_subscription = await self.check_user_subscription(user_id)
            if not has_subscription:
                return False, i18n.get_text("botnet_no_subscription", lang)
            
            return True, None 
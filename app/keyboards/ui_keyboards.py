"""
Модуль для создания пользовательских клавиатур с единым дизайном
"""
import logging
from typing import List, Dict, Any, Optional, Union, Tuple

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telebot.types import KeyboardButton

import config

logger = logging.getLogger(__name__)

# Символы для визуального оформления
ICONS = {
    "profile": "👤",
    "help": "📚",
    "info": "ℹ️",
    "shop": "🛒",
    "settings": "⚙️",
    "bot": "🤖",
    "channel": "📢",
    "stats": "📊",
    "admin": "👑",
    "back": "◀️",
    "next": "▶️",
    "up": "🔼",
    "down": "🔽",
    "plus": "➕",
    "minus": "➖",
    "check": "✅",
    "cross": "❌",
    "warning": "⚠️",
    "money": "💰",
    "pay": "💳",
    "time": "⏱",
    "premium": "⭐️",
    "ok": "✓",
    "link": "🔗",
    "report": "🚨",
    "success": "🟢",
    "error": "🔴",
    "neutral": "⚪️",
}

# Настройки внешнего вида клавиатур
UI_SETTINGS = {
    "row_width": 2,  # Ширина строки клавиатуры по умолчанию
    "button_prefix": "",  # Префикс для кнопок (можно добавить пробел для отступа)
    "button_suffix": "",  # Суффикс для кнопок
}

class KeyboardBuilder:
    """Класс для создания клавиатур с единым стилем"""
    
    @staticmethod
    def create_inline_keyboard(
        buttons: List[Dict[str, Any]], 
        row_width: int = UI_SETTINGS["row_width"]
    ) -> InlineKeyboardMarkup:
        """
        Создание inline-клавиатуры
        
        Args:
            buttons: Список словарей с параметрами кнопок
                - text: Текст кнопки
                - callback_data: Данные callback (опционально)
                - url: URL для кнопки-ссылки (опционально)
                - icon: Иконка для кнопки (опционально)
            row_width: Ширина строки клавиатуры
            
        Returns:
            InlineKeyboardMarkup: Готовая клавиатура
        """
        markup = InlineKeyboardMarkup(row_width=row_width)
        
        keyboard_buttons = []
        for button in buttons:
            text = button.get("text", "")
            callback_data = button.get("callback_data")
            url = button.get("url")
            icon = button.get("icon")
            
            # Добавляем иконку, если указана
            if icon and icon in ICONS:
                text = f"{ICONS[icon]} {text}"
            
            # Создаем кнопку в зависимости от типа
            if url:
                keyboard_buttons.append(InlineKeyboardButton(
                    text=f"{UI_SETTINGS['button_prefix']}{text}{UI_SETTINGS['button_suffix']}", 
                    url=url
                ))
            elif callback_data:
                keyboard_buttons.append(InlineKeyboardButton(
                    text=f"{UI_SETTINGS['button_prefix']}{text}{UI_SETTINGS['button_suffix']}", 
                    callback_data=callback_data
                ))
        
        # Добавляем кнопки в клавиатуру
        markup.add(*keyboard_buttons)
        return markup
    
    @staticmethod
    def create_reply_keyboard(
        buttons: List[Union[str, Dict[str, Any]]],
        row_width: int = UI_SETTINGS["row_width"],
        resize_keyboard: bool = True,
        one_time_keyboard: bool = False,
        selective: bool = False
    ) -> ReplyKeyboardMarkup:
        """
        Создание обычной клавиатуры
        
        Args:
            buttons: Список строк или словарей с параметрами кнопок
                - text: Текст кнопки
                - request_contact: Запрос контакта (опционально)
                - request_location: Запрос локации (опционально)
                - icon: Иконка для кнопки (опционально)
            row_width: Ширина строки клавиатуры
            resize_keyboard: Подгонять размер клавиатуры под экран
            one_time_keyboard: Скрывать клавиатуру после использования
            selective: Показывать клавиатуру только определенным пользователям
            
        Returns:
            ReplyKeyboardMarkup: Готовая клавиатура
        """
        markup = ReplyKeyboardMarkup(
            row_width=row_width,
            resize_keyboard=resize_keyboard,
            one_time_keyboard=one_time_keyboard,
            selective=selective
        )
        
        keyboard_buttons = []
        for button in buttons:
            if isinstance(button, str):
                # Если передана просто строка
                keyboard_buttons.append(KeyboardButton(button))
            else:
                # Если передан словарь с параметрами
                text = button.get("text", "")
                request_contact = button.get("request_contact", False)
                request_location = button.get("request_location", False)
                icon = button.get("icon")
                
                # Добавляем иконку, если указана
                if icon and icon in ICONS:
                    text = f"{ICONS[icon]} {text}"
                
                keyboard_buttons.append(KeyboardButton(
                    text=text,
                    request_contact=request_contact,
                    request_location=request_location
                ))
        
        # Добавляем кнопки в клавиатуру
        markup.add(*keyboard_buttons)
        return markup
    
    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """Создание главного меню бота"""
        buttons = [
            {"text": "Профиль", "callback_data": "profile", "icon": "profile"},
            {"text": "Инструкция", "url": config.bot_documentation, "icon": "help"},
            {"text": "Магазин", "callback_data": "shop", "icon": "shop"},
            {"text": "BotNet", "callback_data": "snoser", "icon": "bot"},
            {"text": "Статистика", "callback_data": "stats", "icon": "stats"},
            {"text": "Настройки", "callback_data": "settings", "icon": "settings"},
            {"text": "Канал", "url": config.bot_channel_link, "icon": "channel"},
        ]
        return KeyboardBuilder.create_inline_keyboard(buttons, row_width=2)
    
    @staticmethod
    def back_button() -> InlineKeyboardMarkup:
        """Создание кнопки 'Назад'"""
        buttons = [
            {"text": "Назад", "callback_data": "back", "icon": "back"},
        ]
        return KeyboardBuilder.create_inline_keyboard(buttons)
    
    @staticmethod
    def shop_menu() -> InlineKeyboardMarkup:
        """Создание меню магазина подписок"""
        buttons = [
            {"text": f"1 день - {config.subscribe_1_day}$", "callback_data": "sub_1", "icon": "premium"},
            {"text": f"7 дней - {config.subscribe_7_days}$", "callback_data": "sub_2", "icon": "premium"},
            {"text": f"30 дней - {config.subscribe_30_days}$", "callback_data": "sub_4", "icon": "premium"},
            {"text": f"Навсегда - {config.subscribe_infinity_days}$", "callback_data": "sub_6", "icon": "premium"},
            {"text": "Назад", "callback_data": "back", "icon": "back"},
        ]
        return KeyboardBuilder.create_inline_keyboard(buttons, row_width=2)
    
    @staticmethod
    def admin_menu(admin_level: int) -> InlineKeyboardMarkup:
        """
        Создание меню администратора в зависимости от уровня доступа
        
        Args:
            admin_level: Уровень доступа администратора
            
        Returns:
            InlineKeyboardMarkup: Клавиатура с доступными функциями
        """
        buttons = []
        
        # Наблюдатель (уровень 1) и выше
        if admin_level >= config.ADMIN_LEVEL_OBSERVER:
            buttons.extend([
                {"text": "Статистика", "callback_data": "admin_stats", "icon": "stats"},
                {"text": "Список пользователей", "callback_data": "admin_users", "icon": "profile"},
                {"text": "Проверка сессий", "callback_data": "admin_sessions", "icon": "check"},
            ])
        
        # Модератор (уровень 2) и выше
        if admin_level >= config.ADMIN_LEVEL_MODERATOR:
            buttons.extend([
                {"text": "Выдать подписку", "callback_data": "add_subsribe", "icon": "plus"},
                {"text": "Забрать подписку", "callback_data": "clear_subscribe", "icon": "minus"},
                {"text": "Промокоды", "callback_data": "admin_promos", "icon": "gift"},
            ])
        
        # Полный админ (уровень 3)
        if admin_level >= config.ADMIN_LEVEL_FULL:
            buttons.extend([
                {"text": "Рассылка", "callback_data": "send_all", "icon": "channel"},
                {"text": "Управление админами", "callback_data": "admin_manage", "icon": "admin"},
                {"text": "Настройки системы", "callback_data": "admin_settings", "icon": "settings"},
            ])
            
        # Кнопка возврата в главное меню
        buttons.append({"text": "Главное меню", "callback_data": "back", "icon": "back"})
        
        return KeyboardBuilder.create_inline_keyboard(buttons, row_width=2)
    
    @staticmethod
    def payment_keyboard(pay_url: str, invoice_id: str, subscription_type: str, sub_days: str) -> InlineKeyboardMarkup:
        """
        Создание клавиатуры для оплаты
        
        Args:
            pay_url: URL для оплаты
            invoice_id: ID инвойса
            subscription_type: Тип подписки
            sub_days: Количество дней подписки
            
        Returns:
            InlineKeyboardMarkup: Клавиатура для оплаты
        """
        buttons = [
            {"text": "Оплатить", "url": pay_url, "icon": "pay"},
            {"text": "Проверить оплату", "callback_data": f"check_status_{invoice_id}_{subscription_type}_{sub_days}", "icon": "check"},
            {"text": "Отмена", "callback_data": "back", "icon": "cross"},
        ]
        return KeyboardBuilder.create_inline_keyboard(buttons, row_width=2)
    
    @staticmethod
    def user_profile_menu(subscribe_active: bool = False) -> InlineKeyboardMarkup:
        """
        Создание меню профиля пользователя
        
        Args:
            subscribe_active: Активна ли подписка
            
        Returns:
            InlineKeyboardMarkup: Клавиатура профиля
        """
        buttons = [
            {"text": "Моя статистика", "callback_data": "user_stats", "icon": "stats"},
        ]
        
        # Если подписка не активна, добавляем кнопку покупки
        if not subscribe_active:
            buttons.append({"text": "Купить подписку", "callback_data": "shop", "icon": "shop"})
        
        # Добавляем кнопку возврата
        buttons.append({"text": "Назад", "callback_data": "back", "icon": "back"})
        
        return KeyboardBuilder.create_inline_keyboard(buttons, row_width=1)
    
    @staticmethod
    def settings_menu() -> InlineKeyboardMarkup:
        """Создание меню настроек"""
        buttons = [
            {"text": "Уведомления", "callback_data": "settings_notifications", "icon": "info"},
            {"text": "Язык", "callback_data": "settings_language", "icon": "settings"},
            {"text": "Назад", "callback_data": "back", "icon": "back"},
        ]
        return KeyboardBuilder.create_inline_keyboard(buttons, row_width=2)
    
    @staticmethod
    def session_status_menu() -> InlineKeyboardMarkup:
        """Создание меню статуса сессий"""
        buttons = [
            {"text": "Проверить сессии", "callback_data": "check_sessions", "icon": "check"},
            {"text": "Показать статистику", "callback_data": "sessions_stats", "icon": "stats"},
            {"text": "Назад", "callback_data": "back", "icon": "back"},
        ]
        return KeyboardBuilder.create_inline_keyboard(buttons, row_width=1)
    
    @staticmethod
    def language_menu() -> InlineKeyboardMarkup:
        """Создание меню выбора языка"""
        buttons = [
            {"text": "Русский 🇷🇺", "callback_data": "lang_ru"},
            {"text": "English 🇬🇧", "callback_data": "lang_en"},
            {"text": "Назад", "callback_data": "back", "icon": "back"},
        ]
        return KeyboardBuilder.create_inline_keyboard(buttons, row_width=2)
        
    @staticmethod
    def report_reasons_menu() -> InlineKeyboardMarkup:
        """Создание меню выбора причины жалобы"""
        buttons = []
        
        # Добавляем кнопки для всех причин из конфига
        for reason, name in config.REPORT_REASON_NAMES.items():
            buttons.append({
                "text": name,
                "callback_data": f"report_reason_{reason}",
                "icon": "warning"
            })
        
        # Добавляем кнопку случайной причины
        buttons.append({
            "text": "Случайная причина",
            "callback_data": "report_reason_random",
            "icon": "warning"
        })
        
        # Добавляем кнопку возврата
        buttons.append({
            "text": "Назад",
            "callback_data": "back",
            "icon": "back"
        })
        
        return KeyboardBuilder.create_inline_keyboard(buttons, row_width=2)
        
    @staticmethod
    def report_intensity_menu() -> InlineKeyboardMarkup:
        """Создание меню выбора интенсивности отправки жалоб"""
        buttons = [
            {"text": "🔥 Максимальная (все сессии)", "callback_data": "intensity_max"},
            {"text": "⚡ Высокая (75% сессий)", "callback_data": "intensity_high"},
            {"text": "⚙️ Средняя (50% сессий)", "callback_data": "intensity_medium"},
            {"text": "🔋 Низкая (25% сессий)", "callback_data": "intensity_low"},
            {"text": "Назад", "callback_data": "back", "icon": "back"},
        ]
        return KeyboardBuilder.create_inline_keyboard(buttons, row_width=1)
        
    @staticmethod
    def cancel_operation_button() -> InlineKeyboardMarkup:
        """Создание кнопки отмены операции"""
        buttons = [
            {"text": "Отменить операцию", "callback_data": "cancel_operation", "icon": "cross"},
        ]
        return KeyboardBuilder.create_inline_keyboard(buttons, row_width=1) 
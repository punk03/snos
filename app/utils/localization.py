"""
Модуль для локализации текстов интерфейса
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class LocalizationManager:
    """Менеджер для работы с локализацией текстов"""
    
    def __init__(self):
        """Инициализация менеджера локализации"""
        # Поддерживаемые языки
        self.supported_languages = ["ru", "en"]
        
        # Словари с локализованными текстами
        self.texts = {
            # Русский язык (основной)
            "ru": {
                # Общие тексты
                "welcome": "Добро пожаловать в BotNet - бот для массовой отправки жалоб на сообщения в Telegram!",
                "menu": "Главное меню:",
                "help": "Отправьте ссылку на сообщение, чтобы начать отправку жалоб.",
                "error": "Ошибка: {}",
                "success": "Успешно!",
                "cancel": "Отменено",
                "back": "Назад",
                "next": "Далее",
                "confirm": "Подтвердить",
                
                # Тексты связанные с подписками
                "subscription_expired": "Ваша подписка истекла. Пожалуйста, продлите её, чтобы продолжить пользоваться ботом.",
                "subscription_active": "Ваша подписка активна до {}",
                "subscription_buy": "Купить подписку",
                "subscription_renew": "Продлить подписку",
                "subscription_plan": "Тарифный план: {}",
                
                # Тексты для статистики
                "stats_title": "📊 Общая статистика",
                "stats_week_title": "📊 Статистика за неделю",
                "stats_month_title": "📊 Статистика за месяц",
                "stats_views": "Просмотры",
                "stats_reports_sent": "Отправлено жалоб",
                "stats_report_results": "Результаты жалоб",
                "stats_successful": "Успешных",
                "stats_failed": "Неудачных",
                "stats_flood": "Флуд",
                "stats_effectiveness": "Эффективность",
                "stats_last_activity": "Последняя активность",
                
                # Тексты для планировщика
                "scheduler_title": "🕒 Планировщик задач",
                "scheduler_new_task": "Создать новую задачу",
                "scheduler_my_tasks": "Мои задачи",
                "scheduler_no_tasks": "У вас нет запланированных задач",
                "scheduler_task_created": "Задача создана и будет выполнена в {}",
                "scheduler_task_cancelled": "Задача отменена",
                "scheduler_select_time": "Выберите время выполнения:",
                "scheduler_select_repeat": "Выберите интервал повторения:",
                "scheduler_select_reason": "Выберите причину жалобы:",
                
                # Тексты для аналитики
                "analytics_title": "📈 Аналитика",
                "analytics_period": "Период: {} дней",
                "analytics_total_reports": "Всего отправлено жалоб: {}",
                "analytics_effectiveness": "Эффективность: {}%",
                "analytics_top_channels": "Топ каналов:",
                "analytics_no_data": "Недостаточно данных для аналитики",
                "analytics_export": "Экспорт данных",
                
                # Тексты для жалоб
                "report_prompt": "Выберите причину жалобы:",
                "report_intensity": "Выберите интенсивность отправки:",
                "report_intensity_max": "Максимальная",
                "report_intensity_high": "Высокая",
                "report_intensity_medium": "Средняя",
                "report_intensity_low": "Низкая",
                "report_success": "✅ Жалобы успешно отправлены!\n\nУспешно: {}\nНеудачно: {}\nФлуд: {}",
                "report_cooldown": "⚠️ Пожалуйста, подождите {} минут перед следующей отправкой",
                "report_in_progress": "⏳ Отправка жалоб...\n\nПрогресс: {}%\nОбработано: {}/{}",
                
                # Тексты для промокодов и рефералов
                "promo_prompt": "Введите промокод:",
                "promo_success": "✅ Промокод применен! Скидка: {}%",
                "promo_invalid": "❌ Недействительный промокод",
                "referral_title": "👥 Реферальная программа",
                "referral_link": "Ваша реферальная ссылка: {}",
                "referral_stats": "Приглашено пользователей: {}\nПолучено вознаграждений: {} дней"
            },
            
            # Английский язык
            "en": {
                # Общие тексты
                "welcome": "Welcome to BotNet - bot for mass reporting messages in Telegram!",
                "menu": "Main menu:",
                "help": "Send a message link to start reporting.",
                "error": "Error: {}",
                "success": "Success!",
                "cancel": "Cancelled",
                "back": "Back",
                "next": "Next",
                "confirm": "Confirm",
                
                # Тексты связанные с подписками
                "subscription_expired": "Your subscription has expired. Please renew it to continue using the bot.",
                "subscription_active": "Your subscription is active until {}",
                "subscription_buy": "Buy subscription",
                "subscription_renew": "Renew subscription",
                "subscription_plan": "Subscription plan: {}",
                
                # Тексты для статистики
                "stats_title": "📊 General Statistics",
                "stats_week_title": "📊 Weekly Statistics",
                "stats_month_title": "📊 Monthly Statistics",
                "stats_views": "Views",
                "stats_reports_sent": "Reports sent",
                "stats_report_results": "Report results",
                "stats_successful": "Successful",
                "stats_failed": "Failed",
                "stats_flood": "Flood",
                "stats_effectiveness": "Effectiveness",
                "stats_last_activity": "Last activity",
                
                # Тексты для планировщика
                "scheduler_title": "🕒 Task Scheduler",
                "scheduler_new_task": "Create new task",
                "scheduler_my_tasks": "My tasks",
                "scheduler_no_tasks": "You don't have any scheduled tasks",
                "scheduler_task_created": "Task created and will be executed at {}",
                "scheduler_task_cancelled": "Task cancelled",
                "scheduler_select_time": "Select execution time:",
                "scheduler_select_repeat": "Select repeat interval:",
                "scheduler_select_reason": "Select report reason:",
                
                # Тексты для аналитики
                "analytics_title": "📈 Analytics",
                "analytics_period": "Period: {} days",
                "analytics_total_reports": "Total reports sent: {}",
                "analytics_effectiveness": "Effectiveness: {}%",
                "analytics_top_channels": "Top channels:",
                "analytics_no_data": "Not enough data for analytics",
                "analytics_export": "Export data",
                
                # Тексты для жалоб
                "report_prompt": "Select report reason:",
                "report_intensity": "Select reporting intensity:",
                "report_intensity_max": "Maximum",
                "report_intensity_high": "High",
                "report_intensity_medium": "Medium",
                "report_intensity_low": "Low",
                "report_success": "✅ Reports successfully sent!\n\nSuccessful: {}\nFailed: {}\nFlood: {}",
                "report_cooldown": "⚠️ Please wait {} minutes before next report",
                "report_in_progress": "⏳ Sending reports...\n\nProgress: {}%\nProcessed: {}/{}",
                
                # Тексты для промокодов и рефералов
                "promo_prompt": "Enter promo code:",
                "promo_success": "✅ Promo code applied! Discount: {}%",
                "promo_invalid": "❌ Invalid promo code",
                "referral_title": "👥 Referral Program",
                "referral_link": "Your referral link: {}",
                "referral_stats": "Invited users: {}\nRewards received: {} days"
            }
        }
        
        logger.info("Инициализирован LocalizationManager")
    
    def get_text(self, key: str, lang: str, *args, **kwargs) -> str:
        """
        Получение локализованного текста по ключу
        
        Args:
            key: Ключ текста
            lang: Код языка
            *args, **kwargs: Аргументы для форматирования текста
            
        Returns:
            str: Локализованный текст
        """
        # Проверяем поддержку языка
        if lang not in self.supported_languages:
            lang = "ru"  # Используем русский по умолчанию
            
        # Получаем текст по ключу
        text = self.texts.get(lang, {}).get(key)
        
        # Если текст не найден, пробуем найти в русском языке
        if text is None and lang != "ru":
            text = self.texts.get("ru", {}).get(key)
            
        # Если текст все равно не найден, возвращаем ключ
        if text is None:
            return f"[{key}]"
            
        # Форматируем текст, если есть аргументы
        try:
            if args or kwargs:
                return text.format(*args, **kwargs)
        except Exception as e:
            logger.error(f"Ошибка при форматировании текста '{key}': {e}")
            
        return text
    
    def get_language(self, user_lang_code: str) -> str:
        """
        Получение поддерживаемого кода языка
        
        Args:
            user_lang_code: Код языка пользователя
            
        Returns:
            str: Поддерживаемый код языка
        """
        # Проверяем, поддерживается ли язык
        if user_lang_code in self.supported_languages:
            return user_lang_code
            
        # Если язык не поддерживается, используем русский по умолчанию
        return "ru"
    
    def add_translations(self, lang: str, translations: Dict[str, str]) -> bool:
        """
        Добавление новых переводов для языка
        
        Args:
            lang: Код языка
            translations: Словарь с переводами {ключ: текст}
            
        Returns:
            bool: Успешно ли добавлены переводы
        """
        try:
            # Если язык не поддерживается, добавляем его
            if lang not in self.supported_languages:
                self.supported_languages.append(lang)
                self.texts[lang] = {}
                
            # Добавляем переводы
            self.texts[lang].update(translations)
            
            logger.info(f"Добавлены переводы для языка {lang}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при добавлении переводов для языка {lang}: {e}")
            return False

# Создаем экземпляр для удобного импорта
i18n = LocalizationManager() 
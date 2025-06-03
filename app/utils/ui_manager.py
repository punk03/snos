"""
Модуль для управления улучшенным пользовательским интерфейсом
"""
import logging
import json
import io
import base64
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime, timedelta

import matplotlib
matplotlib.use('Agg')  # Не требует GUI
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

import config
from app.database.db import db
from app.utils.localization import i18n

logger = logging.getLogger(__name__)

class UIManager:
    """Менеджер для работы с улучшенным пользовательским интерфейсом"""
    
    def __init__(self):
        """Инициализация менеджера UI"""
        self.theme = {
            "primary_color": "#2C3E50",
            "secondary_color": "#3498DB",
            "success_color": "#2ECC71",
            "warning_color": "#F39C12",
            "danger_color": "#E74C3C",
            "background_color": "#ECF0F1",
            "text_color": "#34495E",
        }
        
        # Настройки графиков
        plt.style.use('ggplot')
        self.chart_dpi = 100
        self.chart_size = (8, 5)
        
        logger.info("Инициализирован UIManager")
    
    def generate_report_statistics_chart(self, user_id: int, days: int = 30) -> Optional[bytes]:
        """
        Генерация графика статистики жалоб пользователя
        
        Args:
            user_id: ID пользователя
            days: Количество дней для отображения
            
        Returns:
            Optional[bytes]: PNG изображение в байтах или None
        """
        try:
            # Получаем данные из БД
            conn = db.pool.get_connection()
            if not conn:
                return None
                
            cursor = conn.cursor()
            
            # Определяем период
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Получаем все операции типа "report_result" за период
            cursor.execute(
                """
                SELECT created_at, result FROM operations
                WHERE user_id = ? AND operation_type = 'report_result'
                AND created_at >= ?
                ORDER BY created_at ASC
                """,
                (user_id, start_date.strftime("%Y-%m-%d %H:%M:%S"))
            )
            
            results = cursor.fetchall()
            db.pool.release_connection(conn)
            
            if not results:
                return None
                
            # Подготавливаем данные для графика
            dates = []
            valid_reports = []
            invalid_reports = []
            flood_reports = []
            
            for row in results:
                dates.append(datetime.strptime(row['created_at'], "%Y-%m-%d %H:%M:%S"))
                
                try:
                    result_data = json.loads(row['result'])
                    valid_reports.append(result_data.get('valid', 0))
                    invalid_reports.append(result_data.get('invalid', 0))
                    flood_reports.append(result_data.get('flood', 0))
                except:
                    valid_reports.append(0)
                    invalid_reports.append(0)
                    flood_reports.append(0)
            
            # Создаем график
            fig, ax = plt.subplots(figsize=self.chart_size, dpi=self.chart_dpi)
            
            # Настраиваем формат дат
            if days <= 7:
                date_format = mdates.DateFormatter('%d/%m %H:%M')
                ax.xaxis.set_major_formatter(date_format)
            else:
                date_format = mdates.DateFormatter('%d/%m')
                ax.xaxis.set_major_formatter(date_format)
                
            # Строим график
            ax.plot(dates, valid_reports, label='Успешные', color='green', marker='o')
            ax.plot(dates, invalid_reports, label='Неудачные', color='red', marker='x')
            ax.plot(dates, flood_reports, label='Флуд', color='orange', marker='s')
            
            # Если данных много, добавляем скользящее среднее
            if len(dates) > 5:
                window = min(5, len(dates) // 2)
                if window > 0:
                    valid_avg = np.convolve(valid_reports, np.ones(window)/window, mode='valid')
                    ax.plot(dates[window-1:], valid_avg, label='Среднее (успешные)', color='darkgreen', linestyle='--')
            
            # Настраиваем внешний вид
            ax.set_title(f'Статистика жалоб за {days} дней')
            ax.set_xlabel('Дата')
            ax.set_ylabel('Количество')
            ax.grid(True, linestyle='--', alpha=0.7)
            ax.legend()
            
            # Сохраняем в буфер
            buf = io.BytesIO()
            fig.tight_layout()
            plt.savefig(buf, format='png')
            plt.close(fig)
            
            # Возвращаем байты
            buf.seek(0)
            return buf.getvalue()
            
        except Exception as e:
            logger.error(f"Ошибка при генерации графика статистики: {e}")
            return None
    
    def generate_subscription_usage_chart(self, user_id: int) -> Optional[bytes]:
        """
        Генерация диаграммы использования подписки
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Optional[bytes]: PNG изображение в байтах или None
        """
        try:
            # Получаем данные о подписке
            subscription_date = db.get_subscription_date(user_id)
            if not subscription_date:
                return None
                
            try:
                sub_date = datetime.strptime(subscription_date, "%Y-%m-%d %H:%M:%S")
                # Если подписка истекла, ничего не показываем
                if sub_date < datetime.now():
                    return None
                    
                # Получаем данные о пользователе
                user_data = db.get_user(user_id)
                if not user_data:
                    return None
                    
                # Вычисляем продолжительность подписки
                sub_start = datetime.strptime(user_data.get('registration_date', datetime.now().strftime("%Y-%m-%d %H:%M:%S")), "%Y-%m-%d %H:%M:%S")
                
                # Если дата начала подписки позже текущей, считаем от текущей
                if sub_start > datetime.now():
                    sub_start = datetime.now()
                
                total_days = (sub_date - sub_start).days
                days_left = (sub_date - datetime.now()).days
                days_used = total_days - days_left
                
                # Если некорректные данные, ничего не показываем
                if total_days <= 0 or days_left < 0:
                    return None
                
                # Создаем график
                fig, ax = plt.subplots(figsize=(6, 3), dpi=self.chart_dpi)
                
                # Создаем данные для диаграммы
                labels = ['Использовано', 'Осталось']
                sizes = [days_used, days_left]
                colors = ['#3498db', '#2ecc71']
                explode = (0, 0.1)  # Выделяем часть "Осталось"
                
                # Строим диаграмму
                wedges, texts, autotexts = ax.pie(
                    sizes, 
                    explode=explode, 
                    labels=labels, 
                    colors=colors,
                    autopct='%1.1f%%',
                    shadow=True, 
                    startangle=90
                )
                
                # Настраиваем внешний вид
                ax.set_title(f'Использование подписки')
                ax.axis('equal')  # Равные пропорции для круга
                
                # Улучшаем читаемость текста
                for text in texts:
                    text.set_fontsize(10)
                for autotext in autotexts:
                    autotext.set_fontsize(10)
                    autotext.set_fontweight('bold')
                
                # Добавляем информацию о днях
                plt.figtext(0.5, 0.01, f"Осталось дней: {days_left} из {total_days}", 
                         ha="center", fontsize=10, bbox={"facecolor":"orange", "alpha":0.2, "pad":5})
                
                # Сохраняем в буфер
                buf = io.BytesIO()
                fig.tight_layout()
                plt.savefig(buf, format='png')
                plt.close(fig)
                
                # Возвращаем байты
                buf.seek(0)
                return buf.getvalue()
                
            except Exception as e:
                logger.error(f"Ошибка при обработке дат подписки для пользователя {user_id}: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка при генерации диаграммы использования подписки: {e}")
            return None
    
    def generate_effectiveness_bar_chart(self, user_id: int, limit: int = 5) -> Optional[bytes]:
        """
        Генерация столбчатой диаграммы эффективности жалоб по каналам
        
        Args:
            user_id: ID пользователя
            limit: Количество каналов для отображения
            
        Returns:
            Optional[bytes]: PNG изображение в байтах или None
        """
        try:
            # Получаем данные из БД
            conn = db.pool.get_connection()
            if not conn:
                return None
                
            cursor = conn.cursor()
            
            # Получаем статистику по каналам
            cursor.execute(
                """
                SELECT target, COUNT(*) as count, AVG(json_extract(result, '$.valid')) as avg_valid
                FROM operations
                WHERE user_id = ? AND operation_type = 'report_result'
                GROUP BY target
                ORDER BY count DESC
                LIMIT ?
                """,
                (user_id, limit)
            )
            
            results = cursor.fetchall()
            db.pool.release_connection(conn)
            
            if not results:
                return None
                
            # Подготавливаем данные для графика
            channels = []
            counts = []
            effectiveness = []
            
            for row in results:
                # Извлекаем имя канала из ссылки
                target = row['target']
                try:
                    channel_name = target.split('t.me/')[1].split('/')[0]
                    if not channel_name:
                        channel_name = "Неизвестно"
                except:
                    channel_name = "Неизвестно"
                    
                channels.append(channel_name)
                counts.append(row['count'])
                effectiveness.append(float(row['avg_valid'] or 0) * 100)  # В процентах
            
            # Создаем график
            fig, ax1 = plt.subplots(figsize=self.chart_size, dpi=self.chart_dpi)
            
            # Создаем первый набор столбцов (количество)
            x = np.arange(len(channels))
            width = 0.35
            
            rects1 = ax1.bar(x - width/2, counts, width, label='Количество', color='#3498db')
            
            ax1.set_xlabel('Канал')
            ax1.set_ylabel('Количество жалоб', color='#3498db')
            ax1.tick_params(axis='y', labelcolor='#3498db')
            ax1.set_xticks(x)
            ax1.set_xticklabels(channels, rotation=45, ha='right')
            
            # Создаем вторую ось Y для процента эффективности
            ax2 = ax1.twinx()
            rects2 = ax2.bar(x + width/2, effectiveness, width, label='Эффективность (%)', color='#2ecc71')
            
            ax2.set_ylabel('Эффективность (%)', color='#2ecc71')
            ax2.tick_params(axis='y', labelcolor='#2ecc71')
            
            # Добавляем значения над столбцами
            def autolabel(rects, ax):
                for rect in rects:
                    height = rect.get_height()
                    ax.annotate(f'{height:.0f}',
                               xy=(rect.get_x() + rect.get_width() / 2, height),
                               xytext=(0, 3),
                               textcoords="offset points",
                               ha='center', va='bottom', fontsize=8)
            
            autolabel(rects1, ax1)
            autolabel(rects2, ax2)
            
            # Настраиваем внешний вид
            ax1.set_title('Эффективность жалоб по каналам')
            ax1.legend(loc='upper left')
            ax2.legend(loc='upper right')
            
            # Сохраняем в буфер
            buf = io.BytesIO()
            fig.tight_layout()
            plt.savefig(buf, format='png')
            plt.close(fig)
            
            # Возвращаем байты
            buf.seek(0)
            return buf.getvalue()
            
        except Exception as e:
            logger.error(f"Ошибка при генерации диаграммы эффективности: {e}")
            return None
    
    def create_premium_features_keyboard(self, user_id: int) -> InlineKeyboardMarkup:
        """
        Создание клавиатуры с премиум функциями с учетом тарифного плана пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            InlineKeyboardMarkup: Клавиатура с доступными функциями
        """
        markup = InlineKeyboardMarkup(row_width=2)
        
        # Определяем тарифный план пользователя
        subscription = db.get_user_subscription(user_id)
        plan = "basic"
        
        if subscription:
            plan = subscription.get("subscription_plan", "basic")
        
        # Получаем возможности плана
        plan_features = config.SUBSCRIPTION_PLANS.get(plan, {}).get("features", [])
        
        # Основные функции (доступны всем)
        markup.add(
            InlineKeyboardButton("🚨 Отправить жалобы", callback_data="botnet"),
            InlineKeyboardButton("📊 Моя статистика", callback_data="stats")
        )
        
        # Премиум функции
        if "priority_processing" in plan_features:
            markup.add(InlineKeyboardButton("⚡ Приоритетная отправка", callback_data="priority_send"))
        
        if "advanced_analytics" in plan_features:
            markup.add(InlineKeyboardButton("📈 Расширенная аналитика", callback_data="advanced_analytics"))
        
        if "custom_reporting" in plan_features:
            markup.add(InlineKeyboardButton("📋 Отчеты и графики", callback_data="reports"))
        
        if "scheduled_tasks" in plan_features:
            markup.add(InlineKeyboardButton("🕒 Планировщик задач", callback_data="scheduler"))
        
        # Кнопки для обновления подписки и возврата
        markup.add(
            InlineKeyboardButton("⭐ Улучшить план", callback_data="upgrade_plan"),
            InlineKeyboardButton("◀️ Назад", callback_data="back")
        )
        
        return markup
    
    def create_dynamic_subscription_keyboard(self, user_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
        """
        Создание динамической клавиатуры для выбора подписки с учетом текущего плана
        
        Args:
            user_id: ID пользователя
            lang: Код языка
            
        Returns:
            InlineKeyboardMarkup: Клавиатура с вариантами подписки
        """
        markup = InlineKeyboardMarkup(row_width=1)
        
        # Определяем текущий тарифный план пользователя
        subscription = db.get_user_subscription(user_id)
        current_plan = "basic"
        
        if subscription:
            current_plan = subscription.get("subscription_plan", "basic")
        
        # Добавляем доступные планы с выделением текущего
        for plan_id, plan_data in config.SUBSCRIPTION_PLANS.items():
            # Пропускаем текущий план
            if plan_id == current_plan:
                continue
                
            # Формируем текст кнопки
            plan_name = plan_data.get("name")
            
            # Добавляем возможность выбора периода для каждого плана
            for period, price in plan_data.get("prices", {}).items():
                if period == "lifetime":
                    button_text = f"🔆 {plan_name} (навсегда) - {price}$"
                    callback_data = f"subscribe_{plan_id}_lifetime"
                else:
                    days = period
                    button_text = f"⭐ {plan_name} ({days} дней) - {price}$"
                    callback_data = f"subscribe_{plan_id}_{days}"
                
                markup.add(InlineKeyboardButton(button_text, callback_data=callback_data))
        
        # Добавляем информацию о текущем плане
        current_plan_data = config.SUBSCRIPTION_PLANS.get(current_plan, {})
        current_plan_name = current_plan_data.get("name", "Базовый")
        
        # Определяем оставшиеся дни подписки
        remaining_days = 0
        if subscription:
            try:
                expires_at = subscription.get("expires_at")
                if expires_at:
                    expires_date = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
                    remaining_days = (expires_date - datetime.now()).days
            except:
                pass
        
        # Добавляем кнопку с информацией о текущем плане
        if remaining_days > 0:
            markup.add(InlineKeyboardButton(
                f"✅ Ваш текущий план: {current_plan_name} ({remaining_days} дней)",
                callback_data="current_plan_info"
            ))
        else:
            markup.add(InlineKeyboardButton(
                f"✅ Ваш текущий план: {current_plan_name}",
                callback_data="current_plan_info"
            ))
        
        # Добавляем кнопку ввода промокода
        markup.add(InlineKeyboardButton("🎟 Использовать промокод", callback_data="use_promo"))
        
        # Кнопка возврата
        markup.add(InlineKeyboardButton("◀️ Назад", callback_data="back"))
        
        return markup
    
    def create_statistics_keyboard(self, user_id: int, has_premium: bool = False) -> InlineKeyboardMarkup:
        """
        Создание клавиатуры для просмотра статистики
        
        Args:
            user_id: ID пользователя
            has_premium: Имеет ли пользователь премиум-подписку
            
        Returns:
            InlineKeyboardMarkup: Клавиатура с опциями статистики
        """
        markup = InlineKeyboardMarkup(row_width=2)
        
        # Основные опции статистики (доступны всем)
        markup.add(
            InlineKeyboardButton("📊 Общая статистика", callback_data="stats_general"),
            InlineKeyboardButton("📆 За неделю", callback_data="stats_week")
        )
        
        # Дополнительные опции для премиум-подписки
        if has_premium:
            markup.add(
                InlineKeyboardButton("📈 График результатов", callback_data="stats_chart"),
                InlineKeyboardButton("📊 По каналам", callback_data="stats_channels")
            )
            
            markup.add(
                InlineKeyboardButton("📋 Полный отчет", callback_data="stats_full_report"),
                InlineKeyboardButton("📤 Экспорт данных", callback_data="stats_export")
            )
        
        # Кнопка возврата
        markup.add(InlineKeyboardButton("◀️ Назад", callback_data="back"))
        
        return markup
    
    def format_statistics_message(self, user_id: int, stats_type: str = "general", lang: str = "ru") -> str:
        """
        Форматирование сообщения со статистикой
        
        Args:
            user_id: ID пользователя
            stats_type: Тип статистики (general, week, month)
            lang: Код языка
            
        Returns:
            str: Отформатированное сообщение
        """
        try:
            # Получаем данные пользователя
            user_data = db.get_user(user_id)
            if not user_data:
                return i18n.get_text("error", lang, "Пользователь не найден")
            
            # Получаем статистику в зависимости от типа
            conn = db.pool.get_connection()
            if not conn:
                return i18n.get_text("error", lang, "Ошибка соединения с базой данных")
                
            cursor = conn.cursor()
            
            # Определяем период для выборки
            date_filter = ""
            if stats_type == "week":
                week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
                date_filter = f"AND created_at >= '{week_ago}'"
            elif stats_type == "month":
                month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
                date_filter = f"AND created_at >= '{month_ago}'"
            
            # Получаем количество операций
            cursor.execute(
                f"""
                SELECT COUNT(*) as count FROM operations
                WHERE user_id = ? AND operation_type = 'command'
                {date_filter}
                """,
                (user_id,)
            )
            command_count = cursor.fetchone()['count']
            
            # Получаем количество жалоб
            cursor.execute(
                f"""
                SELECT COUNT(*) as count FROM operations
                WHERE user_id = ? AND operation_type = 'report'
                {date_filter}
                """,
                (user_id,)
            )
            report_count = cursor.fetchone()['count']
            
            # Получаем статистику по результатам жалоб
            cursor.execute(
                f"""
                SELECT result FROM operations
                WHERE user_id = ? AND operation_type = 'report_result'
                {date_filter}
                """,
                (user_id,)
            )
            
            results = cursor.fetchall()
            db.pool.release_connection(conn)
            
            # Подсчитываем успешные и неуспешные жалобы
            valid_count = 0
            invalid_count = 0
            flood_count = 0
            
            for row in results:
                try:
                    result_data = json.loads(row['result'])
                    valid_count += result_data.get('valid', 0)
                    invalid_count += result_data.get('invalid', 0)
                    flood_count += result_data.get('flood', 0)
                except:
                    pass
            
            # Вычисляем эффективность
            total_reports = valid_count + invalid_count + flood_count
            effectiveness = (valid_count / total_reports * 100) if total_reports > 0 else 0
            
            # Формируем заголовок в зависимости от типа статистики
            title = ""
            if stats_type == "general":
                title = i18n.get_text("stats_title", lang)
            elif stats_type == "week":
                title = i18n.get_text("stats_week_title", lang)
            elif stats_type == "month":
                title = i18n.get_text("stats_month_title", lang)
            
            # Формируем сообщение
            last_activity = user_data.get('last_activity', '')
            
            message = f"{title}\n\n"
            message += f"👁 *{i18n.get_text('stats_views', lang)}:* `{command_count}`\n"
            message += f"🚨 *{i18n.get_text('stats_reports_sent', lang)}:* `{report_count}`\n\n"
            
            message += f"📊 *{i18n.get_text('stats_report_results', lang)}:*\n"
            message += f"✅ *{i18n.get_text('stats_successful', lang)}:* `{valid_count}`\n"
            message += f"❌ *{i18n.get_text('stats_failed', lang)}:* `{invalid_count}`\n"
            message += f"⚠️ *{i18n.get_text('stats_flood', lang)}:* `{flood_count}`\n\n"
            
            message += f"📈 *{i18n.get_text('stats_effectiveness', lang)}:* `{effectiveness:.1f}%`\n\n"
            
            message += f"⏱ *{i18n.get_text('stats_last_activity', lang)}:* `{last_activity}`"
            
            return message
            
        except Exception as e:
            logger.error(f"Ошибка при форматировании статистики для пользователя {user_id}: {e}")
            return i18n.get_text("error", lang, str(e))
    
    def create_report_scheduler_keyboard(self) -> InlineKeyboardMarkup:
        """
        Создание клавиатуры для планировщика задач
        
        Returns:
            InlineKeyboardMarkup: Клавиатура с опциями планировщика
        """
        markup = InlineKeyboardMarkup(row_width=2)
        
        # Опции планировщика
        markup.add(
            InlineKeyboardButton("🆕 Новая задача", callback_data="scheduler_new"),
            InlineKeyboardButton("📋 Мои задачи", callback_data="scheduler_list")
        )
        
        markup.add(
            InlineKeyboardButton("📅 Расписание", callback_data="scheduler_schedule"),
            InlineKeyboardButton("⚙️ Настройки", callback_data="scheduler_settings")
        )
        
        # Кнопка возврата
        markup.add(InlineKeyboardButton("◀️ Назад", callback_data="back"))
        
        return markup
    
    def create_time_selection_keyboard(self, action: str) -> InlineKeyboardMarkup:
        """
        Создание клавиатуры для выбора времени
        
        Args:
            action: Действие (для callback_data)
            
        Returns:
            InlineKeyboardMarkup: Клавиатура с опциями времени
        """
        markup = InlineKeyboardMarkup(row_width=3)
        
        # Кнопки для выбора часа
        row = []
        for hour in [9, 12, 15, 18, 21, 0]:
            row.append(InlineKeyboardButton(f"{hour}:00", callback_data=f"{action}_time_{hour}_00"))
            
            if len(row) == 3:
                markup.add(*row)
                row = []
        
        # Добавляем оставшиеся кнопки
        if row:
            markup.add(*row)
        
        # Кнопки "Через 1 час" и "Через 3 часа"
        markup.add(
            InlineKeyboardButton("Через 1 час", callback_data=f"{action}_time_plus_1h"),
            InlineKeyboardButton("Через 3 часа", callback_data=f"{action}_time_plus_3h")
        )
        
        # Кнопка возврата
        markup.add(InlineKeyboardButton("◀️ Назад", callback_data="back"))
        
        return markup

# Создаем экземпляр для удобного импорта
ui_manager = UIManager() 
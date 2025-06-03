"""
Модуль для аналитики и сбора статистики
"""
import logging
import json
import io
import base64
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime, timedelta
import csv

import config
from app.database.db import db

logger = logging.getLogger(__name__)

class AnalyticsManager:
    """Менеджер для работы с аналитикой и статистикой"""
    
    def __init__(self):
        """Инициализация менеджера аналитики"""
        logger.info("Инициализирован AnalyticsManager")
    
    def get_user_report_stats(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Получение статистики отправленных жалоб пользователя
        
        Args:
            user_id: ID пользователя
            days: Количество дней для анализа
            
        Returns:
            Dict[str, Any]: Статистика жалоб
        """
        try:
            # Получаем данные из БД
            conn = db.pool.get_connection()
            if not conn:
                return {"error": "database_connection_error"}
                
            cursor = conn.cursor()
            
            # Определяем период
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            start_date_str = start_date.strftime("%Y-%m-%d %H:%M:%S")
            
            # Получаем количество операций отправки жалоб
            cursor.execute(
                """
                SELECT COUNT(*) as count FROM operations
                WHERE user_id = ? AND operation_type = 'report'
                AND created_at >= ?
                """,
                (user_id, start_date_str)
            )
            total_reports = cursor.fetchone()['count']
            
            # Получаем статистику по результатам жалоб
            cursor.execute(
                """
                SELECT result FROM operations
                WHERE user_id = ? AND operation_type = 'report_result'
                AND created_at >= ?
                """,
                (user_id, start_date_str)
            )
            
            result_rows = cursor.fetchall()
            
            # Получаем статистику по каналам
            cursor.execute(
                """
                SELECT target, COUNT(*) as count FROM operations
                WHERE user_id = ? AND operation_type = 'report'
                AND created_at >= ?
                GROUP BY target
                ORDER BY count DESC
                LIMIT ?
                """,
                (user_id, start_date_str, config.UI_SETTINGS.get("charts", {}).get("max_channels", 10))
            )
            
            channel_stats = []
            for row in cursor.fetchall():
                channel_stats.append({
                    "target": row['target'],
                    "count": row['count']
                })
            
            # Получаем статистику по причинам жалоб
            cursor.execute(
                """
                SELECT params, COUNT(*) as count FROM operations
                WHERE user_id = ? AND operation_type = 'report'
                AND created_at >= ?
                GROUP BY params
                ORDER BY count DESC
                """,
                (user_id, start_date_str)
            )
            
            reason_stats = {}
            for row in cursor.fetchall():
                try:
                    params = json.loads(row['params'])
                    reason = params.get('reason', 'other')
                    reason_name = config.REPORT_REASON_NAMES.get(reason, "Другое")
                    
                    if reason_name in reason_stats:
                        reason_stats[reason_name] += row['count']
                    else:
                        reason_stats[reason_name] = row['count']
                except:
                    pass
            
            # Получаем динамику отправки жалоб по дням
            cursor.execute(
                """
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM operations
                WHERE user_id = ? AND operation_type = 'report'
                AND created_at >= ?
                GROUP BY DATE(created_at)
                ORDER BY date
                """,
                (user_id, start_date_str)
            )
            
            daily_stats = []
            for row in cursor.fetchall():
                daily_stats.append({
                    "date": row['date'],
                    "count": row['count']
                })
            
            db.pool.release_connection(conn)
            
            # Анализируем результаты жалоб
            valid_reports = 0
            invalid_reports = 0
            flood_reports = 0
            
            for row in result_rows:
                try:
                    result_data = json.loads(row['result'])
                    valid_reports += result_data.get('valid', 0)
                    invalid_reports += result_data.get('invalid', 0)
                    flood_reports += result_data.get('flood', 0)
                except:
                    pass
            
            # Рассчитываем общую эффективность
            total_processed = valid_reports + invalid_reports + flood_reports
            effectiveness = (valid_reports / total_processed * 100) if total_processed > 0 else 0
            
            # Формируем итоговую статистику
            return {
                "total_reports": total_reports,
                "valid_reports": valid_reports,
                "invalid_reports": invalid_reports,
                "flood_reports": flood_reports,
                "effectiveness": round(effectiveness, 2),
                "channels": channel_stats,
                "reasons": reason_stats,
                "daily_stats": daily_stats,
                "period_days": days
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики жалоб пользователя {user_id}: {e}")
            return {"error": str(e)}
    
    def get_global_report_stats(self, days: int = 7) -> Dict[str, Any]:
        """
        Получение глобальной статистики отправленных жалоб
        
        Args:
            days: Количество дней для анализа
            
        Returns:
            Dict[str, Any]: Глобальная статистика
        """
        try:
            # Получаем данные из БД
            conn = db.pool.get_connection()
            if not conn:
                return {"error": "database_connection_error"}
                
            cursor = conn.cursor()
            
            # Определяем период
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            start_date_str = start_date.strftime("%Y-%m-%d %H:%M:%S")
            
            # Получаем общее количество операций отправки жалоб
            cursor.execute(
                """
                SELECT COUNT(*) as count FROM operations
                WHERE operation_type = 'report'
                AND created_at >= ?
                """,
                (start_date_str,)
            )
            total_reports = cursor.fetchone()['count']
            
            # Получаем количество уникальных пользователей
            cursor.execute(
                """
                SELECT COUNT(DISTINCT user_id) as count FROM operations
                WHERE operation_type = 'report'
                AND created_at >= ?
                """,
                (start_date_str,)
            )
            unique_users = cursor.fetchone()['count']
            
            # Получаем статистику по результатам жалоб
            cursor.execute(
                """
                SELECT result FROM operations
                WHERE operation_type = 'report_result'
                AND created_at >= ?
                """,
                (start_date_str,)
            )
            
            result_rows = cursor.fetchall()
            
            # Получаем статистику по каналам
            cursor.execute(
                """
                SELECT target, COUNT(*) as count FROM operations
                WHERE operation_type = 'report'
                AND created_at >= ?
                GROUP BY target
                ORDER BY count DESC
                LIMIT ?
                """,
                (start_date_str, config.UI_SETTINGS.get("charts", {}).get("max_channels", 10))
            )
            
            channel_stats = []
            for row in cursor.fetchall():
                channel_stats.append({
                    "target": row['target'],
                    "count": row['count']
                })
            
            # Получаем статистику по причинам жалоб
            cursor.execute(
                """
                SELECT params, COUNT(*) as count FROM operations
                WHERE operation_type = 'report'
                AND created_at >= ?
                GROUP BY params
                ORDER BY count DESC
                """,
                (start_date_str,)
            )
            
            reason_stats = {}
            for row in cursor.fetchall():
                try:
                    params = json.loads(row['params'])
                    reason = params.get('reason', 'other')
                    reason_name = config.REPORT_REASON_NAMES.get(reason, "Другое")
                    
                    if reason_name in reason_stats:
                        reason_stats[reason_name] += row['count']
                    else:
                        reason_stats[reason_name] = row['count']
                except:
                    pass
            
            # Получаем динамику отправки жалоб по дням
            cursor.execute(
                """
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM operations
                WHERE operation_type = 'report'
                AND created_at >= ?
                GROUP BY DATE(created_at)
                ORDER BY date
                """,
                (start_date_str,)
            )
            
            daily_stats = []
            for row in cursor.fetchall():
                daily_stats.append({
                    "date": row['date'],
                    "count": row['count']
                })
            
            db.pool.release_connection(conn)
            
            # Анализируем результаты жалоб
            valid_reports = 0
            invalid_reports = 0
            flood_reports = 0
            
            for row in result_rows:
                try:
                    result_data = json.loads(row['result'])
                    valid_reports += result_data.get('valid', 0)
                    invalid_reports += result_data.get('invalid', 0)
                    flood_reports += result_data.get('flood', 0)
                except:
                    pass
            
            # Рассчитываем общую эффективность
            total_processed = valid_reports + invalid_reports + flood_reports
            effectiveness = (valid_reports / total_processed * 100) if total_processed > 0 else 0
            
            # Средние значения
            avg_reports_per_user = total_reports / unique_users if unique_users > 0 else 0
            
            # Формируем итоговую статистику
            return {
                "total_reports": total_reports,
                "unique_users": unique_users,
                "valid_reports": valid_reports,
                "invalid_reports": invalid_reports,
                "flood_reports": flood_reports,
                "effectiveness": round(effectiveness, 2),
                "avg_reports_per_user": round(avg_reports_per_user, 2),
                "channels": channel_stats,
                "reasons": reason_stats,
                "daily_stats": daily_stats,
                "period_days": days
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении глобальной статистики жалоб: {e}")
            return {"error": str(e)}
    
    def generate_user_report(self, user_id: int, days: int = 30, format: str = "text") -> Union[str, bytes]:
        """
        Генерация отчета о жалобах пользователя
        
        Args:
            user_id: ID пользователя
            days: Количество дней для анализа
            format: Формат отчета (text, csv)
            
        Returns:
            Union[str, bytes]: Отчет в запрошенном формате
        """
        try:
            # Получаем статистику
            stats = self.get_user_report_stats(user_id, days)
            
            if "error" in stats:
                return f"Ошибка при генерации отчета: {stats['error']}"
                
            # Получаем данные пользователя
            user_data = db.get_user(user_id)
            username = user_data.get('username', '') if user_data else ''
            
            # Генерируем отчет в нужном формате
            if format == "csv":
                # Создаем CSV в памяти
                output = io.StringIO()
                writer = csv.writer(output)
                
                # Заголовок
                writer.writerow(['Отчет о жалобах пользователя', f'@{username}', f'ID: {user_id}'])
                writer.writerow(['Период:', f'{days} дней', f'Дата формирования: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
                writer.writerow([])
                
                # Основная статистика
                writer.writerow(['Общая статистика'])
                writer.writerow(['Всего отправлено жалоб:', stats['total_reports']])
                writer.writerow(['Успешных жалоб:', stats['valid_reports']])
                writer.writerow(['Неуспешных жалоб:', stats['invalid_reports']])
                writer.writerow(['Жалоб с флудом:', stats['flood_reports']])
                writer.writerow(['Эффективность:', f"{stats['effectiveness']}%"])
                writer.writerow([])
                
                # Статистика по каналам
                writer.writerow(['Статистика по каналам'])
                writer.writerow(['Канал', 'Количество жалоб'])
                
                for channel in stats['channels']:
                    target = channel['target']
                    writer.writerow([target, channel['count']])
                    
                writer.writerow([])
                
                # Статистика по причинам
                writer.writerow(['Статистика по причинам жалоб'])
                writer.writerow(['Причина', 'Количество'])
                
                for reason, count in stats['reasons'].items():
                    writer.writerow([reason, count])
                    
                writer.writerow([])
                
                # Динамика по дням
                writer.writerow(['Динамика отправки жалоб по дням'])
                writer.writerow(['Дата', 'Количество'])
                
                for day in stats['daily_stats']:
                    writer.writerow([day['date'], day['count']])
                
                # Получаем данные в формате CSV
                output.seek(0)
                return output.getvalue().encode('utf-8')
                
            else:  # Текстовый формат
                # Форматируем текстовый отчет
                report = f"📊 *Отчет о жалобах пользователя @{username} (ID: {user_id})*\n"
                report += f"📆 Период: {days} дней\n"
                report += f"📅 Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                
                report += "📈 *Общая статистика:*\n"
                report += f"📨 Всего отправлено жалоб: {stats['total_reports']}\n"
                report += f"✅ Успешных жалоб: {stats['valid_reports']}\n"
                report += f"❌ Неуспешных жалоб: {stats['invalid_reports']}\n"
                report += f"⚠️ Жалоб с флудом: {stats['flood_reports']}\n"
                report += f"🎯 Эффективность: {stats['effectiveness']}%\n\n"
                
                report += "🔝 *Топ каналов:*\n"
                for i, channel in enumerate(stats['channels'][:5], 1):
                    target = channel['target']
                    report += f"{i}. {target} - {channel['count']} жалоб\n"
                    
                report += "\n📋 *Причины жалоб:*\n"
                for reason, count in stats['reasons'].items():
                    report += f"• {reason}: {count}\n"
                
                return report
                
        except Exception as e:
            logger.error(f"Ошибка при генерации отчета для пользователя {user_id}: {e}")
            return f"Ошибка при генерации отчета: {e}"
    
    def get_effectiveness_by_channel(self, channels: List[str], days: int = 30) -> Dict[str, Any]:
        """
        Получение статистики эффективности жалоб по каналам
        
        Args:
            channels: Список каналов для анализа
            days: Количество дней для анализа
            
        Returns:
            Dict[str, Any]: Статистика эффективности
        """
        try:
            # Получаем данные из БД
            conn = db.pool.get_connection()
            if not conn:
                return {"error": "database_connection_error"}
                
            cursor = conn.cursor()
            
            # Определяем период
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            start_date_str = start_date.strftime("%Y-%m-%d %H:%M:%S")
            
            # Результаты по каналам
            results = {}
            
            for channel in channels:
                # Получаем количество жалоб на канал
                cursor.execute(
                    """
                    SELECT COUNT(*) as count FROM operations
                    WHERE operation_type = 'report' AND target LIKE ?
                    AND created_at >= ?
                    """,
                    (f"%{channel}%", start_date_str)
                )
                
                total_reports = cursor.fetchone()['count']
                
                # Получаем результаты жалоб на канал
                cursor.execute(
                    """
                    SELECT result FROM operations
                    WHERE operation_type = 'report_result' AND target LIKE ?
                    AND created_at >= ?
                    """,
                    (f"%{channel}%", start_date_str)
                )
                
                result_rows = cursor.fetchall()
                
                # Анализируем результаты
                valid_reports = 0
                invalid_reports = 0
                flood_reports = 0
                
                for row in result_rows:
                    try:
                        result_data = json.loads(row['result'])
                        valid_reports += result_data.get('valid', 0)
                        invalid_reports += result_data.get('invalid', 0)
                        flood_reports += result_data.get('flood', 0)
                    except:
                        pass
                
                # Рассчитываем эффективность
                total_processed = valid_reports + invalid_reports + flood_reports
                effectiveness = (valid_reports / total_processed * 100) if total_processed > 0 else 0
                
                # Сохраняем результаты
                results[channel] = {
                    "total_reports": total_reports,
                    "valid_reports": valid_reports,
                    "invalid_reports": invalid_reports,
                    "flood_reports": flood_reports,
                    "effectiveness": round(effectiveness, 2)
                }
            
            db.pool.release_connection(conn)
            
            return {
                "channels": results,
                "period_days": days
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении эффективности по каналам: {e}")
            return {"error": str(e)}
    
    def get_subscription_usage_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Получение статистики использования подписки
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Dict[str, Any]: Статистика использования подписки
        """
        try:
            # Получаем данные о подписке пользователя
            subscription = db.get_user_subscription(user_id)
            
            if not subscription:
                return {"active": False}
                
            # Проверяем активность подписки
            is_active = subscription.get("is_active", False)
            
            if not is_active:
                return {"active": False}
                
            # Получаем данные о плане
            plan_id = subscription.get("subscription_plan", "basic")
            plan_data = config.SUBSCRIPTION_PLANS.get(plan_id, {})
            
            # Рассчитываем оставшиеся дни
            expires_at = subscription.get("expires_at")
            
            if not expires_at:
                return {"active": False}
                
            expires_date = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
            starts_at = subscription.get("starts_at")
            start_date = datetime.strptime(starts_at, "%Y-%m-%d %H:%M:%S") if starts_at else datetime.now()
            
            current_date = datetime.now()
            
            if expires_date < current_date:
                return {"active": False}
                
            total_days = (expires_date - start_date).days
            days_left = (expires_date - current_date).days
            days_used = total_days - days_left
            
            # Получаем статистику использования функций
            conn = db.pool.get_connection()
            if not conn:
                return {
                    "active": True,
                    "plan": plan_id,
                    "plan_name": plan_data.get("name", "Базовый"),
                    "days_total": total_days,
                    "days_left": days_left,
                    "days_used": days_used,
                    "expires_at": expires_at,
                    "auto_renew": subscription.get("auto_renew", False)
                }
                
            cursor = conn.cursor()
            
            # Получаем количество отправленных жалоб с момента начала подписки
            cursor.execute(
                """
                SELECT COUNT(*) as count FROM operations
                WHERE user_id = ? AND operation_type = 'report'
                AND created_at >= ?
                """,
                (user_id, starts_at or "2000-01-01 00:00:00")
            )
            
            reports_count = cursor.fetchone()['count']
            
            # Получаем количество запланированных задач
            cursor.execute(
                """
                SELECT COUNT(*) as count FROM scheduled_tasks
                WHERE user_id = ? AND status != 'cancelled'
                AND created_at >= ?
                """,
                (user_id, starts_at or "2000-01-01 00:00:00")
            )
            
            tasks_count = cursor.fetchone()['count'] if 'scheduled_tasks' in [t[0] for t in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()] else 0
            
            db.pool.release_connection(conn)
            
            # Формируем статистику
            return {
                "active": True,
                "plan": plan_id,
                "plan_name": plan_data.get("name", "Базовый"),
                "days_total": total_days,
                "days_left": days_left,
                "days_used": days_used,
                "expires_at": expires_at,
                "auto_renew": subscription.get("auto_renew", False),
                "reports_count": reports_count,
                "tasks_count": tasks_count,
                "features": plan_data.get("features", []),
                "max_sessions": plan_data.get("max_sessions_per_request", 50),
                "cooldown_minutes": plan_data.get("cooldown_minutes", 5)
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики использования подписки для пользователя {user_id}: {e}")
            return {"active": False, "error": str(e)}

# Создаем экземпляр для удобного импорта
analytics_manager = AnalyticsManager() 
import asyncio
import logging
from datetime import datetime, timedelta

from telebot import TeleBot
from telebot import types

import config
from app.database import db
from app.keyboards import (
    create_main_menu,
    create_back_button,
    create_channel_button,
    create_shop_menu,
    create_payment_keyboard
)
from app.utils import (
    extract_username_and_message_id,
    report_message,
    create_invoice,
    check_payment,
    update_subscription
)

# Настройка логирования
logger = logging.getLogger(__name__)

# Словарь для отслеживания времени последнего использования функции
last_used = {}

def register_user_handlers(bot: TeleBot):
    """
    Регистрирует обработчики для пользовательских команд
    
    Args:
        bot: Экземпляр бота
    """
    @bot.message_handler(commands=['start'])
    def welcome(message):
        """Обработчик команды /start"""
        try:
            user_id = message.chat.id
            
            # Добавляем пользователя в базу, если его там нет
            if not db.user_exists(user_id):
                db.add_user(user_id)
                bot.send_message(
                    user_id, 
                    "👋 *Привет!*", 
                    reply_markup=create_channel_button(), 
                    parse_mode="Markdown"
                )
            
            # Отправляем приветственное сообщение
            bot.send_message(
                user_id, 
                f'♨️ *{config.bot_name}* — _инструмент для уничтожения аккаунтов._\n\n'
                f'⚡️ *Админ: {config.bot_admin}*\n'
                f'⭐️ *Отзывы:* [Reviews]({config.bot_reviews})\n'
                f'🔥 *Работы:* [Works]({config.bot_works})', 
                parse_mode="Markdown", 
                reply_markup=create_main_menu()
            )
            
            logger.info(f"Пользователь {user_id} запустил бота")
            
        except Exception as e:
            logger.error(f"Ошибка в обработчике /start: {e}")
    
    @bot.callback_query_handler(lambda c: c.data and c.data.startswith('sub_'))
    def handle_subscription(callback_query: types.CallbackQuery):
        """Обработчик выбора подписки"""
        try:
            user_id = callback_query.from_user.id
            
            if not db.user_exists(user_id):
                bot.send_message(
                    user_id, 
                    "*❗️ Вы блокировали бота! Пропишите /start*", 
                    parse_mode="Markdown"
                )
                return
            
            subscription_type = callback_query.data.split('_')[1]
            
            try:
                invoice = create_invoice(subscription_type)
                
                sub_days, amount, _ = get_subscription_params(subscription_type)
                
                pay_url = invoice['pay_url']
                invoice_id = invoice['invoice_id']
                
                bot.edit_message_text(
                    chat_id=callback_query.message.chat.id, 
                    message_id=callback_query.message.message_id,
                    text=f'⭐️ *Оплата подписки {config.bot_name}* ⭐️\n\n'
                         f'🛒 *Товар:* *Подписка на {sub_days} дней*\n'
                         f'💳 *Цена:* `{amount}$`\n\n'
                         f'✨ *Спасибо за ваш выбор!*',
                    parse_mode="Markdown", 
                    reply_markup=create_payment_keyboard(pay_url, invoice_id, subscription_type, sub_days)
                )
                
                logger.info(f"Пользователь {user_id} выбрал подписку на {sub_days} дней")
                
            except Exception as e:
                logger.error(f"Ошибка при создании счета: {e}")
                bot.answer_callback_query(
                    callback_query.id, 
                    "Произошла ошибка при создании счета. Попробуйте позже."
                )
                
        except Exception as e:
            logger.error(f"Ошибка в обработчике выбора подписки: {e}")
    
    @bot.callback_query_handler(lambda c: c.data and c.data.startswith('check_status_'))
    def check_status_callback(callback_query: types.CallbackQuery):
        """Обработчик проверки статуса оплаты"""
        try:
            user_id = callback_query.from_user.id
            
            if not db.user_exists(user_id):
                bot.send_message(
                    user_id, 
                    "*❗️ Вы блокировали бота! Пропишите /start*", 
                    parse_mode="Markdown"
                )
                return
            
            parts = callback_query.data.split('_')
            if len(parts) < 5:
                callback_query.answer("Неверный формат данных. Пожалуйста, попробуйте еще раз.")
                return
            
            invoice_id = parts[2]
            subscription_type = parts[3]
            sub_days = parts[4]
            
            try:
                invoice_data = check_payment(invoice_id)
                
                if invoice_data and invoice_data['status'] == "paid":
                    # Обновляем подписку
                    days = int(sub_days)
                    success = update_subscription(user_id, days)
                    
                    if success:
                        bot.edit_message_text(
                            chat_id=callback_query.message.chat.id, 
                            message_id=callback_query.message.message_id,
                            text=f'⭐️ *Оплачен!*',
                            parse_mode="Markdown", 
                            reply_markup=create_back_button()
                        )
                        bot.send_message(
                            callback_query.message.chat.id, 
                            "✨ *Оплата получена! Подписка активирована.*", 
                            parse_mode="Markdown"
                        )
                        
                        # Отправляем уведомление в лог-канал
                        subscribe_date = db.get_subscription_date(user_id)
                        markup = types.InlineKeyboardMarkup(row_width=1)
                        user_button = types.InlineKeyboardButton(f"Пользователь: {user_id}", url=f'tg://openmessage?user_id={user_id}')
                        markup.add(user_button)
                        
                        bot.send_message(
                            config.bot_logs, 
                            f'⚡️ *Пользователь* `{user_id}` *оплатил подписку (теперь действует до* `{subscribe_date}`*)*', 
                            parse_mode="Markdown", 
                            reply_markup=markup
                        )
                        
                        logger.info(f"Пользователь {user_id} оплатил подписку на {sub_days} дней")
                    else:
                        bot.send_message(
                            callback_query.message.chat.id, 
                            "❌ *Ошибка при активации подписки. Обратитесь к администратору.*", 
                            parse_mode="Markdown"
                        )
                        logger.error(f"Ошибка при обновлении подписки пользователя {user_id}")
                else:
                    bot.send_message(
                        callback_query.message.chat.id, 
                        "❌ *Оплата не получена!*", 
                        parse_mode="Markdown"
                    )
            except Exception as e:
                logger.error(f"Ошибка при проверке оплаты: {e}")
                bot.send_message(
                    callback_query.message.chat.id, 
                    "❌ *Произошла ошибка при проверке оплаты.*", 
                    parse_mode="Markdown"
                )
                
        except Exception as e:
            logger.error(f"Ошибка в обработчике проверки статуса: {e}")
    
    @bot.callback_query_handler(func=lambda call: True)
    def callback_inline(call):
        """Обработчик инлайн-кнопок"""
        try:
            user_id = call.from_user.id
            
            if not db.user_exists(user_id):
                bot.send_message(
                    user_id, 
                    "*❗️ Вы блокировали бота! Пропишите /start*", 
                    parse_mode="Markdown"
                )
                return
            
            subscribe_date = db.get_subscription_date(user_id)
            if not subscribe_date:
                bot.send_message(
                    call.message.chat.id, 
                    "❌ *Не удалось получить информацию о подписке. Попробуйте перезапустить бота командой /start*", 
                    parse_mode="Markdown"
                )
                return
            
            subsribe = datetime.strptime(subscribe_date, "%Y-%m-%d %H:%M:%S")
            
            if call.message:
                if call.data == 'snoser':
                    # Проверяем подписку
                    if subsribe < datetime.now():
                        bot.send_message(
                            call.message.chat.id, 
                            '⚡️ *Ваша подписка истекла!* \n\n💔 *Для использования функций обновите подписку.*', 
                            parse_mode="Markdown"
                        )
                    else:
                        # Проверяем кулдаун
                        if user_id in last_used and (datetime.now() - last_used[user_id]) < timedelta(minutes=config.COOLDOWN_MINUTES):
                            remaining_time = timedelta(minutes=config.COOLDOWN_MINUTES) - (datetime.now() - last_used[user_id])
                            bot.edit_message_text(
                                chat_id=call.message.chat.id, 
                                message_id=call.message.message_id,
                                text=f'❌ *Жди {remaining_time.seconds // 60} минут и {remaining_time.seconds % 60} секунд до следующей отправки жалоб!*',
                                parse_mode="Markdown", 
                                reply_markup=create_back_button()
                            )
                            return
                        
                        # Устанавливаем время последнего использования
                        last_used[user_id] = datetime.now()
                        
                        # Запрашиваем ссылку на сообщение
                        x = bot.send_message(
                            call.message.chat.id, 
                            f'⚡️ *Введите ссылку на нарушение:*', 
                            parse_mode="Markdown"
                        )
                        bot.register_next_step_handler(x, botnet_step1)
                        
                elif call.data == 'back':
                    # Возвращаемся в главное меню
                    bot.edit_message_text(
                        chat_id=call.message.chat.id, 
                        message_id=call.message.message_id,
                        text=f'♨️ *{config.bot_name}* — _инструмент для уничтожения аккаунтов._\n\n'
                             f'⚡️ *Админ: {config.bot_admin}*\n'
                             f'⭐️ *Отзывы:* [Reviews]({config.bot_reviews})\n'
                             f'🔥 *Работы:* [Works]({config.bot_works})',
                        parse_mode="Markdown", 
                        reply_markup=create_main_menu()
                    )
                    
                elif call.data == 'profile':
                    # Показываем профиль пользователя
                    bot.edit_message_text(
                        chat_id=call.message.chat.id, 
                        message_id=call.message.message_id,
                        text=f'⚡️ *Профиль пользователя* ⚡️\n\n'
                             f'🆔 *ID:* `{user_id}`\n'
                             f'🕐 *Текущее время:* `{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}`\n'
                             f'💰 *Подписка до:* `{subsribe}`\n\n'
                             f'🔐 _Не забудьте вовремя обновить свою подписку!_',
                        parse_mode="Markdown", 
                        reply_markup=create_back_button()
                    )
                    
                elif call.data == 'shop':
                    # Показываем магазин подписок
                    bot.edit_message_text(
                        chat_id=call.message.chat.id, 
                        message_id=call.message.message_id, 
                        text=(f"⚡️ *{config.bot_name} Price List* ⚡️\n\n"
                              f"🔹 *1 дeнь* — `{config.subscribe_1_day}$`\n"
                              f"🔹 *7 дней* — `{config.subscribe_7_days}$`\n"
                              f"🔹 *30 дней* — `{config.subscribe_30_days}$`\n"
                              f"🔹 *Навсегда* — `{config.subscribe_infinity_days}$`\n\n"
                              f"💼 *Для покупки за рубли: {config.bot_admin}*\n\n"
                              f"⚡️ *Работаем быстро!*"), 
                        parse_mode="Markdown", 
                        reply_markup=create_shop_menu(), 
                        disable_web_page_preview=True
                    )
                    
        except Exception as e:
            logger.error(f"Ошибка в обработчике callback: {e}")
    
    def botnet_step1(message):
        """Обработчик ввода ссылки на сообщение"""
        try:
            message_url = message.text
            user_id = message.from_user.id
            
            try:
                chat_username, message_id = extract_username_and_message_id(message_url)
                
                bot.send_message(
                    message.chat.id, 
                    '⚡️ *Отправка жалоб началась!\n\nПожалуйста, ожидайте.*', 
                    parse_mode="Markdown"
                )
                
                # Запускаем асинхронную функцию отправки жалоб
                asyncio.run(report_message(bot, chat_username, message_id, user_id))
                
            except ValueError as e:
                bot.send_message(
                    message.chat.id, 
                    f'⚡️ *{str(e)}*', 
                    parse_mode="Markdown"
                )
                
        except Exception as e:
            logger.error(f"Ошибка в обработчике botnet_step1: {e}")
            bot.send_message(
                message.chat.id, 
                "❌ *Произошла ошибка при обработке запроса.*", 
                parse_mode="Markdown", 
                reply_markup=create_back_button()
            ) 
from telebot import types
import config

def create_main_menu():
    """Создает главное меню бота"""
    menu = types.InlineKeyboardMarkup(row_width=2)
    profile = types.InlineKeyboardButton("👤 Профиль", callback_data='profile')
    doc = types.InlineKeyboardButton("📃 Инструкция", url=f'{config.bot_documentation}')
    shop = types.InlineKeyboardButton("🛍 Магазин", callback_data='shop')
    snoser = types.InlineKeyboardButton("🌐 BotNet", callback_data='snoser')
    menu.add(profile)
    menu.add(doc, shop)
    menu.add(snoser)
    return menu

def create_back_button():
    """Создает кнопку 'Назад'"""
    back_markup = types.InlineKeyboardMarkup(row_width=2)
    back = types.InlineKeyboardButton("❌ Назад", callback_data='back')
    back_markup.add(back)
    return back_markup

def create_channel_button():
    """Создает кнопку для канала бота"""
    channel_markup = types.InlineKeyboardMarkup(row_width=2)
    channel = types.InlineKeyboardButton(f"⚡️ {config.bot_name} - канал", url=f'{config.bot_channel_link}')
    channel_markup.add(channel)
    return channel_markup

def create_admin_menu():
    """Создает меню администратора"""
    admin_markup = types.InlineKeyboardMarkup(row_width=2)
    add_subsribe = types.InlineKeyboardButton("Выдать подписку", callback_data='add_subsribe')
    clear_subscribe = types.InlineKeyboardButton("Забрать подписку", callback_data='clear_subscribe')
    send_all = types.InlineKeyboardButton("Рассылка", callback_data='send_all')
    admin_markup.add(add_subsribe, clear_subscribe)
    admin_markup.add(send_all)
    return admin_markup

def create_shop_menu():
    """Создает меню магазина подписок"""
    shop_markup = types.InlineKeyboardMarkup(row_width=2)
    sub_1 = types.InlineKeyboardButton(f"🔹 1 день - {config.subscribe_1_day}$", callback_data='sub_1')
    sub_2 = types.InlineKeyboardButton(f"🔹 7 дней - {config.subscribe_7_days}$", callback_data='sub_2')
    sub_4 = types.InlineKeyboardButton(f"🔹 30 дней - {config.subscribe_30_days}$", callback_data='sub_4')
    sub_6 = types.InlineKeyboardButton(f"🔹 навсегда - {config.subscribe_infinity_days}$", callback_data='sub_6')
    back = types.InlineKeyboardButton("❌ Назад", callback_data='back')
    
    shop_markup.add(sub_1, sub_2)
    shop_markup.add(sub_4, sub_6)
    shop_markup.add(back)
    return shop_markup

def create_payment_keyboard(pay_url, invoice_id, subscription_type, sub_days):
    """Создает клавиатуру для оплаты"""
    pay_check = types.InlineKeyboardMarkup(row_width=2)
    pay_button = types.InlineKeyboardButton("💸 Оплатить", url=pay_url)
    check = types.InlineKeyboardButton(
        "🔍 Проверить оплату", 
        callback_data=f'check_status_{invoice_id}_{subscription_type}_{sub_days}'
    )
    back = types.InlineKeyboardButton("❌ Назад", callback_data='back')
    
    pay_check.add(pay_button, check)
    pay_check.add(back)
    return pay_check

def create_user_markup(user_id):
    """Создает клавиатуру с кнопкой профиля пользователя"""
    user_markup = types.InlineKeyboardMarkup(row_width=2)
    user_profile = types.InlineKeyboardButton(
        f"{user_id}", 
        url=f'tg://openmessage?user_id={user_id}'
    )
    user_markup.add(user_profile)
    return user_markup

def create_admin_user_markup(admin_id, user_id):
    """Создает клавиатуру с кнопками админа и пользователя"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    admin_button = types.InlineKeyboardButton(
        f"Админ: {admin_id}", 
        url=f'tg://openmessage?user_id={admin_id}'
    )
    user_button = types.InlineKeyboardButton(
        f"Пользователь: {user_id}", 
        url=f'tg://openmessage?user_id={user_id}'
    )
    markup.add(admin_button, user_button)
    return markup 
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

def create_admin_menu(admin_level):
    """
    Создает меню администратора в зависимости от уровня доступа
    
    Args:
        admin_level (int): Уровень доступа администратора
    
    Returns:
        types.InlineKeyboardMarkup: Клавиатура с доступными функциями
    """
    admin_markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Кнопки для наблюдателей (уровень 1)
    stats = types.InlineKeyboardButton("📊 Статистика", callback_data='admin_stats')
    users = types.InlineKeyboardButton("👥 Список пользователей", callback_data='admin_users')
    
    # Кнопки для модераторов (уровень 2)
    add_subscribe = types.InlineKeyboardButton("➕ Выдать подписку", callback_data='add_subsribe')
    clear_subscribe = types.InlineKeyboardButton("➖ Забрать подписку", callback_data='clear_subscribe')
    
    # Кнопки для полных админов (уровень 3)
    send_all = types.InlineKeyboardButton("📨 Рассылка", callback_data='send_all')
    add_admin = types.InlineKeyboardButton("👑 Управление админами", callback_data='admin_manage')
    system_settings = types.InlineKeyboardButton("⚙️ Настройки системы", callback_data='admin_settings')
    
    # Наблюдатель (уровень 1) и выше
    if admin_level >= config.ADMIN_LEVEL_OBSERVER:
        admin_markup.add(stats, users)
    
    # Модератор (уровень 2) и выше
    if admin_level >= config.ADMIN_LEVEL_MODERATOR:
        admin_markup.add(add_subscribe, clear_subscribe)
    
    # Полный админ (уровень 3)
    if admin_level >= config.ADMIN_LEVEL_FULL:
        admin_markup.add(send_all)
        admin_markup.add(add_admin, system_settings)
        
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

def create_admin_manage_menu():
    """Создает меню управления администраторами"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    add_admin = types.InlineKeyboardButton("➕ Добавить админа", callback_data='add_admin')
    edit_admin = types.InlineKeyboardButton("✏️ Изменить уровень", callback_data='edit_admin')
    remove_admin = types.InlineKeyboardButton("❌ Удалить админа", callback_data='remove_admin')
    list_admins = types.InlineKeyboardButton("📋 Список админов", callback_data='list_admins')
    back = types.InlineKeyboardButton("◀️ Назад", callback_data='admin_back')
    
    markup.add(add_admin, edit_admin)
    markup.add(remove_admin, list_admins)
    markup.add(back)
    return markup

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
import asyncio
import sqlite3
from telethon import Button, TelegramClient, events
from telethon.tl.types import User
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import re
import time

load_dotenv()

# Данные из https://my.telegram.org/
API_ID = int(os.getenv('API_ID', 'API_ID'))
API_HASH = os.getenv('API_HASH', 'API_HASH')
SESSION_NAME = 'WaitAssistent'

# ID админ-чата (Избранное/Saved Messages)
ADMIN_CHAT_ID = 'me'

# Инициализация клиента
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# Глобальные переменные для управления ботом
bot_active = False
last_messages = []  # Храним ID последних сообщений для удаления
selected_contacts = []  # для массовой рассылки
current_template_id = None  # для массовой рассылки
mailing_messages = []  # отдельный список для сообщений рассылки
scheduled_mailings = []  # список запланированных рассылок

# Инициализация БД
def init_db():
    conn = sqlite3.connect('telegram_assistant.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_mailings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            template_id INTEGER,
            contacts TEXT,
            send_time DATETIME,
            repeat_type TEXT,
            repeat_count INTEGER,
            repeat_interval INTEGER,
            status TEXT DEFAULT 'scheduled',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Стандартные шаблоны
    default_templates = [
        ('later', 'Отвечу позже! Сейчас занят, но обязательно напишу.'),
        ('busy', 'В данный момент занят, отвечу при первой возможности.'),
        ('thanks', 'Спасибо за сообщение! Изучил и скоро отвечу.'),
        ('quick', '⚡ Быстрый ответ: понял вас, подробнее отвечу позже!'),
        ('meeting', 'На совещании, напишу позже.'),
    ]
    
    for name, text in default_templates:
        cursor.execute('''
            INSERT OR IGNORE INTO templates (name, text) 
            VALUES (?, ?)
        ''', (name, text))
    
    conn.commit()
    conn.close()

# Функции для работы с БД
def get_templates():
    conn = sqlite3.connect('telegram_assistant.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, text FROM templates ORDER BY name')
    templates = cursor.fetchall()
    conn.close()
    return templates

def save_template(name, text):
    conn = sqlite3.connect('telegram_assistant.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO templates (name, text)
        VALUES (?, ?)
    ''', (name, text))
    conn.commit()
    conn.close()

def get_contacts():
    conn = sqlite3.connect('telegram_assistant.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, username, first_name, last_name, phone 
        FROM contacts 
        ORDER BY first_name
    ''')
    contacts = cursor.fetchall()
    conn.close()
    return contacts

def save_contact(user_id, username, first_name, last_name, phone):
    conn = sqlite3.connect('telegram_assistant.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO contacts (user_id, username, first_name, last_name, phone)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name, phone))
    conn.commit()
    conn.close()

def save_scheduled_mailing(name, template_id, contacts, send_time, repeat_type, repeat_count, repeat_interval):
    conn = sqlite3.connect('telegram_assistant.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO scheduled_mailings 
        (name, template_id, contacts, send_time, repeat_type, repeat_count, repeat_interval)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (name, template_id, ','.join(map(str, contacts)), send_time, repeat_type, repeat_count, repeat_interval))
    mailing_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return mailing_id

def get_scheduled_mailings():
    conn = sqlite3.connect('telegram_assistant.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, name, template_id, contacts, send_time, repeat_type, repeat_count, repeat_interval, status
        FROM scheduled_mailings 
        WHERE status = 'scheduled'
        ORDER BY send_time
    ''')
    mailings = cursor.fetchall()
    conn.close()
    return mailings

def update_mailing_status(mailing_id, status):
    conn = sqlite3.connect('telegram_assistant.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE scheduled_mailings 
        SET status = ? 
        WHERE id = ?
    ''', (status, mailing_id))
    conn.commit()
    conn.close()

def update_mailing_time_and_count(mailing_id, new_send_time, new_repeat_count):
    conn = sqlite3.connect('telegram_assistant.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE scheduled_mailings 
        SET send_time = ?, repeat_count = ?
        WHERE id = ?
    ''', (new_send_time, new_repeat_count, mailing_id))
    conn.commit()
    conn.close()

# Функции для управления сообщениями
async def send_message(chat_id, text, save_message=True, is_mailing=False):
    """Отправляет сообщение и сохраняет его ID для последующего удаления"""
    message = await client.send_message(chat_id, text)
    if save_message:
        if is_mailing:
            mailing_messages.append(message.id)
        else:
            last_messages.append(message.id)
            await asyncio.sleep(5)
    return message

async def delete_last_messages(chat_id, keep_last=0, is_mailing=False):
    """Удаляет последние сообщения бота"""
    global last_messages, mailing_messages
    
    messages_list = mailing_messages if is_mailing else last_messages
    
    if not messages_list:
        return
    
    # Оставляем указанное количество последних сообщений
    if keep_last > 0 and len(messages_list) > keep_last:
        messages_to_delete = messages_list[:-keep_last]
        if is_mailing:
            mailing_messages = mailing_messages[-keep_last:]
        else:
            last_messages = last_messages[-keep_last:]
    else:
        messages_to_delete = messages_list.copy()
        if is_mailing:
            mailing_messages = []
        else:
            last_messages = []
    
    for msg_id in messages_to_delete:
        try:
            await client.delete_messages(chat_id, msg_id)
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Не удалось удалить сообщение {msg_id}: {e}")

async def clear_chat_interface(chat_id, is_mailing=False):
    """Очищает интерфейс бота в чате"""
    await delete_last_messages(chat_id, is_mailing=is_mailing)

# Состояния пользователей {user_id: state}
user_states = {}

# Проверка что сообщение из админ-чата
def is_admin_chat(chat_id):
    return chat_id == ADMIN_CHAT_ID or (isinstance(chat_id, int) and chat_id == client._self_id)

# Главное меню (только в админ-чата)
async def show_main_menu(chat_id):
    if not is_admin_chat(chat_id):
        return
        
    await clear_chat_interface(chat_id)
    user_states[chat_id] = 'main_menu'
    
    contacts_count = len(get_contacts())
    templates_count = len(get_templates())
    scheduled_count = len(get_scheduled_mailings())
    
    text = f"""
🤖 **Панель управления ассистентом** 🚀

*Статистика:*
👥 Контактов: {contacts_count}
📝 Шаблонов: {templates_count}
⏰ Запланированных рассылок: {scheduled_count}

*Доступные команды:*
/start - Запустить бота
/menu - Главное меню  
/stop - Остановить бота и очистить чат
/clear - Очистить чат

*Быстрые действия (цифры):*
1️⃣ Контакты
2️⃣ Шаблоны  
3️⃣ Отправить сообщение
4️⃣ 📨 Массовая рассылка
5️⃣ ⏰ Отложенная рассылка
6️⃣ Обновить

💡 *Бот автоматически очищает за собой сообщения*
"""
    await send_message(chat_id, text)

# Меню контактов
async def show_contacts_menu(chat_id):
    if not is_admin_chat(chat_id):
        return
        
    await clear_chat_interface(chat_id)
    user_states[chat_id] = 'contacts_menu'
    
    text = """
👥 **Управление контактами**

*Доступные действия:*
1️⃣ Добавить контакт (перешлите сообщение)
2️⃣ Список контактов
3️⃣ Назад

💡 *Напишите цифру или /menu для возврата*
"""
    await send_message(chat_id, text)

# Меню шаблонов
async def show_templates_menu(chat_id):
    if not is_admin_chat(chat_id):
        return
        
    await clear_chat_interface(chat_id)
    user_states[chat_id] = 'templates_menu'
    
    text = """
📝 **Управление шаблонами**

*Доступные действия:*
1️⃣ Создать шаблон
2️⃣ Список шаблонов
3️⃣ Назад

💡 *Напишите цифру или /menu для возврата*
"""
    await send_message(chat_id, text)

# Меню массовой рассылки
async def show_mass_mailing_menu(chat_id):
    """Показывает меню массовой рассылки"""
    if not is_admin_chat(chat_id):
        return
        
    await clear_chat_interface(chat_id, is_mailing=True)
    user_states[chat_id] = 'mass_mailing_menu'
    
    # Получаем информацию о выбранном шаблоне
    template_info = "❌ Не выбран"
    if current_template_id:
        templates = get_templates()
        selected_template = next((t for t in templates if t[0] == current_template_id), None)
        if selected_template:
            template_info = f"✅ {selected_template[1]}"
    
    text = f"""
📨 **Массовая рассылка**

✅ Выбрано контактов: {len(selected_contacts)}
📝 Выбран шаблон: {template_info}

*Доступные действия:*
1️⃣ Выбрать контакты (по номерам)
2️⃣ Выбрать шаблон  
3️⃣ Начать рассылку
4️⃣ Статус рассылки
5️⃣ Остановить рассылку
6️⃣ Назад

💡 *Сначала выберите контакты и шаблон*
"""
    await send_message(chat_id, text, is_mailing=True)

# Меню отложенной рассылки
async def show_scheduled_mailing_menu(chat_id):
    """Показывает меню отложенной рассылки"""
    if not is_admin_chat(chat_id):
        return
        
    await clear_chat_interface(chat_id)
    user_states[chat_id] = 'scheduled_mailing_menu'
    
    scheduled_mailings = get_scheduled_mailings()
    
    text = f"""
⏰ **Отложенная рассылка**

📅 Запланировано: {len(scheduled_mailings)} рассылок

*Доступные действия:*
1️⃣ Создать отложенную рассылку
2️⃣ Список запланированных
3️⃣ Удалить рассылку
4️⃣ Назад

💡 *Рассылки выполняются автоматически в указанное время*
"""
    await send_message(chat_id, text)

# Запуск бота
async def start_bot(chat_id):
    global bot_active
    bot_active = True
    await clear_chat_interface(chat_id)
    await send_message(chat_id, "✅ **Бот запущен!**\nИспользуйте /menu для доступа к функциям")
    
    # Запускаем фоновую задачу для проверки отложенных рассылок
    asyncio.create_task(check_scheduled_mailings())
    
    # Показываем информацию о запланированных рассылках
    scheduled_mailings = get_scheduled_mailings()
    if scheduled_mailings:
        await send_message(
            chat_id,
            f"⏰ **Активные отложенные рассылки:** {len(scheduled_mailings)}\n"
            f"📊 Фоновая задача проверки запущена",
            save_message=False
        )
    
    await show_main_menu(chat_id)

# Остановка бота
async def stop_bot(chat_id):
    global bot_active
    bot_active = False
    await clear_chat_interface(chat_id)
    await send_message(chat_id, "🛑 **Бот остановлен**\nИспользуйте /start для повторного запуска", save_message=False)
    user_states.clear()

# Обработчики команд
@client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    if not is_admin_chat(event.chat_id):
        return
        
    await start_bot(event.chat_id)

@client.on(events.NewMessage(pattern='/menu'))
async def menu_handler(event):
    if not is_admin_chat(event.chat_id):
        return
        
    if not bot_active:
        await send_message(event.chat_id, "❌ Бот не запущен. Используйте /start")
        return
        
    await show_main_menu(event.chat_id)

@client.on(events.NewMessage(pattern='/stop'))
async def stop_handler(event):
    if not is_admin_chat(event.chat_id):
        return
        
    await stop_bot(event.chat_id)

@client.on(events.NewMessage(pattern='/clear'))
async def clear_handler(event):
    if not is_admin_chat(event.chat_id):
        return
        
    await clear_chat_interface(event.chat_id)
    await send_message(event.chat_id, "🧹 **Чат очищен**")

@client.on(events.NewMessage(pattern='/help'))
async def help_handler(event):
    if not is_admin_chat(event.chat_id):
        return
        
    text = """
📖 **Справка по командам:**

/start - Запустить бота
/stop - Остановить бота и очистить чат
/menu - Главное меню
/clear - Очистить чат от сообщений бота
/help - Эта справка

💡 *Бот автоматически удаляет свои сообщения при навигации*
"""
    await send_message(event.chat_id, text)

# Главный обработчик сообщений
@client.on(events.NewMessage)
async def message_handler(event):
    user_id = event.sender_id
    message_text = event.message.text.strip()
    chat_id = event.chat_id
    
    if not is_admin_chat(chat_id) or not bot_active:
        return

    current_state = user_states.get(chat_id, 'main_menu')
    
    print(f"Админка: '{message_text}' от {user_id}, состояние: {current_state}")

    # Обработка пересланных сообщений для добавления контактов
    if event.message.forward:
        if user_states.get(chat_id) == 'waiting_for_contact':
            await process_contact_addition(event, chat_id)
        else:
            await send_message(chat_id, "💡 Чтобы добавить контакт, сначала зайдите в *Контакты → Добавить контакт*")
        return
    
    # Обработка текстовых команд по состояниям
    if current_state == 'main_menu':
        await handle_main_menu(event, message_text, chat_id)
    
    elif current_state == 'contacts_menu':
        await handle_contacts_menu(event, message_text, chat_id)
    
    elif current_state == 'templates_menu':
        await handle_templates_menu(event, message_text, chat_id)
    
    elif current_state == 'mass_mailing_menu':
        await handle_mass_mailing_menu(event, message_text, chat_id)
    
    elif current_state == 'scheduled_mailing_menu':
        await handle_scheduled_mailing_menu(event, message_text, chat_id)
    
    elif current_state.startswith('waiting_template_'):
        await handle_template_creation(event, message_text, chat_id, current_state)
    
    elif current_state == 'selecting_contact':
        await handle_contact_selection(event, message_text, chat_id)
    
    elif current_state.startswith('sending_to_'):
        await handle_template_selection(event, message_text, chat_id, current_state)
    
    elif current_state.startswith('confirm_mailing_'):
        await handle_mailing_confirmation(event, message_text, chat_id, current_state)
    
    elif current_state == 'select_contacts_numbers':
        await handle_contact_numbers_selection(event, message_text, chat_id)
    
    elif current_state == 'select_template_mass':
        await handle_template_selection_mass(event, message_text, chat_id)
    
    elif current_state == 'scheduled_waiting_name':
        await handle_scheduled_name_input(event, message_text, chat_id)
    
    elif current_state == 'scheduled_waiting_time':
        await handle_scheduled_time_input(event, message_text, chat_id)
    
    elif current_state == 'scheduled_waiting_repeat':
        await handle_scheduled_repeat_input(event, message_text, chat_id)
    
    elif current_state == 'scheduled_waiting_delete':
        await handle_scheduled_delete_input(event, message_text, chat_id)

# Обработка главного меню
async def handle_main_menu(event, message_text, chat_id):
    if message_text == '1':
        await show_contacts_menu(chat_id)
    elif message_text == '2':
        await show_templates_menu(chat_id)
    elif message_text == '3':
        await show_send_message_menu(chat_id)
    elif message_text == '4':
        await show_mass_mailing_menu(chat_id)
    elif message_text == '5':
        await show_scheduled_mailing_menu(chat_id)
    elif message_text == '6':
        await show_main_menu(chat_id)
    else:
        await send_message(chat_id, "❌ Пожалуйста, выберите цифру от 1 до 6")
        await asyncio.sleep(2)
        await show_main_menu(chat_id)

# Обработка меню отложенной рассылки
async def handle_scheduled_mailing_menu(event, message_text, chat_id):
    if message_text == '1':
        await start_scheduled_mailing_creation(chat_id)
    elif message_text == '2':
        await show_scheduled_mailings_list(chat_id)
    elif message_text == '3':
        await show_scheduled_mailings_for_deletion(chat_id)
    elif message_text == '4' or message_text.lower() == 'назад':
        await show_main_menu(chat_id)
    else:
        await send_message(chat_id, "❌ Пожалуйста, выберите цифру от 1 до 4")
        await asyncio.sleep(2)
        await show_scheduled_mailing_menu(chat_id)

# Обработка меню контактов
async def handle_contacts_menu(event, message_text, chat_id):
    if message_text == '1':
        user_states[chat_id] = 'waiting_for_contact'
        await clear_chat_interface(chat_id)
        await send_message(
            chat_id,
            "👤 **Добавление контакта**\n\n"
            "Перешлите мне любое сообщение от человека, которого хотите добавить в контакты.\n\n"
            "Или напишите /menu для возврата:"
        )
    elif message_text == '2':
        await show_contacts_list(chat_id)
    elif message_text == '3' or message_text.lower() == 'назад':
        await show_main_menu(chat_id)
    else:
        await send_message(chat_id, "❌ Пожалуйста, выберите цифру от 1 до 3")
        await asyncio.sleep(2)
        await show_contacts_menu(chat_id)

# Обработка меню шаблонов
async def handle_templates_menu(event, message_text, chat_id):
    if message_text == '1':
        user_states[chat_id] = 'waiting_template_name'
        await clear_chat_interface(chat_id)
        await send_message(
            chat_id,
            "📝 **Создание шаблона**\n\n"
            "Введите название для нового шаблона:\n\n"
            "Или напишите /menu для возврата:"
        )
    elif message_text == '2':
        await show_templates_list(chat_id)
    elif message_text == '3' or message_text.lower() == 'назад':
        await show_main_menu(chat_id)
    else:
        await send_message(chat_id, "❌ Пожалуйста, выберите цифру от 1 до 3")
        await asyncio.sleep(2)
        await show_templates_menu(chat_id)

# Обработка меню массовой рассылки
async def handle_mass_mailing_menu(event, message_text, chat_id):
    if message_text == '1':
        await show_contact_selection(chat_id)
    elif message_text == '2':
        await show_template_selection_mass(chat_id)
    elif message_text == '3':
        if not selected_contacts:
            await send_message(chat_id, "❌ Сначала выберите контакты", is_mailing=True)
            return
        if not current_template_id:
            await send_message(chat_id, "❌ Сначала выберите шаблон", is_mailing=True)
            return
        await start_mass_mailing(chat_id)
    elif message_text == '4':
        # Простая заглушка для статуса рассылки
        await send_message(chat_id, "📭 Рассылка не активна", is_mailing=True)
    elif message_text == '5':
        # Простая заглушка для остановки рассылки
        await send_message(chat_id, "ℹ️ Рассылка не активна", is_mailing=True)
    elif message_text == '6' or message_text.lower() == 'назад':
        await show_main_menu(chat_id)
    else:
        await send_message(chat_id, "❌ Пожалуйста, выберите цифру от 1 до 6", is_mailing=True)
        await asyncio.sleep(2)
        await show_mass_mailing_menu(chat_id)

# ФУНКЦИИ ДЛЯ МАССОВОЙ РАССЫЛКИ

async def show_contact_selection(chat_id):
    """Показывает контакты для выбора по номерам"""
    user_states[chat_id] = 'select_contacts_numbers'
    
    contacts = get_contacts()
    
    if not contacts:
        await send_message(chat_id, "📝 Список контактов пуст", is_mailing=True)
        await show_mass_mailing_menu(chat_id)
        return
    
    text = "👥 **Выбор контактов для рассылки**\n\n"
    text += f"✅ Выбрано: {len(selected_contacts)} контактов\n\n"
    text += "**Список контактов:**\n\n"
    
    # Показываем все контакты с номерами
    for i, contact in enumerate(contacts, 1):
        id_, user_id, username, first_name, last_name, phone = contact
        name = f"{first_name} {last_name}" if last_name else first_name
        status = "✅" if user_id in selected_contacts else "⚪"
        
        contact_text = f"{status} {i}. {name}"
        if username:
            contact_text += f" (@{username})"
        
        text += f"{contact_text}\n"
    
    text += "\n💡 **Как выбрать:**"
    text += "\n• Введите номера контактов через пробел (например: 1 3 5)"
    text += "\n• Или диапазон (например: 1-5)"
    text += "\n• Или 'все' для выбора всех контактов"
    text += "\n• 'очистить' для сброса выбора"
    text += "\n• 'назад' для возврата в меню"
    text += f"\n\n📋 **Пример:** `1 3 5-7 10`"
    
    await send_message(chat_id, text, is_mailing=True)

async def show_template_selection_mass(chat_id):
    """Показывает шаблоны для выбора в массовой рассылке (по номерам)"""
    user_states[chat_id] = 'select_template_mass'
    
    templates = get_templates()
    
    if not templates:
        await send_message(chat_id, "📝 Список шаблонов пуст", is_mailing=True)
        await show_mass_mailing_menu(chat_id)
        return
    
    text = "📋 **Выберите шаблон для рассылки:**\n\n"
    
    for i, template in enumerate(templates, 1):
        id_, name, text_content = template
        preview = text_content[:50] + "..." if len(text_content) > 50 else text_content
        text += f"{i}. **{name}:** {preview}\n\n"
    
    text += "\n💡 *Введите номер шаблона:*"
    
    await send_message(chat_id, text, is_mailing=True)

async def start_mass_mailing(chat_id):
    """Запускает массовую рассылку"""
    if not selected_contacts:
        await send_message(chat_id, "❌ Не выбраны контакты для рассылки", is_mailing=True)
        return
    
    if not current_template_id:
        await send_message(chat_id, "❌ Не выбран шаблон для рассылки", is_mailing=True)
        return
    
    templates = get_templates()
    template = next((t for t in templates if t[0] == current_template_id), None)
    
    if not template:
        await send_message(chat_id, "❌ Шаблон не найден", is_mailing=True)
        return
    
    template_id, template_name, template_text = template
    
    # Подтверждение перед рассылкой
    text = f"""
⚠️ **Подтверждение рассылки**

📝 Шаблон: **{template_name}**
👥 Контактов: **{len(selected_contacts)}**
💬 Текст: {template_text[:100]}...

✅ Для начала отправьте "ДА"
❌ Для отмены отправьте "НЕТ"
"""
    user_states[chat_id] = f'confirm_mailing_{template_id}'
    await send_message(chat_id, text, is_mailing=True)

async def handle_contact_numbers_selection(event, message_text, chat_id):
    """Обрабатывает выбор контактов по номерам"""
    contacts = get_contacts()
    
    if message_text.lower() == 'назад':
        await show_mass_mailing_menu(chat_id)
        return
    
    elif message_text.lower() == 'все':
        # Выбираем все контакты
        selected_contacts.clear()
        selected_contacts.extend([c[1] for c in contacts])
        await send_message(chat_id, f"✅ Выбраны все контакты ({len(contacts)} шт.)", is_mailing=True)
        await show_mass_mailing_menu(chat_id)
        return
    
    elif message_text.lower() == 'очистить':
        # Очищаем выбор
        selected_contacts.clear()
        await send_message(chat_id, "🗑️ Выбор контактов очищен", is_mailing=True)
        await show_mass_mailing_menu(chat_id)
        return
    
    # Обрабатываем ввод номеров
    try:
        selected_numbers = set()
        
        # Разбиваем ввод на части
        parts = message_text.split()
        
        for part in parts:
            if '-' in part:
                # Обрабатываем диапазон (например: 1-5)
                range_parts = part.split('-')
                if len(range_parts) == 2:
                    start = int(range_parts[0])
                    end = int(range_parts[1])
                    selected_numbers.update(range(start, end + 1))
            else:
                # Обрабатываем отдельный номер
                selected_numbers.add(int(part))
        
        # Проверяем валидность номеров
        valid_numbers = []
        invalid_numbers = []
        
        for num in selected_numbers:
            if 1 <= num <= len(contacts):
                valid_numbers.append(num)
            else:
                invalid_numbers.append(num)
        
        if not valid_numbers:
            await send_message(chat_id, "❌ Не указано ни одного правильного номера", is_mailing=True)
            await show_mass_mailing_menu(chat_id)
            return
        
        # Обновляем выбранные контакты
        selected_contacts.clear()
        for num in valid_numbers:
            contact = contacts[num - 1]  # -1 потому что нумерация с 1
            selected_contacts.append(contact[1])
        
        # Формируем сообщение с результатами
        result_text = f"✅ Выбрано контактов: {len(valid_numbers)}\n\n"
        
        # Показываем выбранные контакты
        for i, num in enumerate(sorted(valid_numbers)[:10], 1):  # Показываем первые 10
            contact = contacts[num - 1]
            name = f"{contact[3]} {contact[4]}" if contact[4] else contact[3]
            result_text += f"{i}. {name}\n"
        
        if len(valid_numbers) > 10:
            result_text += f"... и еще {len(valid_numbers) - 10} контактов\n"
        
        if invalid_numbers:
            result_text += f"\n❌ Неверные номера: {', '.join(map(str, invalid_numbers))}"
        
        await send_message(chat_id, result_text, is_mailing=True)
        await show_mass_mailing_menu(chat_id)
        
    except ValueError:
        await send_message(chat_id, "❌ Ошибка формата. Используйте числа, пробелы и дефисы", is_mailing=True)
        await show_mass_mailing_menu(chat_id)
    except Exception as e:
        await send_message(chat_id, f"❌ Ошибка: {str(e)}", is_mailing=True)
        await show_mass_mailing_menu(chat_id)

async def handle_template_selection_mass(event, message_text, chat_id):
    """Обрабатывает выбор шаблона для массовой рассылки по номеру"""
    if message_text.lower() in ['/menu', 'назад']:
        await show_mass_mailing_menu(chat_id)
        return
    
    templates = get_templates()
    
    if message_text.isdigit():
        template_index = int(message_text) - 1
        if 0 <= template_index < len(templates):
            template = templates[template_index]
            global current_template_id
            current_template_id = template[0]
            
            await send_message(
                chat_id,
                f"✅ **Шаблон выбран!**\n\n"
                f"📝 **Название:** {template[1]}\n"
                f"💬 **Текст:** {template[2]}",
                is_mailing=True
            )
            await asyncio.sleep(2)
            await show_mass_mailing_menu(chat_id)
        else:
            await send_message(chat_id, "❌ Неверный номер шаблона", is_mailing=True)
            await asyncio.sleep(2)
            await show_template_selection_mass(chat_id)
    else:
        await send_message(chat_id, "❌ Пожалуйста, введите номер шаблона", is_mailing=True)
        await asyncio.sleep(2)
        await show_template_selection_mass(chat_id)

async def handle_mailing_confirmation(event, message_text, chat_id, current_state):
    if message_text.upper() == 'ДА':
        template_id = int(current_state.replace('confirm_mailing_', ''))
        templates = get_templates()
        template = next((t for t in templates if t[0] == template_id), None)
        
        if template:
            await send_message(chat_id, "🚀 Запускаю рассылку...", is_mailing=True)
            
            # Получаем контакты для рассылки
            contacts = get_contacts()
            contacts_to_send = [c for c in contacts if c[1] in selected_contacts]
            
            # Запускаем рассылку
            success_count = 0
            fail_count = 0
            results = []
            
            for i, contact in enumerate(contacts_to_send, 1):
                try:
                    await client.send_message(contact[1], template[2])
                    success_count += 1
                    result = {
                        'success': True,
                        'contact_name': f"{contact[3]} {contact[4]}" if contact[4] else contact[3],
                        'message': '✅ Отправлено'
                    }
                    results.append(result)
                    
                    # Обновляем прогресс каждые 5 сообщений или на последнем
                    if i % 5 == 0 or i == len(contacts_to_send):
                        progress_text = f"""
📨 **Идет рассылка...**

📊 Прогресс: {i}/{len(contacts_to_send)} ({i/len(contacts_to_send)*100:.1f}%)
✅ Успешно: {success_count}
❌ Ошибок: {fail_count}

👤 Текущий: {contact[3]}
"""
                        await send_message(chat_id, progress_text, save_message=False, is_mailing=True)
                    
                    await asyncio.sleep(2)  # Задержка между сообщениями
                    
                except Exception as e:
                    fail_count += 1
                    result = {
                        'success': False,
                        'contact_name': f"{contact[3]} {contact[4]}" if contact[4] else contact[3],
                        'message': f'❌ {str(e)}'
                    }
                    results.append(result)
                    print(f"Ошибка отправки {contact[3]}: {e}")
            
            # Показываем финальные результаты
            await complete_mass_mailing(chat_id, results)
            await asyncio.sleep(3)
            await show_main_menu(chat_id)
        
    elif message_text.upper() == 'НЕТ':
        await send_message(chat_id, "❌ Рассылка отменена", is_mailing=True)
        await show_mass_mailing_menu(chat_id)

async def complete_mass_mailing(chat_id, results: list):
    """Завершает рассылку и показывает результаты"""
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    text = f"""
🎉 **Рассылка завершена!**

📊 Результаты:
✅ Успешно: {len(successful)}
❌ Ошибок: {len(failed)}
📨 Всего: {len(results)}
"""
    await send_message(chat_id, text, save_message=False, is_mailing=True)
    
    # Детализация
    if failed:
        details = "❌ **Контакты с ошибками:**\n\n"
        for fail in failed[:10]:
            details += f"• {fail['contact_name']}: {fail['message']}\n"
        
        if len(failed) > 10:
            details += f"\n... и еще {len(failed) - 10} ошибок"
        
        await send_message(chat_id, details, save_message=False, is_mailing=True)
    
    # Очищаем выбранные контакты после рассылки
    selected_contacts.clear()

# ФУНКЦИИ ДЛЯ ОТЛОЖЕННОЙ РАССЫЛКИ

async def start_scheduled_mailing_creation(chat_id):
    """Начинает процесс создания отложенной рассылки"""
    if not selected_contacts:
        await send_message(chat_id, "❌ Сначала выберите контакты для рассылки")
        await show_mass_mailing_menu(chat_id)
        return
    
    if not current_template_id:
        await send_message(chat_id, "❌ Сначала выберите шаблон для рассылки")
        await show_mass_mailing_menu(chat_id)
        return
    
    user_states[chat_id] = 'scheduled_waiting_name'
    await send_message(
        chat_id,
        "⏰ **Создание отложенной рассылки**\n\n"
        "Введите название для этой рассылки:\n\n"
        "💡 *Пример: 'Новогодняя рассылка' или 'Напоминание о встрече'*"
    )

async def handle_scheduled_name_input(event, message_text, chat_id):
    """Обрабатывает ввод названия отложенной рассылки"""
    if message_text.lower() in ['/menu', 'назад']:
        await show_scheduled_mailing_menu(chat_id)
        return
    
    user_states[chat_id] = 'scheduled_waiting_time'
    user_states[f'{chat_id}_scheduled_name'] = message_text
    
    await send_message(
        chat_id,
        "🕐 **Укажите время отправки:**\n\n"
        "Формат: `ГГГГ-ММ-ДД ЧЧ:ММ`\n"
        "💡 *Примеры:*\n"
        "• `2024-12-31 23:59` - конкретная дата и время\n"
        "• `+2h` - через 2 часа\n"
        "• `+30m` - через 30 минут\n"
        "• `+1d` - через 1 день\n"
        "• `tomorrow 14:00` - завтра в 14:00\n\n"
        "Текущее время: " + datetime.now().strftime("%Y-%m-%d %H:%M")
    )

async def handle_scheduled_time_input(event, message_text, chat_id):
    """Обрабатывает ввод времени отправки"""
    if message_text.lower() in ['/menu', 'назад']:
        await show_scheduled_mailing_menu(chat_id)
        return
    
    try:
        send_time = parse_time_input(message_text)
        if not send_time:
            await send_message(chat_id, "❌ Неверный формат времени. Попробуйте снова:")
            return
        
        user_states[chat_id] = 'scheduled_waiting_repeat'
        user_states[f'{chat_id}_scheduled_time'] = send_time
        
        await send_message(
            chat_id,
            "🔄 **Настройка повтора:**\n\n"
            "Выберите тип повтора:\n"
            "1. 📅 Однократно (без повтора)\n"
            "2. 🔁 Ежедневно\n"
            "3. 📆 Еженедельно\n"
            "4. 📊 Ежемесячно\n"
            "5. ⏱️ С интервалом (в минутах)\n\n"
            "Введите номер варианта:"
        )
        
    except Exception as e:
        await send_message(chat_id, f"❌ Ошибка: {str(e)}\nПопробуйте снова:")

async def handle_scheduled_repeat_input(event, message_text, chat_id):
    """Обрабатывает ввод настроек повтора"""
    if message_text.lower() in ['/menu', 'назад']:
        await show_scheduled_mailing_menu(chat_id)
        return
    
    repeat_options = {
        '1': ('once', 1, 0),
        '2': ('daily', 0, 1440),  # 24 часа в минутах
        '3': ('weekly', 0, 10080),  # 7 дней в минутах
        '4': ('monthly', 0, 43200),  # 30 дней в минутах
    }
    
    if message_text in repeat_options:
        repeat_type, repeat_count, repeat_interval = repeat_options[message_text]
    elif message_text == '5':
        await send_message(
            chat_id,
            "⏱️ **Введите интервал в минутах:**\n\n"
            "💡 *Примеры:*\n"
            "• `60` - каждый час\n"
            "• `1440` - каждый день\n"
            "• `10080` - каждую неделю\n"
            "• `5` - каждые 5 минут\n\n"
            "Также укажите количество повторов (0 = бесконечно):\n"
            "Формат: `интервал_в_минутах количество_повторов`\n"
            "💡 *Пример:* `60 10` - каждые 60 минут, 10 раз"
        )
        user_states[f'{chat_id}_waiting_interval'] = True
        return
    else:
        # Парсим интервал вручную
        try:
            parts = message_text.split()
            if len(parts) == 2:
                repeat_interval = int(parts[0])
                repeat_count = int(parts[1])
                repeat_type = 'interval'
            else:
                await send_message(chat_id, "❌ Неверный формат. Попробуйте снова:")
                return
        except:
            await send_message(chat_id, "❌ Неверный формат. Введите номер от 1 до 5:")
            return
    
    # Сохраняем отложенную рассылку
    name = user_states.get(f'{chat_id}_scheduled_name')
    send_time = user_states.get(f'{chat_id}_scheduled_time')
    
    mailing_id = save_scheduled_mailing(
        name=name,
        template_id=current_template_id,
        contacts=selected_contacts,
        send_time=send_time.strftime("%Y-%m-%d %H:%M:%S"),
        repeat_type=repeat_type,
        repeat_count=repeat_count,
        repeat_interval=repeat_interval
    )
    
    # Очищаем временные данные
    for key in [f'{chat_id}_scheduled_name', f'{chat_id}_scheduled_time', f'{chat_id}_waiting_interval']:
        if key in user_states:
            del user_states[key]
    
    templates = get_templates()
    template = next((t for t in templates if t[0] == current_template_id), None)
    template_name = template[1] if template else "Неизвестный шаблон"
    
    await send_message(
        chat_id,
        f"✅ **Отложенная рассылка создана!**\n\n"
        f"📝 Название: {name}\n"
        f"🕐 Время: {send_time.strftime('%Y-%m-%d %H:%M')}\n"
        f"📋 Шаблон: {template_name}\n"
        f"👥 Контактов: {len(selected_contacts)}\n"
        f"🔄 Повтор: {get_repeat_description(repeat_type, repeat_count, repeat_interval)}\n"
        f"📊 ID: {mailing_id}"
    )
    
    await asyncio.sleep(3)
    await show_scheduled_mailing_menu(chat_id)

async def show_scheduled_mailings_list(chat_id):
    """Показывает список запланированных рассылок"""
    mailings = get_scheduled_mailings()
    
    if not mailings:
        await send_message(chat_id, "📭 Нет запланированных рассылок")
        await asyncio.sleep(2)
        await show_scheduled_mailing_menu(chat_id)
        return
    
    text = "📅 **Запланированные рассылки:**\n\n"
    
    for mailing in mailings:
        id_, name, template_id, contacts_str, send_time, repeat_type, repeat_count, repeat_interval, status = mailing
        contacts_count = len(contacts_str.split(',')) if contacts_str else 0
        
        templates = get_templates()
        template = next((t for t in templates if t[0] == template_id), None)
        template_name = template[1] if template else "Неизвестный шаблон"
        
        text += f"📊 **{name}** (ID: {id_})\n"
        text += f"🕐 {send_time}\n"
        text += f"📝 {template_name}\n"
        text += f"👥 {contacts_count} контактов\n"
        text += f"🔄 {get_repeat_description(repeat_type, repeat_count, repeat_interval)}\n"
        text += f"📊 Статус: {status}\n\n"
    
    await send_message(chat_id, text)
    await asyncio.sleep(3)
    await show_scheduled_mailing_menu(chat_id)

async def show_scheduled_mailings_for_deletion(chat_id):
    """Показывает рассылки для удаления"""
    mailings = get_scheduled_mailings()
    
    if not mailings:
        await send_message(chat_id, "📭 Нет запланированных рассылок для удаления")
        await asyncio.sleep(2)
        await show_scheduled_mailing_menu(chat_id)
        return
    
    text = "🗑️ **Выберите рассылку для удаления:**\n\n"
    
    for i, mailing in enumerate(mailings, 1):
        id_, name, template_id, contacts_str, send_time, repeat_type, repeat_count, repeat_interval, status = mailing
        text += f"{i}. **{name}** (ID: {id_})\n"
        text += f"   🕐 {send_time}\n\n"
    
    text += "💡 *Введите номер рассылки для удаления:*"
    
    user_states[chat_id] = 'scheduled_waiting_delete'
    user_states[f'{chat_id}_scheduled_mailings'] = mailings
    await send_message(chat_id, text)

async def handle_scheduled_delete_input(event, message_text, chat_id):
    """Обрабатывает удаление отложенной рассылки"""
    if message_text.lower() in ['/menu', 'назад']:
        await show_scheduled_mailing_menu(chat_id)
        return
    
    if not message_text.isdigit():
        await send_message(chat_id, "❌ Пожалуйста, введите номер рассылки:")
        return
    
    index = int(message_text) - 1
    mailings = user_states.get(f'{chat_id}_scheduled_mailings', [])
    
    if 0 <= index < len(mailings):
        mailing = mailings[index]
        mailing_id = mailing[0]
        mailing_name = mailing[1]
        
        update_mailing_status(mailing_id, 'cancelled')
        
        await send_message(
            chat_id,
            f"🗑️ **Рассылка удалена!**\n\n"
            f"📝 Название: {mailing_name}\n"
            f"📊 ID: {mailing_id}"
        )
        
        # Очищаем временные данные
        if f'{chat_id}_scheduled_mailings' in user_states:
            del user_states[f'{chat_id}_scheduled_mailings']
        
        await asyncio.sleep(2)
        await show_scheduled_mailing_menu(chat_id)
    else:
        await send_message(chat_id, "❌ Неверный номер рассылки. Попробуйте снова:")
        return

async def check_scheduled_mailings():
    """Фоновая задача для проверки и выполнения отложенных рассылок"""
    print("🕐 Запущена фоновая задача проверки отложенных рассылок")
    
    while True:
        try:
            if bot_active:
                mailings = get_scheduled_mailings()
                current_time = datetime.now()
                
                print(f"🔍 Проверяем {len(mailings)} отложенных рассылок...")
                
                for mailing in mailings:
                    id_, name, template_id, contacts_str, send_time, repeat_type, repeat_count, repeat_interval, status = mailing
                    
                    try:
                        # Преобразуем строку времени в datetime объект
                        send_time_dt = datetime.strptime(send_time, "%Y-%m-%d %H:%M:%S")
                        
                        print(f"📊 Рассылка '{name}': запланирована на {send_time_dt}, текущее время: {current_time}")
                        
                        # Проверяем, настало ли время отправки
                        if current_time >= send_time_dt:
                            print(f"🚀 Время отправки настало! Запускаем рассылку '{name}'")
                            await execute_scheduled_mailing(mailing)
                        else:
                            time_diff = send_time_dt - current_time
                            print(f"⏳ До отправки '{name}': {time_diff}")
                            
                    except Exception as e:
                        print(f"❌ Ошибка при проверке рассылки {name}: {e}")
            
            # Ждем 30 секунд перед следующей проверкой
            await asyncio.sleep(30)
            
        except Exception as e:
            print(f"❌ Критическая ошибка в check_scheduled_mailings: {e}")
            await asyncio.sleep(60)

async def execute_scheduled_mailing(mailing):
    """Выполняет отложенную рассылку"""
    id_, name, template_id, contacts_str, send_time, repeat_type, repeat_count, repeat_interval, status = mailing
    
    print(f"🎯 Начинаем выполнение отложенной рассылки: {name}")
    
    try:
        # Получаем данные для рассылки
        templates = get_templates()
        template = next((t for t in templates if t[0] == template_id), None)
        
        if not template:
            print(f"❌ Шаблон не найден для рассылки {name}")
            update_mailing_status(id_, 'failed')
            return
        
        contacts = get_contacts()
        contact_ids = [int(cid) for cid in contacts_str.split(',')] if contacts_str else []
        contacts_to_send = [c for c in contacts if c[1] in contact_ids]
        
        if not contacts_to_send:
            print(f"❌ Нет контактов для рассылки {name}")
            update_mailing_status(id_, 'failed')
            return
        
        print(f"📨 Начинаем рассылку '{name}' для {len(contacts_to_send)} контактов")
        
        # Выполняем рассылку
        success_count = 0
        fail_count = 0
        
        for i, contact in enumerate(contacts_to_send, 1):
            try:
                await client.send_message(contact[1], template[2])
                success_count += 1
                print(f"✅ Отправлено сообщение {i}/{len(contacts_to_send)} для {contact[3]}")
                
                # Задержка между сообщениями
                await asyncio.sleep(1)
                
            except Exception as e:
                fail_count += 1
                print(f"❌ Ошибка отправки для {contact[3]}: {e}")
        
        print(f"📊 Рассылка '{name}' завершена: {success_count} успешно, {fail_count} с ошибками")
        
        # Обрабатываем повтор рассылки
        if repeat_type != 'once' and (repeat_count > 1 or repeat_count == 0):
            # Вычисляем следующее время отправки
            current_send_time = datetime.strptime(send_time, "%Y-%m-%d %H:%M:%S")
            next_send_time = calculate_next_send_time(current_send_time, repeat_type, repeat_interval)
            
            # Уменьшаем счетчик повторов (если не бесконечно)
            new_repeat_count = repeat_count - 1 if repeat_count > 0 else 0
            
            # Обновляем время и счетчик в БД
            update_mailing_time_and_count(
                id_, 
                next_send_time.strftime("%Y-%m-%d %H:%M:%S"), 
                new_repeat_count
            )
            
            print(f"🔄 Запланирован повтор рассылки '{name}' на {next_send_time}")
            
        else:
            # Завершаем рассылку
            update_mailing_status(id_, 'completed')
            print(f"✅ Рассылка '{name}' завершена окончательно")
        
        # Отправляем уведомление в админ-чат
        notification_text = f"""
✅ **Отложенная рассылка выполнена**

📝 Название: {name}
🕐 Время: {datetime.now().strftime('%Y-%m-%d %H:%M')}
✅ Успешно: {success_count}/{len(contacts_to_send)}
❌ Ошибок: {fail_count}
"""
        
        if repeat_type != 'once' and (repeat_count > 1 or repeat_count == 0):
            notification_text += f"🔄 Следующая отправка: {calculate_next_send_time(datetime.strptime(send_time, '%Y-%m-%d %H:%M:%S'), repeat_type, repeat_interval).strftime('%Y-%m-%d %H:%M')}"
        
        await send_message(
            ADMIN_CHAT_ID,
            notification_text,
            save_message=False
        )
        
    except Exception as e:
        print(f"❌ Критическая ошибка выполнения рассылки {name}: {e}")
        update_mailing_status(id_, 'failed')
        
        # Отправляем уведомление об ошибке
        await send_message(
            ADMIN_CHAT_ID,
            f"❌ **Ошибка отложенной рассылки**\n\n"
            f"📝 Название: {name}\n"
            f"🕐 Время: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"💬 Ошибка: {str(e)}",
            save_message=False
        )

# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ОТЛОЖЕННОЙ РАССЫЛКИ

def parse_time_input(time_str):
    """Парсит ввод времени - УЛУЧШЕННАЯ ВЕРСИЯ"""
    time_str = time_str.strip().lower()
    current_time = datetime.now()
    
    print(f"🕐 Парсим время: '{time_str}'")
    
    try:
        # Формат: ГГГГ-ММ-ДД ЧЧ:ММ
        if re.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}', time_str):
            result = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
            print(f"✅ Распознан формат даты: {result}")
            return result
        
        # Формат: +Nh (часы)
        elif re.match(r'^\+\d+h$', time_str):
            hours = int(time_str[1:-1])
            result = current_time + timedelta(hours=hours)
            print(f"✅ Распознан формат +Nh: +{hours} часов = {result}")
            return result
        
        # Формат: +Nm (минуты)
        elif re.match(r'^\+\d+m$', time_str):
            minutes = int(time_str[1:-1])
            result = current_time + timedelta(minutes=minutes)
            print(f"✅ Распознан формат +Nm: +{minutes} минут = {result}")
            return result
        
        # Формат: +Nd (дни)
        elif re.match(r'^\+\d+d$', time_str):
            days = int(time_str[1:-1])
            result = current_time + timedelta(days=days)
            print(f"✅ Распознан формат +Nd: +{days} дней = {result}")
            return result
        
        # Формат: tomorrow HH:MM
        elif time_str.startswith('tomorrow'):
            try:
                time_part = time_str.split()[1]
                hours, minutes = map(int, time_part.split(':'))
                tomorrow = current_time + timedelta(days=1)
                result = tomorrow.replace(hour=hours, minute=minutes, second=0, microsecond=0)
                print(f"✅ Распознан формат tomorrow: {result}")
                return result
            except:
                return None
        
        # Формат: today HH:MM
        elif time_str.startswith('today'):
            try:
                time_part = time_str.split()[1]
                hours, minutes = map(int, time_part.split(':'))
                result = current_time.replace(hour=hours, minute=minutes, second=0, microsecond=0)
                if result < current_time:
                    result += timedelta(days=1)  # Если время уже прошло, ставим на завтра
                print(f"✅ Распознан формат today: {result}")
                return result
            except:
                return None
        
        # Формат: now (немедленно, для тестирования)
        elif time_str == 'now' or time_str == 'тест':
            result = current_time + timedelta(seconds=10)  # +10 секунд для теста
            print(f"✅ Распознан формат now (тест): {result}")
            return result
        
        else:
            print(f"❌ Неизвестный формат времени: {time_str}")
            return None
            
    except Exception as e:
        print(f"❌ Ошибка парсинга времени '{time_str}': {e}")
        return None

def calculate_next_send_time(current_send_time, repeat_type, repeat_interval):
    """Вычисляет следующее время отправки"""
    if repeat_type == 'daily':
        return current_send_time + timedelta(days=1)
    elif repeat_type == 'weekly':
        return current_send_time + timedelta(weeks=1)
    elif repeat_type == 'monthly':
        # Просто добавляем 30 дней для упрощения
        return current_send_time + timedelta(days=30)
    elif repeat_type == 'interval':
        return current_send_time + timedelta(minutes=repeat_interval)
    else:
        return current_send_time

def get_repeat_description(repeat_type, repeat_count, repeat_interval):
    """Возвращает описание повтора"""
    if repeat_type == 'once':
        return "Однократно"
    elif repeat_type == 'daily':
        return f"Ежедневно ({repeat_count} раз)" if repeat_count > 0 else "Ежедневно (бесконечно)"
    elif repeat_type == 'weekly':
        return f"Еженедельно ({repeat_count} раз)" if repeat_count > 0 else "Еженедельно (бесконечно)"
    elif repeat_type == 'monthly':
        return f"Ежемесячно ({repeat_count} раз)" if repeat_count > 0 else "Ежемесячно (бесконечно)"
    elif repeat_type == 'interval':
        if repeat_interval < 60:
            interval_desc = f"{repeat_interval} мин"
        elif repeat_interval < 1440:
            interval_desc = f"{repeat_interval // 60} ч"
        else:
            interval_desc = f"{repeat_interval // 1440} дн"
        
        if repeat_count > 0:
            return f"Каждые {interval_desc} ({repeat_count} раз)"
        else:
            return f"Каждые {interval_desc} (бесконечно)"
    else:
        return "Неизвестно"

# ОСТАЛЬНЫЕ НЕОБХОДИМЫЕ ФУНКЦИИ

async def show_send_message_menu(chat_id):
    if not is_admin_chat(chat_id):
        return
        
    contacts = get_contacts()
    templates = get_templates()
    
    if not contacts:
        await send_message(
            chat_id,
            "❌ **Нет контактов для отправки**\n\nСначала добавьте контакты через меню 'Контакты'"
        )
        await asyncio.sleep(2)
        await show_main_menu(chat_id)
        return
    
    if not templates:
        await send_message(
            chat_id,
            "❌ **Нет шаблонов для отправки**\n\nСначала создайте шаблоны через меню 'Шаблоны'"
        )
        await asyncio.sleep(2)
        await show_main_menu(chat_id)
        return
    
    await show_contacts_for_sending(chat_id)

async def show_contacts_for_sending(chat_id):
    if not is_admin_chat(chat_id):
        return
        
    await clear_chat_interface(chat_id)
    contacts = get_contacts()
    
    text = "👥 **Выберите контакт для отправки:**\n\n"
    
    for i, contact in enumerate(contacts, 1):
        id_, user_id, username, first_name, last_name, phone = contact
        name = f"{first_name} {last_name}" if last_name else first_name
        
        text += f"{i}. {name}\n"
    
    text += "\n💡 *Введите номер контакта:*"
    
    user_states[chat_id] = 'selecting_contact'
    await send_message(chat_id, text)

async def handle_contact_selection(event, message_text, chat_id):
    if message_text.lower() in ['/menu', 'назад']:
        await show_main_menu(chat_id)
        return
        
    if message_text.isdigit():
        contact_index = int(message_text) - 1
        contacts = get_contacts()
        
        if 0 <= contact_index < len(contacts):
            contact = contacts[contact_index]
            user_id_contact = contact[1]
            first_name = contact[3]
            
            user_states[chat_id] = f'sending_to_{user_id_contact}'
            await show_templates_for_contact(chat_id, user_id_contact, first_name)
        else:
            await send_message(chat_id, "❌ Неверный номер контакта")
            await asyncio.sleep(2)
            await show_contacts_for_sending(chat_id)
    else:
        await send_message(chat_id, "❌ Пожалуйста, введите номер контакта")
        await asyncio.sleep(2)
        await show_contacts_for_sending(chat_id)

async def show_templates_for_contact(chat_id, contact_id, contact_name):
    if not is_admin_chat(chat_id):
        return
        
    await clear_chat_interface(chat_id)
    templates = get_templates()
    
    text = f"📨 **Отправка сообщения для {contact_name}**\n\n"
    text += "📋 **Доступные шаблоны:**\n\n"
    
    for i, template in enumerate(templates, 1):
        template_id, name, text_content = template
        text += f"{i}. **{name}**\n"
    
    text += f"\n💡 *Введите номер или название шаблона:*"
    
    await send_message(chat_id, text)

async def handle_template_selection(event, message_text, chat_id, current_state):
    contact_id = int(current_state.replace('sending_to_', ''))
    
    if message_text.lower() in ['/menu', 'назад']:
        await show_contacts_for_sending(chat_id)
        return
    
    templates = get_templates()
    template = None
    
    # Поиск по номеру
    if message_text.isdigit():
        template_index = int(message_text) - 1
        if 0 <= template_index < len(templates):
            template = templates[template_index]
    
    # Поиск по названию
    if not template:
        template = next((t for t in templates if t[1].lower() == message_text.lower()), None)
    
    if template:
        await send_template_to_contact(chat_id, contact_id, template)
    else:
        await send_message(chat_id, "❌ Шаблон не найден. Пожалуйста, выберите номер или название из списка")
        await asyncio.sleep(2)
        contacts = get_contacts()
        contact = next((c for c in contacts if c[1] == contact_id), None)
        if contact:
            await show_templates_for_contact(chat_id, contact_id, contact[3])

async def send_template_to_contact(chat_id, contact_id, template):
    if not is_admin_chat(chat_id):
        return
        
    contacts = get_contacts()
    contact = next((c for c in contacts if c[1] == contact_id), None)
    
    if not contact:
        await send_message(chat_id, "❌ Контакт не найден")
        await asyncio.sleep(2)
        await show_main_menu(chat_id)
        return
    
    template_id, template_name, template_text = template
    id_, user_id, username, first_name, last_name, phone = contact
    name = f"{first_name} {last_name}" if last_name else first_name
    
    try:
        # Отправляем сообщение от твоего имени контакту!
        await client.send_message(user_id, template_text)
        
        # Это сообщение не сохраняем для удаления - оно должно остаться как подтверждение
        await send_message(
            chat_id,
            f"✅ **Сообщение отправлено!**\n\n"
            f"👤 **Кому:** {name}\n"
            f"📱 @{username if username else 'нет username'}\n"
            f"📝 **Шаблон:** {template_name}\n"
            f"💬 **Текст:** {template_text}",
            save_message=False
        )
        
    except Exception as e:
        await send_message(
            chat_id,
            f"❌ **Не удалось отправить сообщение**\n\n"
            f"Ошибка: {str(e)}\n\n"
            f"💡 *Возможно, пользователь заблокировал вас*",
            save_message=False
        )
    
    await asyncio.sleep(3)
    await show_main_menu(chat_id)

async def process_contact_addition(event, chat_id):
    try:
        original_sender = await event.message.forward.get_sender()
        if isinstance(original_sender, User):
            save_contact(
                original_sender.id,
                original_sender.username,
                original_sender.first_name,
                original_sender.last_name,
                original_sender.phone
            )
            name = f"{original_sender.first_name} {original_sender.last_name}" if original_sender.last_name else original_sender.first_name
            await send_message(
                chat_id,
                f"✅ **Контакт добавлен!**\n\n"
                f"👤 {name}\n"
                f"📱 @{original_sender.username if original_sender.username else 'нет username'}"
            )
            await asyncio.sleep(2)
            await show_contacts_menu(chat_id)
        else:
            await send_message(chat_id, "❌ Не удалось добавить контакт")
    except Exception as e:
        await send_message(chat_id, f"❌ Ошибка добавления контакта: {str(e)}")
        await asyncio.sleep(2)
        await show_contacts_menu(chat_id)

async def show_contacts_list(chat_id):
    if not is_admin_chat(chat_id):
        return
        
    await clear_chat_interface(chat_id)
    contacts = get_contacts()
    
    if not contacts:
        await send_message(
            chat_id,
            "📝 Список контактов пуст.\n\nДобавьте контакты через меню 'Добавить контакт'"
        )
    else:
        text = "👥 **Сохраненные контакты:**\n\n"
        
        for i, contact in enumerate(contacts, 1):
            id_, user_id, username, first_name, last_name, phone = contact
            name = f"{first_name} {last_name}" if last_name else first_name
            username_display = f"(@{username})" if username else ""
            
            text += f"{i}. {name} {username_display}\n"
        
        await send_message(chat_id, text)
    
    await asyncio.sleep(3)
    await show_contacts_menu(chat_id)

async def show_templates_list(chat_id):
    if not is_admin_chat(chat_id):
        return
        
    await clear_chat_interface(chat_id)
    templates = get_templates()
    
    if not templates:
        await send_message(
            chat_id,
            "📝 Список шаблонов пуст.\n\nСоздайте шаблоны через меню 'Создать шаблон'"
        )
    else:
        text = "📋 **Мои шаблоны:**\n\n"
        for template in templates:
            id_, name, text_content = template
            text_preview = text_content[:50] + "..." if len(text_content) > 50 else text_content
            text += f"• **{name}:** {text_preview}\n\n"
        
        await send_message(chat_id, text)
    
    await asyncio.sleep(3)
    await show_templates_menu(chat_id)

async def handle_template_creation(event, message_text, chat_id, current_state):
    if message_text.lower() in ['/menu', 'назад']:
        await show_templates_menu(chat_id)
        return
    
    if current_state == 'waiting_template_name':
        user_states[chat_id] = f'waiting_template_text_{message_text}'
        await send_message(
            chat_id,
            "📝 Теперь введите текст шаблона:\n\n"
            "Или напишите /menu для возврата:"
        )
    
    elif current_state.startswith('waiting_template_text_'):
        template_name = current_state.replace('waiting_template_text_', '')
        template_text = message_text
        save_template(template_name, template_text)
        
        await send_message(
            chat_id,
            f"✅ **Шаблон создан!**\n\n"
            f"📝 **Название:** {template_name}\n"
            f"💬 **Текст:** {template_text}"
        )
        await asyncio.sleep(2)
        await show_templates_menu(chat_id)

# Запуск клиента
async def main():
    init_db()
  
    print("🔑 Запуск Telegram клиента...")
    print("📱 Тебе нужно будет авторизоваться")
    
    await client.start()
    
    me = await client.get_me()
    print(f"✅ Успешный вход как: {me.first_name}")
    print("🤖 Умный ассистент с самоочисткой запущен!")
    print("💬 Работает ТОЛЬКО в Избранном (Saved Messages)")
    print("🧹 Автоматически удаляет свои сообщения при навигации")
    print("⏰ Система отложенной рассылки активирована")
    print("⚡ Команды: /start, /stop, /menu, /clear, /help")
    
    # Проверяем запланированные рассылки при старте
    scheduled_mailings = get_scheduled_mailings()
    print(f"📊 Найдено запланированных рассылок: {len(scheduled_mailings)}")
    
    # Отправляем приветственное сообщение (не удаляем его)
    await client.send_message(
        ADMIN_CHAT_ID,
        "🤖 **Умный ассистент готов к работе!**\n\n"
        "Используйте команды:\n"
        "/start - запустить бота\n"
        "/help - справка по командам\n\n"
        "💡 Бот автоматически очищает за собой сообщения\n"
        f"⏰ Активных отложенных рассылок: {len(scheduled_mailings)}"
    )
    
    print("✅ Система готова! Напишите /start в Избранном")
    
    try:
        await client.run_until_disconnected()
    except KeyboardInterrupt:
        print("\n Бот остановлен")
    finally:
        await client.disconnect()
        print("До свидания!")

if __name__ == '__main__':
    asyncio.run(main())

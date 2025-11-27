from database import db
from models.state_manager import state_manager

async def show_main_menu(chat_id, bot_manager):
    """Показывает главное меню"""
    if not bot_manager.is_admin_chat(chat_id):
        return
        
    # Очищаем интерфейс при показе главного меню
    await bot_manager.message_manager.clear_chat_interface(chat_id)
    state_manager.set_state(str(chat_id), 'main_menu')
    
    contacts_count = len(db.get_contacts())
    templates_count = len(db.get_templates())
    scheduled_count = len(db.get_scheduled_mailings())
    
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
    # Отправляем как меню-сообщение (будет заменять предыдущее меню)
    await bot_manager.message_manager.send_message(chat_id, text, is_menu=True)

async def show_send_message_menu(chat_id, bot_manager):
    """Показывает меню отправки сообщения"""
    if not bot_manager.is_admin_chat(chat_id):
        return
        
    contacts = db.get_contacts()
    templates = db.get_templates()
    
    if not contacts:
        await bot_manager.message_manager.send_message(
            chat_id,
            "❌ **Нет контактов для отправки**\n\nСначала добавьте контакты через меню 'Контакты'",
            is_menu=True
        )
        await asyncio.sleep(3)
        await show_main_menu(chat_id, bot_manager)
        return
    
    if not templates:
        await bot_manager.message_manager.send_message(
            chat_id,
            "❌ **Нет шаблонов для отправки**\n\nСначала создайте шаблоны через меню 'Шаблоны'",
            is_menu=True
        )
        await asyncio.sleep(3)
        await show_main_menu(chat_id, bot_manager)
        return
    
    await show_contacts_for_sending(chat_id, bot_manager)

async def show_contacts_for_sending(chat_id, bot_manager):
    """Показывает контакты для отправки сообщения"""
    if not bot_manager.is_admin_chat(chat_id):
        return
        
    # Очищаем интерфейс при переходе
    await bot_manager.message_manager.clear_chat_interface(chat_id)
    
    contacts = db.get_contacts()
    
    text = "👥 **Выберите контакт для отправки:**\n\n"
    
    for i, contact in enumerate(contacts, 1):
        name = f"{contact['first_name']} {contact['last_name']}" if contact['last_name'] else contact['first_name']
        text += f"{i}. {name}\n"
    
    text += "\n💡 *Введите номер контакта:*"
    
    state_manager.set_state(str(chat_id), 'selecting_contact')
    await bot_manager.message_manager.send_message(chat_id, text, is_menu=True)
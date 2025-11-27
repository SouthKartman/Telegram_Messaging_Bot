from database import db
from models.state_manager import state_manager

async def show_contacts_menu(chat_id, bot_manager):
    """Показывает меню контактов"""
    if not bot_manager.is_admin_chat(chat_id):
        return
        
    await bot_manager.message_manager.clear_chat_interface(chat_id)
    state_manager.set_state(str(chat_id), 'contacts_menu')
    
    text = """
👥 **Управление контактами**

*Доступные действия:*
1️⃣ Добавить контакт (перешлите сообщение)
2️⃣ Список контактов
3️⃣ Назад

💡 *Напишите цифру или /menu для возврата*
"""
    await bot_manager.message_manager.send_message(chat_id, text, is_menu=True)

async def show_contacts_list(chat_id, bot_manager):
    """Показывает список контактов"""
    if not bot_manager.is_admin_chat(chat_id):
        return
        
    contacts = db.get_contacts()
    
    if not contacts:
        text = "📝 Список контактов пуст.\n\nДобавьте контакты через меню 'Добавить контакт'"
    else:
        text = "👥 **Сохраненные контакты:**\n\n"
        
        for i, contact in enumerate(contacts, 1):
            name = f"{contact['first_name']} {contact['last_name']}" if contact['last_name'] else contact['first_name']
            username_display = f"(@{contact['username']})" if contact['username'] else ""
            
            text += f"{i}. {name} {username_display}\n"
    
    await bot_manager.message_manager.send_message(chat_id, text, is_menu=True)
    await asyncio.sleep(3)
    await show_contacts_menu(chat_id, bot_manager)
from database import db
from models.state_manager import state_manager

async def show_templates_menu(chat_id, bot_manager):
    """Показывает меню шаблонов"""
    if not bot_manager.is_admin_chat(chat_id):
        return
        
    await bot_manager.message_manager.clear_chat_interface(chat_id)
    state_manager.set_state(str(chat_id), 'templates_menu')
    
    text = """
📝 **Управление шаблонами**

*Доступные действия:*
1️⃣ Создать шаблон
2️⃣ Список шаблонов
3️⃣ Назад

💡 *Напишите цифру или /menu для возврата*
"""
    await bot_manager.message_manager.send_message(chat_id, text, is_menu=True)

async def show_templates_list(chat_id, bot_manager):
    """Показывает список шаблонов"""
    if not bot_manager.is_admin_chat(chat_id):
        return
        
    templates = db.get_templates()
    
    if not templates:
        text = "📝 Список шаблонов пуст.\n\nСоздайте шаблоны через меню 'Создать шаблон'"
    else:
        text = "📋 **Мои шаблоны:**\n\n"
        for template in templates:
            text_preview = template['text'][:50] + "..." if len(template['text']) > 50 else template['text']
            text += f"• **{template['name']}:** {text_preview}\n\n"
    
    await bot_manager.message_manager.send_message(chat_id, text, is_menu=True)
    await asyncio.sleep(3)
    await show_templates_menu(chat_id, bot_manager)

async def handle_template_creation(event, message_text, chat_id, current_state, bot_manager):
    """Обрабатывает создание шаблона"""
    from menus.main_menu import show_main_menu
    
    if message_text.lower() in ['/menu', 'назад']:
        await show_templates_menu(chat_id, bot_manager)
        return
    
    if current_state == 'waiting_template_name':
        state_manager.set_state(str(chat_id), f'waiting_template_text_{message_text}')
        await bot_manager.message_manager.send_message(
            chat_id,
            "📝 Теперь введите текст шаблона:\n\n"
            "Или напишите /menu для возврата:",
            is_menu=True
        )
    
    elif current_state.startswith('waiting_template_text_'):
        template_name = current_state.replace('waiting_template_text_', '')
        template_text = message_text
        db.save_template(template_name, template_text)
        
        await bot_manager.message_manager.send_message(
            chat_id,
            f"✅ **Шаблон создан!**\n\n"
            f"📝 **Название:** {template_name}\n"
            f"💬 **Текст:** {template_text}",
            is_menu=True
        )
        await asyncio.sleep(2)
        await show_templates_menu(chat_id, bot_manager)
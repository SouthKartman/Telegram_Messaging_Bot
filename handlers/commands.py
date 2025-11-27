from telethon import events
from config import config
from utils.message_utils import is_admin_chat
from menus.main_menu import show_main_menu
from models.state_manager import state_manager

class CommandHandlers:
    def __init__(self, client, bot_manager):
        self.client = client
        self.bot_manager = bot_manager
    
    async def start_handler(self, event):
        if not is_admin_chat(event.chat_id, self.client._self_id):
            return
        
        await self.bot_manager.start_bot(event.chat_id)
    
    async def menu_handler(self, event):
        if not is_admin_chat(event.chat_id, self.client._self_id):
            return
        
        if not self.bot_manager.bot_active:
            await self.bot_manager.message_manager.send_message(
                event.chat_id, "❌ Бот не запущен. Используйте /start"
            )
            return
        
        # Сбрасываем состояние и показываем главное меню
        state_manager.set_state(str(event.chat_id), 'main_menu')
        await show_main_menu(event.chat_id, self.bot_manager)
    
    async def stop_handler(self, event):
        if not is_admin_chat(event.chat_id, self.client._self_id):
            return
        
        await self.bot_manager.stop_bot(event.chat_id)
    
    async def clear_handler(self, event):
        if not is_admin_chat(event.chat_id, self.client._self_id):
            return
        
        # Используем полную очистку вместо частичной
        await self.bot_manager.message_manager.clear_all_messages(event.chat_id)
        await self.bot_manager.message_manager.send_message(
            event.chat_id, "🧹 **Чат полностью очищен**", save_message=False
        )
    
    async def help_handler(self, event):
        if not is_admin_chat(event.chat_id, self.client._self_id):
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
        await self.bot_manager.message_manager.send_message(event.chat_id, text)

def register_command_handlers(client, bot_manager):
    handlers = CommandHandlers(client, bot_manager)
    
    client.on(events.NewMessage(pattern='/start'))(handlers.start_handler)
    client.on(events.NewMessage(pattern='/menu'))(handlers.menu_handler)
    client.on(events.NewMessage(pattern='/stop'))(handlers.stop_handler)
    client.on(events.NewMessage(pattern='/clear'))(handlers.clear_handler)
    client.on(events.NewMessage(pattern='/help'))(handlers.help_handler)
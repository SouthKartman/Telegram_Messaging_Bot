import asyncio
from telethon import TelegramClient
from config import config
from database import db
from utils.message_utils import MessageManager, is_admin_chat
from handlers.commands import register_command_handlers
from handlers.messages import register_message_handlers

class BotManager:
    def __init__(self, client):
        self.client = client
        self.config = config
        self.bot_active = False
        self.message_manager = MessageManager(client)
    
    def is_admin_chat(self, chat_id):
        return is_admin_chat(chat_id, self.client._self_id)
    
    async def start_bot(self, chat_id):
        """Запускает бота"""
        self.bot_active = True
        await self.message_manager.clear_all_messages(chat_id)  # Полная очистка при старте
        await self.message_manager.send_message(
            chat_id, "✅ **Бот запущен!**\nИспользуйте /menu для доступа к функциям", save_message=False
        )
        
        # Запускаем фоновую задачу для проверки отложенных рассылок
        from menus.scheduled_mailing import scheduled_mailing_manager
        asyncio.create_task(scheduled_mailing_manager.check_scheduled_mailings(self))
        
        # Показываем информацию о запланированных рассылках
        scheduled_mailings = db.get_scheduled_mailings()
        if scheduled_mailings:
            await self.message_manager.send_message(
                chat_id,
                f"⏰ **Активные отложенные рассылки:** {len(scheduled_mailings)}\n"
                f"📊 Фоновая задача проверки запущена",
                save_message=False
            )
        
        from menus.main_menu import show_main_menu
        await show_main_menu(chat_id, self)
    
    async def stop_bot(self, chat_id):
        """Останавливает бота"""
        self.bot_active = False
        await self.message_manager.clear_chat_interface(chat_id)
        await self.message_manager.send_message(
            chat_id, "🛑 **Бот остановлен**\nИспользуйте /start для повторного запуска", save_message=False
        )
        
        from models.state_manager import state_manager
        state_manager.clear_state(str(chat_id))

async def main():
    # Инициализация базы данных
    db.init_db()
    
    # Создание клиента Telegram
    client = TelegramClient(
        config.bot.session_name,
        config.bot.api_id,
        config.bot.token
    )
    
    # Создание менеджера бота
    bot_manager = BotManager(client)
    
    # Регистрация обработчиков
    register_command_handlers(client, bot_manager)
    register_message_handlers(client, bot_manager)
    
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
    scheduled_mailings = db.get_scheduled_mailings()
    print(f"📊 Найдено запланированных рассылок: {len(scheduled_mailings)}")
    
    # Отправляем приветственное сообщение
    await client.send_message(
        config.bot.admin_chat_id,
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
        print("\n🛑 Бот остановлен")
    finally:
        await client.disconnect()
        print("👋 До свидания!")

if __name__ == '__main__':
    asyncio.run(main())
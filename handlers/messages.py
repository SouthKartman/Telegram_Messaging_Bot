import asyncio
from telethon import events
from telethon.tl.types import User
from config import config
from utils.message_utils import is_admin_chat
from models.state_manager import state_manager
from database import db

class MessageHandlers:
    def __init__(self, client, bot_manager):
        self.client = client
        self.bot_manager = bot_manager
    
    async def handle_message(self, event):
        user_id = event.sender_id
        message_text = event.message.text.strip() if event.message.text else ""
        chat_id = event.chat_id
        
        if not is_admin_chat(chat_id, self.client._self_id) or not self.bot_manager.bot_active:
            return

        current_state = state_manager.get_state(str(chat_id)) or 'main_menu'
        
        print(f"Админка: '{message_text}' от {user_id}, состояние: {current_state}")

        # Сохраняем сообщение пользователя для последующего удаления
        await self.bot_manager.message_manager.save_user_message(chat_id, event.message.id)

        # Обработка пересланных сообщений для добавления контактов
        if event.message.forward:
            if state_manager.get_state(str(chat_id)) == 'waiting_for_contact':
                await self.process_contact_addition(event, chat_id)
            else:
                await self.bot_manager.message_manager.send_message(
                    chat_id, 
                    "💡 Чтобы добавить контакт, сначала зайдите в *Контакты → Добавить контакт*"
                )
            return
        
        # Обработка текстовых команд по состояниям
        await self.route_by_state(event, message_text, chat_id, current_state)
    
    async def route_by_state(self, event, message_text, chat_id, current_state):
        """Маршрутизирует сообщения по состояниям"""
        # Сначала проверяем специальные состояния
        if current_state.startswith('waiting_template_'):
            await self.handle_template_creation(event, message_text, chat_id, current_state)
            return
        
        if current_state.startswith('confirm_mailing_'):
            await self.handle_mailing_confirmation(event, message_text, chat_id, current_state)
            return
        
        if current_state.startswith('sending_to_'):
            await self.handle_template_selection(event, message_text, chat_id, current_state)
            return
        
        # Затем основные состояния меню
        state_handlers = {
            'main_menu': self.handle_main_menu,
            'contacts_menu': self.handle_contacts_menu,
            'templates_menu': self.handle_templates_menu,
            'mass_mailing_menu': self.handle_mass_mailing_menu,
            'scheduled_mailing_menu': self.handle_scheduled_mailing_menu,
            'selecting_contact': self.handle_contact_selection,
            'select_contacts_numbers': self.handle_contact_numbers_selection,
            'select_template_mass': self.handle_template_selection_mass,
            'scheduled_waiting_name': self.handle_scheduled_name_input,
            'scheduled_waiting_time': self.handle_scheduled_time_input,
            'scheduled_waiting_repeat': self.handle_scheduled_repeat_input,
            'scheduled_waiting_delete': self.handle_scheduled_delete_input,
            'waiting_for_contact': self.handle_waiting_for_contact,
        }
        
        if current_state in state_handlers:
            await state_handlers[current_state](event, message_text, chat_id)
        else:
            print(f"❌ Неизвестное состояние: {current_state}")
            await self.bot_manager.message_manager.send_message(
                chat_id, f"❌ Неизвестное состояние: {current_state}. Возврат в главное меню."
            )
            from menus.main_menu import show_main_menu
            await show_main_menu(chat_id, self.bot_manager)
    
    # ОСНОВНЫЕ ОБРАБОТЧИКИ МЕНЮ
    
    async def handle_main_menu(self, event, message_text, chat_id):
        """Обрабатывает главное меню"""
        from menus.main_menu import show_main_menu
        from menus.contacts_menu import show_contacts_menu
        from menus.templates_menu import show_templates_menu
        from menus.mass_mailing import show_mass_mailing_menu
        from menus.scheduled_mailing import show_scheduled_mailing_menu
        
        # Очищаем интерфейс при переходе между меню
        await self.bot_manager.message_manager.clear_chat_interface(chat_id)
        
        menu_actions = {
            '1': lambda: show_contacts_menu(chat_id, self.bot_manager),
            '2': lambda: show_templates_menu(chat_id, self.bot_manager),
            '3': lambda: self.show_send_message_menu(chat_id),
            '4': lambda: show_mass_mailing_menu(chat_id, self.bot_manager),
            '5': lambda: show_scheduled_mailing_menu(chat_id, self.bot_manager),
            '6': lambda: show_main_menu(chat_id, self.bot_manager),
        }
        
        if message_text in menu_actions:
            await menu_actions[message_text]()
        else:
            await self.bot_manager.message_manager.send_message(
                chat_id, "❌ Пожалуйста, выберите цифру от 1 до 6"
            )
            await show_main_menu(chat_id, self.bot_manager)
    
    async def handle_contacts_menu(self, event, message_text, chat_id):
        """Обрабатывает меню контактов"""
        from menus.contacts_menu import show_contacts_menu, show_contacts_list
        from menus.main_menu import show_main_menu
        
        # Очищаем интерфейс при переходе между меню
        await self.bot_manager.message_manager.clear_chat_interface(chat_id)
        
        if message_text == '1':
            state_manager.set_state(str(chat_id), 'waiting_for_contact')
            await self.bot_manager.message_manager.send_message(
                chat_id,
                "👤 **Добавление контакта**\n\n"
                "Перешлите мне любое сообщение от человека, которого хотите добавить в контакты.\n\n"
                "Или напишите /menu для возврата:",
                is_menu=True
            )
        elif message_text == '2':
            await show_contacts_list(chat_id, self.bot_manager)
        elif message_text == '3' or message_text.lower() == 'назад':
            await show_main_menu(chat_id, self.bot_manager)
        else:
            await self.bot_manager.message_manager.send_message(
                chat_id, "❌ Пожалуйста, выберите цифру от 1 до 3"
            )
            await show_contacts_menu(chat_id, self.bot_manager)
    
    async def handle_templates_menu(self, event, message_text, chat_id):
        """Обрабатывает меню шаблонов"""
        from menus.templates_menu import show_templates_menu, show_templates_list
        from menus.main_menu import show_main_menu
        
        # Очищаем интерфейс при переходе между меню
        await self.bot_manager.message_manager.clear_chat_interface(chat_id)
        
        if message_text == '1':
            state_manager.set_state(str(chat_id), 'waiting_template_name')
            await self.bot_manager.message_manager.send_message(
                chat_id,
                "📝 **Создание шаблона**\n\n"
                "Введите название для нового шаблона:\n\n"
                "Или напишите /menu для возврата:",
                is_menu=True
            )
        elif message_text == '2':
            await show_templates_list(chat_id, self.bot_manager)
        elif message_text == '3' or message_text.lower() == 'назад':
            await show_main_menu(chat_id, self.bot_manager)
        else:
            await self.bot_manager.message_manager.send_message(
                chat_id, "❌ Пожалуйста, выберите цифру от 1 до 3"
            )
            await show_templates_menu(chat_id, self.bot_manager)
    
    async def handle_mass_mailing_menu(self, event, message_text, chat_id):
        """Обрабатывает меню массовой рассылки"""
        from menus.mass_mailing import (
            show_mass_mailing_menu, show_contact_selection, 
            show_template_selection_mass, start_mass_mailing
        )
        from menus.main_menu import show_main_menu
        
        # Очищаем интерфейс при переходе между меню
        await self.bot_manager.message_manager.clear_chat_interface(chat_id, is_mailing=True)
        
        menu_actions = {
            '1': lambda: show_contact_selection(chat_id, self.bot_manager),
            '2': lambda: show_template_selection_mass(chat_id, self.bot_manager),
            '3': lambda: start_mass_mailing(chat_id, self.bot_manager),
            '4': lambda: self.bot_manager.message_manager.send_message(
                chat_id, "📭 Рассылка не активна", is_mailing=True
            ),
            '5': lambda: self.bot_manager.message_manager.send_message(
                chat_id, "ℹ️ Рассылка не активна", is_mailing=True
            ),
            '6': lambda: show_main_menu(chat_id, self.bot_manager),
        }
        
        if message_text in menu_actions:
            await menu_actions[message_text]()
        else:
            await self.bot_manager.message_manager.send_message(
                chat_id, "❌ Пожалуйста, выберите цифру от 1 до 6", is_mailing=True
            )
            await show_mass_mailing_menu(chat_id, self.bot_manager)
    
    async def handle_scheduled_mailing_menu(self, event, message_text, chat_id):
        """Обрабатывает меню отложенной рассылки"""
        from menus.scheduled_mailing import (
            show_scheduled_mailing_menu, start_scheduled_mailing_creation,
            show_scheduled_mailings_list, show_scheduled_mailings_for_deletion
        )
        from menus.main_menu import show_main_menu
        
        # Очищаем интерфейс при переходе между меню
        await self.bot_manager.message_manager.clear_chat_interface(chat_id)
        
        menu_actions = {
            '1': lambda: start_scheduled_mailing_creation(chat_id, self.bot_manager),
            '2': lambda: show_scheduled_mailings_list(chat_id, self.bot_manager),
            '3': lambda: show_scheduled_mailings_for_deletion(chat_id, self.bot_manager),
            '4': lambda: show_main_menu(chat_id, self.bot_manager),
        }
        
        if message_text in menu_actions:
            await menu_actions[message_text]()
        else:
            await self.bot_manager.message_manager.send_message(
                chat_id, "❌ Пожалуйста, выберите цифру от 1 до 4"
            )
            await show_scheduled_mailing_menu(chat_id, self.bot_manager)
    
    async def handle_waiting_for_contact(self, event, message_text, chat_id):
        """Обрабатывает состояние ожидания контакта"""
        if message_text.lower() in ['/menu', 'назад']:
            from menus.contacts_menu import show_contacts_menu
            await show_contacts_menu(chat_id, self.bot_manager)
        else:
            await self.bot_manager.message_manager.send_message(
                chat_id,
                "💡 Перешлите сообщение от контакта или напишите /menu для возврата",
                is_menu=True
            )
    
    # ОБРАБОТКА ОТПРАВКИ СООБЩЕНИЙ
    
    async def handle_contact_selection(self, event, message_text, chat_id):
        """Обрабатывает выбор контакта для отправки сообщения"""
        from menus.main_menu import show_main_menu
        
        if message_text.lower() in ['/menu', 'назад']:
            await show_main_menu(chat_id, self.bot_manager)
            return
            
        if message_text.isdigit():
            contact_index = int(message_text) - 1
            contacts = db.get_contacts()
            
            if 0 <= contact_index < len(contacts):
                contact = contacts[contact_index]
                user_id_contact = contact['user_id']
                first_name = contact['first_name']
                
                state_manager.set_state(str(chat_id), f'sending_to_{user_id_contact}')
                await self.show_templates_for_contact(chat_id, user_id_contact, first_name)
            else:
                await self.bot_manager.message_manager.send_message(chat_id, "❌ Неверный номер контакта")
                await self.show_contacts_for_sending(chat_id)
        else:
            await self.bot_manager.message_manager.send_message(chat_id, "❌ Пожалуйста, введите номер контакта")
            await self.show_contacts_for_sending(chat_id)
    
    async def handle_template_selection(self, event, message_text, chat_id, current_state):
        """Обрабатывает выбор шаблона для отправки"""
        contact_id = int(current_state.replace('sending_to_', ''))
        
        if message_text.lower() in ['/menu', 'назад']:
            await self.show_contacts_for_sending(chat_id)
            return
        
        templates = db.get_templates()
        template = None
        
        # Поиск по номеру
        if message_text.isdigit():
            template_index = int(message_text) - 1
            if 0 <= template_index < len(templates):
                template = templates[template_index]
        
        # Поиск по названию
        if not template:
            template = next((t for t in templates if t['name'].lower() == message_text.lower()), None)
        
        if template:
            await self.send_template_to_contact(chat_id, contact_id, template)
        else:
            await self.bot_manager.message_manager.send_message(
                chat_id, "❌ Шаблон не найден. Пожалуйста, выберите номер или название из списка"
            )
            contacts = db.get_contacts()
            contact = next((c for c in contacts if c['user_id'] == contact_id), None)
            if contact:
                await self.show_templates_for_contact(chat_id, contact_id, contact['first_name'])
    
    async def show_templates_for_contact(self, chat_id, contact_id, contact_name):
        """Показывает шаблоны для выбора контакту"""
        if not self.bot_manager.is_admin_chat(chat_id):
            return
            
        templates = db.get_templates()
        
        text = f"📨 **Отправка сообщения для {contact_name}**\n\n"
        text += "📋 **Доступные шаблоны:**\n\n"
        
        for i, template in enumerate(templates, 1):
            text += f"{i}. **{template['name']}**\n"
        
        text += f"\n💡 *Введите номер или название шаблона:*"
        
        await self.bot_manager.message_manager.send_message(chat_id, text, is_menu=True)
    
    async def send_template_to_contact(self, chat_id, contact_id, template):
        """Отправляет шаблон контакту"""
        if not self.bot_manager.is_admin_chat(chat_id):
            return
            
        contacts = db.get_contacts()
        contact = next((c for c in contacts if c['user_id'] == contact_id), None)
        
        if not contact:
            await self.bot_manager.message_manager.send_message(chat_id, "❌ Контакт не найден")
            from menus.main_menu import show_main_menu
            await show_main_menu(chat_id, self.bot_manager)
            return
        
        template_name, template_text = template['name'], template['text']
        name = f"{contact['first_name']} {contact['last_name']}" if contact['last_name'] else contact['first_name']
        
        try:
            # Отправляем сообщение контакту
            await self.client.send_message(contact_id, template_text)
            
            # Сообщение подтверждения
            await self.bot_manager.message_manager.send_message(
                chat_id,
                f"✅ **Сообщение отправлено!**\n\n"
                f"👤 **Кому:** {name}\n"
                f"📱 @{contact['username'] if contact['username'] else 'нет username'}\n"
                f"📝 **Шаблон:** {template_name}\n"
                f"💬 **Текст:** {template_text}",
                save_message=False
            )
            
        except Exception as e:
            await self.bot_manager.message_manager.send_message(
                chat_id,
                f"❌ **Не удалось отправить сообщение**\n\n"
                f"Ошибка: {str(e)}\n\n"
                f"💡 *Возможно, пользователь заблокировал вас*",
                save_message=False
            )
        
        from menus.main_menu import show_main_menu
        await show_main_menu(chat_id, self.bot_manager)
    
    async def show_contacts_for_sending(self, chat_id):
        """Показывает контакты для отправки"""
        from menus.main_menu import show_contacts_for_sending as show_contacts
        await show_contacts(chat_id, self.bot_manager)
    
    async def show_send_message_menu(self, chat_id):
        """Показывает меню отправки сообщения"""
        from menus.main_menu import show_send_message_menu as show_send_menu
        await show_send_menu(chat_id, self.bot_manager)
    
    # ОБРАБОТКА МАССОВОЙ РАССЫЛКИ
    
    async def handle_contact_numbers_selection(self, event, message_text, chat_id):
        """Обрабатывает выбор контактов по номерам"""
        from menus.mass_mailing import handle_contact_numbers_selection
        await handle_contact_numbers_selection(event, message_text, chat_id, self.bot_manager)
    
    async def handle_template_selection_mass(self, event, message_text, chat_id):
        """Обрабатывает выбор шаблона для массовой рассылки"""
        from menus.mass_mailing import handle_template_selection_mass
        await handle_template_selection_mass(event, message_text, chat_id, self.bot_manager)
    
    async def handle_mailing_confirmation(self, event, message_text, chat_id, current_state):
        """Обрабатывает подтверждение рассылки"""
        from menus.mass_mailing import handle_mailing_confirmation
        await handle_mailing_confirmation(event, message_text, chat_id, current_state, self.bot_manager)
    
    # ОБРАБОТКА ОТЛОЖЕННОЙ РАССЫЛКИ
    
    async def handle_scheduled_name_input(self, event, message_text, chat_id):
        """Обрабатывает ввод названия отложенной рассылки"""
        from menus.scheduled_mailing import handle_scheduled_name_input
        await handle_scheduled_name_input(event, message_text, chat_id, self.bot_manager)
    
    async def handle_scheduled_time_input(self, event, message_text, chat_id):
        """Обрабатывает ввод времени отправки"""
        from menus.scheduled_mailing import handle_scheduled_time_input
        await handle_scheduled_time_input(event, message_text, chat_id, self.bot_manager)
    
    async def handle_scheduled_repeat_input(self, event, message_text, chat_id):
        """Обрабатывает ввод настроек повтора"""
        from menus.scheduled_mailing import handle_scheduled_repeat_input
        await handle_scheduled_repeat_input(event, message_text, chat_id, self.bot_manager)
    
    async def handle_scheduled_delete_input(self, event, message_text, chat_id):
        """Обрабатывает удаление отложенной рассылки"""
        from menus.scheduled_mailing import handle_scheduled_delete_input
        await handle_scheduled_delete_input(event, message_text, chat_id, self.bot_manager)
    
    # ОБРАБОТКА ШАБЛОНОВ
    
    async def handle_template_creation(self, event, message_text, chat_id, current_state):
        """Обрабатывает создание шаблона"""
        from menus.templates_menu import handle_template_creation
        await handle_template_creation(event, message_text, chat_id, current_state, self.bot_manager)
    
    # ДОБАВЛЕНИЕ КОНТАКТОВ
    
    async def process_contact_addition(self, event, chat_id):
        """Обрабатывает добавление контакта из пересланного сообщения"""
        try:
            original_sender = await event.message.forward.get_sender()
            if isinstance(original_sender, User):
                db.save_contact(
                    original_sender.id,
                    original_sender.username or "",
                    original_sender.first_name or "",
                    original_sender.last_name or "",
                    original_sender.phone or ""
                )
                name = f"{original_sender.first_name} {original_sender.last_name}" if original_sender.last_name else original_sender.first_name
                await self.bot_manager.message_manager.send_message(
                    chat_id,
                    f"✅ **Контакт добавлен!**\n\n"
                    f"👤 {name}\n"
                    f"📱 @{original_sender.username if original_sender.username else 'нет username'}",
                    is_menu=True
                )
                await self.show_contacts_menu(chat_id)
            else:
                await self.bot_manager.message_manager.send_message(chat_id, "❌ Не удалось добавить контакт")
        except Exception as e:
            await self.bot_manager.message_manager.send_message(
                chat_id, f"❌ Ошибка добавления контакта: {str(e)}"
            )
            await self.show_contacts_menu(chat_id)
    
    async def show_contacts_menu(self, chat_id):
        """Показывает меню контактов"""
        from menus.contacts_menu import show_contacts_menu
        await show_contacts_menu(chat_id, self.bot_manager)

def register_message_handlers(client, bot_manager):
    handlers = MessageHandlers(client, bot_manager)
    client.on(events.NewMessage)(handlers.handle_message)
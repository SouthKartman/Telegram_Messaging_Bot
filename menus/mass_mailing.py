import asyncio
from database import db
from models.state_manager import state_manager
from utils.time_utils import get_repeat_description

class MassMailingManager:
    def __init__(self):
        self.selected_contacts = []
        self.current_template_id = None
        self.is_mailing_active = False

    async def show_mass_mailing_menu(self, chat_id, bot_manager):
        """Показывает меню массовой рассылки"""
        if not bot_manager.is_admin_chat(chat_id):
            return
            
        await bot_manager.message_manager.clear_chat_interface(chat_id, is_mailing=True)
        state_manager.set_state(str(chat_id), 'mass_mailing_menu')
        
        # Получаем информацию о выбранном шаблоне
        template_info = "❌ Не выбран"
        if self.current_template_id:
            templates = db.get_templates()
            selected_template = next((t for t in templates if t['id'] == self.current_template_id), None)
            if selected_template:
                template_info = f"✅ {selected_template['name']}"
        
        text = f"""
                    📨 **Массовая рассылка**

                    ✅ Выбрано контактов: {len(self.selected_contacts)}
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
        await bot_manager.message_manager.send_message(chat_id, text, is_mailing=True)

    async def show_contact_selection(self, chat_id, bot_manager):
        """Показывает контакты для выбора по номерам"""
        state_manager.set_state(str(chat_id), 'select_contacts_numbers')
        
        contacts = db.get_contacts()
        
        if not contacts:
            await bot_manager.message_manager.send_message(chat_id, "📝 Список контактов пуст", is_mailing=True)
            await self.show_mass_mailing_menu(chat_id, bot_manager)
            return
        
        text = "👥 **Выбор контактов для рассылки**\n\n"
        text += f"✅ Выбрано: {len(self.selected_contacts)} контактов\n\n"
        text += "**Список контактов:**\n\n"
        
        # Показываем все контакты с номерами
        for i, contact in enumerate(contacts, 1):
            name = f"{contact['first_name']} {contact['last_name']}" if contact['last_name'] else contact['first_name']
            status = "✅" if contact['user_id'] in self.selected_contacts else "⚪"
            
            contact_text = f"{status} {i}. {name}"
            if contact['username']:
                contact_text += f" (@{contact['username']})"
            
            text += f"{contact_text}\n"
        
        text += "\n💡 **Как выбрать:**"
        text += "\n• Введите номера контактов через пробел (например: 1 3 5)"
        text += "\n• Или диапазон (например: 1-5)"
        text += "\n• Или 'все' для выбора всех контактов"
        text += "\n• 'очистить' для сброса выбора"
        text += "\n• 'назад' для возврата в меню"
        text += f"\n\n📋 **Пример:** `1 3 5-7 10`"
        
        await bot_manager.message_manager.send_message(chat_id, text, is_mailing=True)

    async def show_template_selection_mass(self, chat_id, bot_manager):
        """Показывает шаблоны для выбора в массовой рассылке"""
        state_manager.set_state(str(chat_id), 'select_template_mass')
        
        templates = db.get_templates()
        
        if not templates:
            await bot_manager.message_manager.send_message(chat_id, "📝 Список шаблонов пуст", is_mailing=True)
            await self.show_mass_mailing_menu(chat_id, bot_manager)
            return
        
        text = "📋 **Выберите шаблон для рассылки:**\n\n"
        
        for i, template in enumerate(templates, 1):
            preview = template['text'][:50] + "..." if len(template['text']) > 50 else template['text']
            text += f"{i}. **{template['name']}:** {preview}\n\n"
        
        text += "\n💡 *Введите номер шаблона:*"
        
        await bot_manager.message_manager.send_message(chat_id, text, is_mailing=True)

    async def start_mass_mailing(self, chat_id, bot_manager):
        """Запускает массовую рассылку"""
        if not self.selected_contacts:
            await bot_manager.message_manager.send_message(chat_id, "❌ Не выбраны контакты для рассылки", is_mailing=True)
            return
        
        if not self.current_template_id:
            await bot_manager.message_manager.send_message(chat_id, "❌ Не выбран шаблон для рассылки", is_mailing=True)
            return
        
        templates = db.get_templates()
        template = next((t for t in templates if t['id'] == self.current_template_id), None)
        
        if not template:
            await bot_manager.message_manager.send_message(chat_id, "❌ Шаблон не найден", is_mailing=True)
            return
        
        # Подтверждение перед рассылкой
        text = f"""
                    ⚠️ **Подтверждение рассылки**

                    📝 Шаблон: **{template['name']}**
                    👥 Контактов: **{len(self.selected_contacts)}**
                    💬 Текст: {template['text'][:100]}...

                    ✅ Для начала отправьте "ДА"
                    ❌ Для отмены отправьте "НЕТ"
                """
        state_manager.set_state(str(chat_id), f'confirm_mailing_{template["id"]}')
        await bot_manager.message_manager.send_message(chat_id, text, is_mailing=True)

    async def execute_mass_mailing(self, chat_id, template, bot_manager):
        """Выполняет массовую рассылку"""
        self.is_mailing_active = True
        
        # Получаем контакты для рассылки
        contacts = db.get_contacts()
        contacts_to_send = [c for c in contacts if c['user_id'] in self.selected_contacts]
        
        await bot_manager.message_manager.send_message(chat_id, "🚀 Запускаю рассылку...", is_mailing=True)
        
        success_count = 0
        fail_count = 0
        results = []
        
        for i, contact in enumerate(contacts_to_send, 1):
            if not self.is_mailing_active:
                break
                
            try:
                await bot_manager.client.send_message(contact['user_id'], template['text'])
                success_count += 1
                results.append({
                    'success': True,
                    'contact_name': f"{contact['first_name']} {contact['last_name']}" if contact['last_name'] else contact['first_name'],
                    'message': '✅ Отправлено'
                })
                
                # Обновляем прогресс каждые 5 сообщений или на последнем
                if i % 5 == 0 or i == len(contacts_to_send):
                    progress_text = f"""
                                        📨 **Идет рассылка...**

                                        📊 Прогресс: {i}/{len(contacts_to_send)} ({i/len(contacts_to_send)*100:.1f}%)
                                        ✅ Успешно: {success_count}
                                        ❌ Ошибок: {fail_count}

                                        👤 Текущий: {contact['first_name']}
                                    """
                    await bot_manager.message_manager.send_message(chat_id, progress_text, save_message=False, is_mailing=True)
                
                await asyncio.sleep(2)  # Задержка между сообщениями
                
            except Exception as e:
                fail_count += 1
                results.append({
                    'success': False,
                    'contact_name': f"{contact['first_name']} {contact['last_name']}" if contact['last_name'] else contact['first_name'],
                    'message': f'❌ {str(e)}'
                })
                print(f"Ошибка отправки {contact['first_name']}: {e}")
        
        # Показываем финальные результаты
        await self.complete_mass_mailing(chat_id, results, bot_manager)
        self.is_mailing_active = False

    async def complete_mass_mailing(self, chat_id, results, bot_manager):
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
        await bot_manager.message_manager.send_message(chat_id, text, save_message=False, is_mailing=True)
        
        # Детализация
        if failed:
            details = "❌ **Контакты с ошибками:**\n\n"
            for fail in failed[:10]:
                details += f"• {fail['contact_name']}: {fail['message']}\n"
            
            if len(failed) > 10:
                details += f"\n... и еще {len(failed) - 10} ошибок"
            
            await bot_manager.message_manager.send_message(chat_id, details, save_message=False, is_mailing=True)
        
        # Очищаем выбранные контакты после рассылки
        self.selected_contacts.clear()

# Глобальный экземпляр менеджера массовой рассылки
mass_mailing_manager = MassMailingManager()

# Функции для импорта
async def show_mass_mailing_menu(chat_id, bot_manager):
    await mass_mailing_manager.show_mass_mailing_menu(chat_id, bot_manager)

async def show_contact_selection(chat_id, bot_manager):
    await mass_mailing_manager.show_contact_selection(chat_id, bot_manager)

async def show_template_selection_mass(chat_id, bot_manager):
    await mass_mailing_manager.show_template_selection_mass(chat_id, bot_manager)

async def start_mass_mailing(chat_id, bot_manager):
    await mass_mailing_manager.start_mass_mailing(chat_id, bot_manager)

async def handle_contact_numbers_selection(event, message_text, chat_id, bot_manager):
    """Обрабатывает выбор контактов по номерам"""
    from menus.main_menu import show_main_menu
    
    contacts = db.get_contacts()
    
    if message_text.lower() == 'назад':
        await mass_mailing_manager.show_mass_mailing_menu(chat_id, bot_manager)
        return
    
    elif message_text.lower() == 'все':
        # Выбираем все контакты
        mass_mailing_manager.selected_contacts.clear()
        mass_mailing_manager.selected_contacts.extend([c['user_id'] for c in contacts])
        await bot_manager.message_manager.send_message(
            chat_id, f"✅ Выбраны все контакты ({len(contacts)} шт.)", is_mailing=True
        )
        await mass_mailing_manager.show_mass_mailing_menu(chat_id, bot_manager)
        return
    
    elif message_text.lower() == 'очистить':
        # Очищаем выбор
        mass_mailing_manager.selected_contacts.clear()
        await bot_manager.message_manager.send_message(chat_id, "🗑️ Выбор контактов очищен", is_mailing=True)
        await mass_mailing_manager.show_mass_mailing_menu(chat_id, bot_manager)
        return
    
    # Обрабатываем ввод номеров
    try:
        selected_numbers = set()
        parts = message_text.split()
        
        for part in parts:
            if '-' in part:
                range_parts = part.split('-')
                if len(range_parts) == 2:
                    start = int(range_parts[0])
                    end = int(range_parts[1])
                    selected_numbers.update(range(start, end + 1))
            else:
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
            await bot_manager.message_manager.send_message(
                chat_id, "❌ Не указано ни одного правильного номера", is_mailing=True
            )
            await mass_mailing_manager.show_mass_mailing_menu(chat_id, bot_manager)
            return
        
        # Обновляем выбранные контакты
        mass_mailing_manager.selected_contacts.clear()
        for num in valid_numbers:
            contact = contacts[num - 1]
            mass_mailing_manager.selected_contacts.append(contact['user_id'])
        
        # Формируем сообщение с результатами
        result_text = f"✅ Выбрано контактов: {len(valid_numbers)}\n\n"
        
        # Показываем выбранные контакты
        for i, num in enumerate(sorted(valid_numbers)[:10], 1):
            contact = contacts[num - 1]
            name = f"{contact['first_name']} {contact['last_name']}" if contact['last_name'] else contact['first_name']
            result_text += f"{i}. {name}\n"
        
        if len(valid_numbers) > 10:
            result_text += f"... и еще {len(valid_numbers) - 10} контактов\n"
        
        if invalid_numbers:
            result_text += f"\n❌ Неверные номера: {', '.join(map(str, invalid_numbers))}"
        
        await bot_manager.message_manager.send_message(chat_id, result_text, is_mailing=True)
        await mass_mailing_manager.show_mass_mailing_menu(chat_id, bot_manager)
        
    except ValueError:
        await bot_manager.message_manager.send_message(
            chat_id, "❌ Ошибка формата. Используйте числа, пробелы и дефисы", is_mailing=True
        )
        await mass_mailing_manager.show_mass_mailing_menu(chat_id, bot_manager)
    except Exception as e:
        await bot_manager.message_manager.send_message(
            chat_id, f"❌ Ошибка: {str(e)}", is_mailing=True
        )
        await mass_mailing_manager.show_mass_mailing_menu(chat_id, bot_manager)

async def handle_template_selection_mass(event, message_text, chat_id, bot_manager):
    """Обрабатывает выбор шаблона для массовой рассылки по номеру"""
    from menus.main_menu import show_main_menu
    
    if message_text.lower() in ['/menu', 'назад']:
        await mass_mailing_manager.show_mass_mailing_menu(chat_id, bot_manager)
        return
    
    templates = db.get_templates()
    
    if message_text.isdigit():
        template_index = int(message_text) - 1
        if 0 <= template_index < len(templates):
            template = templates[template_index]
            mass_mailing_manager.current_template_id = template['id']
            
            await bot_manager.message_manager.send_message(
                chat_id,
                f"✅ **Шаблон выбран!**\n\n"
                f"📝 **Название:** {template['name']}\n"
                f"💬 **Текст:** {template['text']}",
                is_mailing=True
            )
            await mass_mailing_manager.show_mass_mailing_menu(chat_id, bot_manager)
        else:
            await bot_manager.message_manager.send_message(
                chat_id, "❌ Неверный номер шаблона", is_mailing=True
            )
            await mass_mailing_manager.show_template_selection_mass(chat_id, bot_manager)
    else:
        await bot_manager.message_manager.send_message(
            chat_id, "❌ Пожалуйста, введите номер шаблона", is_mailing=True
        )
        await mass_mailing_manager.show_template_selection_mass(chat_id, bot_manager)

async def handle_mailing_confirmation(event, message_text, chat_id, current_state, bot_manager):
    """Обрабатывает подтверждение рассылки"""
    from menus.main_menu import show_main_menu
    
    if message_text.upper() == 'ДА':
        template_id = int(current_state.replace('confirm_mailing_', ''))
        templates = db.get_templates()
        template = next((t for t in templates if t['id'] == template_id), None)
        
        if template:
            await mass_mailing_manager.execute_mass_mailing(chat_id, template, bot_manager)
            await show_main_menu(chat_id, bot_manager)
        
    elif message_text.upper() == 'НЕТ':
        await bot_manager.message_manager.send_message(chat_id, "❌ Рассылка отменена", is_mailing=True)
        await mass_mailing_manager.show_mass_mailing_menu(chat_id, bot_manager)
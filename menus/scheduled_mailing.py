
import asyncio
from datetime import datetime
from database import db
from models.state_manager import state_manager
from utils.time_utils import parse_time_input, calculate_next_send_time, get_repeat_description
from menus.mass_mailing import mass_mailing_manager

class ScheduledMailingManager:
    def __init__(self):
        self.scheduled_mailings = []
        self.is_checking_active = False

    async def show_scheduled_mailing_menu(self, chat_id, bot_manager):
        """Показывает меню отложенной рассылки"""
        if not bot_manager.is_admin_chat(chat_id):
            return
            
        await bot_manager.message_manager.clear_chat_interface(chat_id)
        state_manager.set_state(str(chat_id), 'scheduled_mailing_menu')
        
        scheduled_mailings = db.get_scheduled_mailings()
        
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
        await bot_manager.message_manager.send_message(chat_id, text)

    async def start_scheduled_mailing_creation(self, chat_id, bot_manager):
        """Начинает процесс создания отложенной рассылки"""
        if not mass_mailing_manager.selected_contacts:
            await bot_manager.message_manager.send_message(
                chat_id, "❌ Сначала выберите контакты для рассылки"
            )
            from menus.mass_mailing import show_mass_mailing_menu
            await show_mass_mailing_menu(chat_id, bot_manager)
            return
        
        if not mass_mailing_manager.current_template_id:
            await bot_manager.message_manager.send_message(
                chat_id, "❌ Сначала выберите шаблон для рассылки"
            )
            from menus.mass_mailing import show_mass_mailing_menu
            await show_mass_mailing_menu(chat_id, bot_manager)
            return
        
        state_manager.set_state(str(chat_id), 'scheduled_waiting_name')
        await bot_manager.message_manager.send_message(
            chat_id,
            "⏰ **Создание отложенной рассылки**\n\n"
            "Введите название для этой рассылки:\n\n"
            "💡 *Пример: 'Новогодняя рассылка' или 'Напоминание о встрече'*"
        )

    async def handle_scheduled_name_input(self, event, message_text, chat_id, bot_manager):
        """Обрабатывает ввод названия отложенной рассылки"""
        from menus.main_menu import show_main_menu
        
        if message_text.lower() in ['/menu', 'назад']:
            await self.show_scheduled_mailing_menu(chat_id, bot_manager)
            return
        
        state_manager.set_state(str(chat_id), 'scheduled_waiting_time')
        state_manager.set_data(str(chat_id), 'scheduled_name', message_text)
        
        await bot_manager.message_manager.send_message(
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

    async def handle_scheduled_time_input(self, event, message_text, chat_id, bot_manager):
        """Обрабатывает ввод времени отправки"""
        from menus.main_menu import show_main_menu
        
        if message_text.lower() in ['/menu', 'назад']:
            await self.show_scheduled_mailing_menu(chat_id, bot_manager)
            return
        
        try:
            send_time = parse_time_input(message_text)
            if not send_time:
                await bot_manager.message_manager.send_message(
                    chat_id, "❌ Неверный формат времени. Попробуйте снова:"
                )
                return
            
            state_manager.set_state(str(chat_id), 'scheduled_waiting_repeat')
            state_manager.set_data(str(chat_id), 'scheduled_time', send_time)
            
            await bot_manager.message_manager.send_message(
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
            await bot_manager.message_manager.send_message(
                chat_id, f"❌ Ошибка: {str(e)}\nПопробуйте снова:"
            )

    async def handle_scheduled_repeat_input(self, event, message_text, chat_id, bot_manager):
        """Обрабатывает ввод настроек повтора"""
        from menus.main_menu import show_main_menu
        
        if message_text.lower() in ['/menu', 'назад']:
            await self.show_scheduled_mailing_menu(chat_id, bot_manager)
            return
        
        repeat_options = {
            '1': ('once', 1, 0),
            '2': ('daily', 0, 1440),
            '3': ('weekly', 0, 10080),
            '4': ('monthly', 0, 43200),
        }
        
        if message_text in repeat_options:
            repeat_type, repeat_count, repeat_interval = repeat_options[message_text]
            await self.save_scheduled_mailing(
                chat_id, repeat_type, repeat_count, repeat_interval, bot_manager
            )
        elif message_text == '5':
            await bot_manager.message_manager.send_message(
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
            state_manager.set_data(str(chat_id), 'waiting_interval', True)
        else:
            # Парсим интервал вручную
            try:
                parts = message_text.split()
                if len(parts) == 2:
                    repeat_interval = int(parts[0])
                    repeat_count = int(parts[1])
                    repeat_type = 'interval'
                    await self.save_scheduled_mailing(
                        chat_id, repeat_type, repeat_count, repeat_interval, bot_manager
                    )
                else:
                    await bot_manager.message_manager.send_message(
                        chat_id, "❌ Неверный формат. Попробуйте снова:"
                    )
            except:
                await bot_manager.message_manager.send_message(
                    chat_id, "❌ Неверный формат. Введите номер от 1 до 5:"
                )

    async def save_scheduled_mailing(self, chat_id, repeat_type, repeat_count, repeat_interval, bot_manager):
        """Сохраняет отложенную рассылку в БД"""
        name = state_manager.get_data(str(chat_id), 'scheduled_name')
        send_time = state_manager.get_data(str(chat_id), 'scheduled_time')
        
        mailing_id = db.save_scheduled_mailing(
            name=name,
            template_id=mass_mailing_manager.current_template_id,
            contacts=mass_mailing_manager.selected_contacts,
            send_time=send_time.strftime("%Y-%m-%d %H:%M:%S"),
            repeat_type=repeat_type,
            repeat_count=repeat_count,
            repeat_interval=repeat_interval
        )
        
        # Очищаем временные данные
        for key in ['scheduled_name', 'scheduled_time', 'waiting_interval']:
            state_manager.clear_data(str(chat_id), key)
        
        templates = db.get_templates()
        template = next((t for t in templates if t['id'] == mass_mailing_manager.current_template_id), None)
        template_name = template['name'] if template else "Неизвестный шаблон"
        
        await bot_manager.message_manager.send_message(
            chat_id,
            f"✅ **Отложенная рассылка создана!**\n\n"
            f"📝 Название: {name}\n"
            f"🕐 Время: {send_time.strftime('%Y-%m-%d %H:%M')}\n"
            f"📋 Шаблон: {template_name}\n"
            f"👥 Контактов: {len(mass_mailing_manager.selected_contacts)}\n"
            f"🔄 Повтор: {get_repeat_description(repeat_type, repeat_count, repeat_interval)}\n"
            f"📊 ID: {mailing_id}"
        )
        
        await self.show_scheduled_mailing_menu(chat_id, bot_manager)

    async def show_scheduled_mailings_list(self, chat_id, bot_manager):
        """Показывает список запланированных рассылок"""
        mailings = db.get_scheduled_mailings()
        
        if not mailings:
            await bot_manager.message_manager.send_message(chat_id, "📭 Нет запланированных рассылок")
            await self.show_scheduled_mailing_menu(chat_id, bot_manager)
            return
        
        text = "📅 **Запланированные рассылки:**\n\n"
        
        for mailing in mailings:
            contacts_count = len(mailing['contacts'].split(',')) if mailing['contacts'] else 0
            
            templates = db.get_templates()
            template = next((t for t in templates if t['id'] == mailing['template_id']), None)
            template_name = template['name'] if template else "Неизвестный шаблон"
            
            text += f"📊 **{mailing['name']}** (ID: {mailing['id']})\n"
            text += f"🕐 {mailing['send_time']}\n"
            text += f"📝 {template_name}\n"
            text += f"👥 {contacts_count} контактов\n"
            text += f"🔄 {get_repeat_description(mailing['repeat_type'], mailing['repeat_count'], mailing['repeat_interval'])}\n"
            text += f"📊 Статус: {mailing['status']}\n\n"
        
        await bot_manager.message_manager.send_message(chat_id, text)
        await self.show_scheduled_mailing_menu(chat_id, bot_manager)

    async def show_scheduled_mailings_for_deletion(self, chat_id, bot_manager):
        """Показывает рассылки для удаления"""
        mailings = db.get_scheduled_mailings()
        
        if not mailings:
            await bot_manager.message_manager.send_message(
                chat_id, "📭 Нет запланированных рассылок для удаления"
            )
            await self.show_scheduled_mailing_menu(chat_id, bot_manager)
            return
        
        text = "🗑️ **Выберите рассылку для удаления:**\n\n"
        
        for i, mailing in enumerate(mailings, 1):
            text += f"{i}. **{mailing['name']}** (ID: {mailing['id']})\n"
            text += f"   🕐 {mailing['send_time']}\n\n"
        
        text += "💡 *Введите номер рассылки для удаления:*"
        
        state_manager.set_state(str(chat_id), 'scheduled_waiting_delete')
        state_manager.set_data(str(chat_id), 'scheduled_mailings', mailings)
        await bot_manager.message_manager.send_message(chat_id, text)

    async def handle_scheduled_delete_input(self, event, message_text, chat_id, bot_manager):
        """Обрабатывает удаление отложенной рассылки"""
        from menus.main_menu import show_main_menu
        
        if message_text.lower() in ['/menu', 'назад']:
            await self.show_scheduled_mailing_menu(chat_id, bot_manager)
            return
        
        if not message_text.isdigit():
            await bot_manager.message_manager.send_message(
                chat_id, "❌ Пожалуйста, введите номер рассылки:"
            )
            return
        
        index = int(message_text) - 1
        mailings = state_manager.get_data(str(chat_id), 'scheduled_mailings', [])
        
        if 0 <= index < len(mailings):
            mailing = mailings[index]
            mailing_id = mailing['id']
            mailing_name = mailing['name']
            
            db.update_mailing_status(mailing_id, 'cancelled')
            
            await bot_manager.message_manager.send_message(
                chat_id,
                f"🗑️ **Рассылка удалена!**\n\n"
                f"📝 Название: {mailing_name}\n"
                f"📊 ID: {mailing_id}"
            )
            
            # Очищаем временные данные
            state_manager.clear_data(str(chat_id), 'scheduled_mailings')
            
            await self.show_scheduled_mailing_menu(chat_id, bot_manager)
        else:
            await bot_manager.message_manager.send_message(
                chat_id, "❌ Неверный номер рассылки. Попробуйте снова:"
            )

    async def check_scheduled_mailings(self, bot_manager):
        """Фоновая задача для проверки и выполнения отложенных рассылок"""
        print("🕐 Запущена фоновая задача проверки отложенных рассылок")
        self.is_checking_active = True
        
        while self.is_checking_active:
            try:
                if bot_manager.bot_active:
                    mailings = db.get_scheduled_mailings()
                    current_time = datetime.now()
                    
                    print(f"🔍 Проверяем {len(mailings)} отложенных рассылок...")
                    
                    for mailing in mailings:
                        try:
                            send_time_dt = datetime.strptime(mailing['send_time'], "%Y-%m-%d %H:%M:%S")
                            
                            print(f"📊 Рассылка '{mailing['name']}': запланирована на {send_time_dt}, текущее время: {current_time}")
                            
                            # Проверяем, настало ли время отправки
                            if current_time >= send_time_dt:
                                print(f"🚀 Время отправки настало! Запускаем рассылку '{mailing['name']}'")
                                await self.execute_scheduled_mailing(mailing, bot_manager)
                            else:
                                time_diff = send_time_dt - current_time
                                print(f"⏳ До отправки '{mailing['name']}': {time_diff}")
                                
                        except Exception as e:
                            print(f"❌ Ошибка при проверке рассылки {mailing['name']}: {e}")
                
                # Ждем 30 секунд перед следующей проверкой
                await asyncio.sleep(30)
                
            except Exception as e:
                print(f"❌ Критическая ошибка в check_scheduled_mailings: {e}")
                await asyncio.sleep(60)

    async def execute_scheduled_mailing(self, mailing, bot_manager):
        """Выполняет отложенную рассылку"""
        print(f"🎯 Начинаем выполнение отложенной рассылки: {mailing['name']}")
        
        try:
            # Получаем данные для рассылки
            templates = db.get_templates()
            template = next((t for t in templates if t['id'] == mailing['template_id']), None)
            
            if not template:
                print(f"❌ Шаблон не найден для рассылки {mailing['name']}")
                db.update_mailing_status(mailing['id'], 'failed')
                return
            
            contacts = db.get_contacts()
            contact_ids = [int(cid) for cid in mailing['contacts'].split(',')] if mailing['contacts'] else []
            contacts_to_send = [c for c in contacts if c['user_id'] in contact_ids]
            
            if not contacts_to_send:
                print(f"❌ Нет контактов для рассылки {mailing['name']}")
                db.update_mailing_status(mailing['id'], 'failed')
                return
            
            print(f"📨 Начинаем рассылку '{mailing['name']}' для {len(contacts_to_send)} контактов")
            
            # Выполняем рассылку
            success_count = 0
            fail_count = 0
            
            for i, contact in enumerate(contacts_to_send, 1):
                try:
                    await bot_manager.client.send_message(contact['user_id'], template['text'])
                    success_count += 1
                    print(f"✅ Отправлено сообщение {i}/{len(contacts_to_send)} для {contact['first_name']}")
                    
                    # Задержка между сообщениями
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    fail_count += 1
                    print(f"❌ Ошибка отправки для {contact['first_name']}: {e}")
            
            print(f"📊 Рассылка '{mailing['name']}' завершена: {success_count} успешно, {fail_count} с ошибками")
            
            # Обрабатываем повтор рассылки
            if mailing['repeat_type'] != 'once' and (mailing['repeat_count'] > 1 or mailing['repeat_count'] == 0):
                # Вычисляем следующее время отправки
                current_send_time = datetime.strptime(mailing['send_time'], "%Y-%m-%d %H:%M:%S")
                next_send_time = calculate_next_send_time(
                    current_send_time, mailing['repeat_type'], mailing['repeat_interval']
                )
                
                # Уменьшаем счетчик повторов (если не бесконечно)
                new_repeat_count = mailing['repeat_count'] - 1 if mailing['repeat_count'] > 0 else 0
                
                # Обновляем время и счетчик в БД
                db.update_mailing_time_and_count(
                    mailing['id'], 
                    next_send_time.strftime("%Y-%m-%d %H:%M:%S"), 
                    new_repeat_count
                )
                
                print(f"🔄 Запланирован повтор рассылки '{mailing['name']}' на {next_send_time}")
                
            else:
                # Завершаем рассылку
                db.update_mailing_status(mailing['id'], 'completed')
                print(f"✅ Рассылка '{mailing['name']}' завершена окончательно")
            
            # Отправляем уведомление в админ-чат
            notification_text = f"""
✅ **Отложенная рассылка выполнена**

📝 Название: {mailing['name']}
🕐 Время: {datetime.now().strftime('%Y-%m-%d %H:%M')}
✅ Успешно: {success_count}/{len(contacts_to_send)}
❌ Ошибок: {fail_count}
"""
            
            if mailing['repeat_type'] != 'once' and (mailing['repeat_count'] > 1 or mailing['repeat_count'] == 0):
                next_time = calculate_next_send_time(
                    datetime.strptime(mailing['send_time'], '%Y-%m-%d %H:%M:%S'), 
                    mailing['repeat_type'], 
                    mailing['repeat_interval']
                )
                notification_text += f"🔄 Следующая отправка: {next_time.strftime('%Y-%m-%d %H:%M')}"
            
            await bot_manager.message_manager.send_message(
                bot_manager.config.bot.admin_chat_id,
                notification_text,
                save_message=False
            )
            
        except Exception as e:
            print(f"❌ Критическая ошибка выполнения рассылки {mailing['name']}: {e}")
            db.update_mailing_status(mailing['id'], 'failed')
            
            # Отправляем уведомление об ошибке
            await bot_manager.message_manager.send_message(
                bot_manager.config.bot.admin_chat_id,
                f"❌ **Ошибка отложенной рассылки**\n\n"
                f"📝 Название: {mailing['name']}\n"
                f"🕐 Время: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"💬 Ошибка: {str(e)}",
                save_message=False
            )

# Глобальный экземпляр менеджера отложенной рассылки
scheduled_mailing_manager = ScheduledMailingManager()

# Функции для импорта
async def show_scheduled_mailing_menu(chat_id, bot_manager):
    await scheduled_mailing_manager.show_scheduled_mailing_menu(chat_id, bot_manager)

async def start_scheduled_mailing_creation(chat_id, bot_manager):
    await scheduled_mailing_manager.start_scheduled_mailing_creation(chat_id, bot_manager)

async def show_scheduled_mailings_list(chat_id, bot_manager):
    await scheduled_mailing_manager.show_scheduled_mailings_list(chat_id, bot_manager)

async def show_scheduled_mailings_for_deletion(chat_id, bot_manager):
    await scheduled_mailing_manager.show_scheduled_mailings_for_deletion(chat_id, bot_manager)

async def handle_scheduled_name_input(event, message_text, chat_id, bot_manager):
    await scheduled_mailing_manager.handle_scheduled_name_input(event, message_text, chat_id, bot_manager)

async def handle_scheduled_time_input(event, message_text, chat_id, bot_manager):
    await scheduled_mailing_manager.handle_scheduled_time_input(event, message_text, chat_id, bot_manager)

async def handle_scheduled_repeat_input(event, message_text, chat_id, bot_manager):
    await scheduled_mailing_manager.handle_scheduled_repeat_input(event, message_text, chat_id, bot_manager)

async def handle_scheduled_delete_input(event, message_text, chat_id, bot_manager):
    await scheduled_mailing_manager.handle_scheduled_delete_input(event, message_text, chat_id, bot_manager)

async def check_scheduled_mailings(bot_manager):
    await scheduled_mailing_manager.check_scheduled_mailings(bot_manager)
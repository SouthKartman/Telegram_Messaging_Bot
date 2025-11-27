import asyncio
import sqlite3
from telethon import TelegramClient
from telethon.tl.types import User
import time
from typing import List, Tuple

class MassMailing:
    def __init__(self, client: TelegramClient):
        self.client = client
        self.is_sending = False
        self.current_progress = 0
        self.total_recipients = 0
        
    def get_contacts(self):
        """Получаем список контактов из БД"""
        conn = sqlite3.connect('telegram_assistant.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, user_id, username, first_name, last_name 
            FROM contacts 
            ORDER BY first_name
        ''')
        contacts = cursor.fetchall()
        conn.close()
        return contacts
    
    def get_templates(self):
        """Получаем список шаблонов из БД"""
        conn = sqlite3.connect('telegram_assistant.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, text FROM templates ORDER BY name')
        templates = cursor.fetchall()
        conn.close()
        return templates
    
    async def send_to_contact(self, contact: Tuple, template_text: str, delay: float = 1.0) -> dict:
        """
        Отправляет сообщение одному контакту
        Возвращает dict с результатом
        """
        try:
            id_, user_id, username, first_name, last_name = contact
            name = f"{first_name} {last_name}" if last_name else first_name
            
            await self.client.send_message(user_id, template_text)
            
            # Задержка между сообщениями чтобы не спамить
            await asyncio.sleep(delay)
            
            return {
                'success': True,
                'contact_id': user_id,
                'contact_name': name,
                'username': username,
                'message': '✅ Отправлено'
            }
            
        except Exception as e:
            error_msg = str(e)
            if "Forbidden" in error_msg:
                error_msg = "❌ Пользователь заблокировал бота"
            elif "Timeout" in error_msg:
                error_msg = "⏰ Таймаут соединения"
            elif "Flood" in error_msg:
                error_msg = "🌊 Flood protection"
            else:
                error_msg = f"❌ Ошибка: {error_msg}"
                
            return {
                'success': False,
                'contact_id': contact[1],
                'contact_name': name,
                'username': username,
                'message': error_msg
            }
    
    async def mass_send(
        self, 
        contact_ids: List[int], 
        template_text: str, 
        progress_callback=None,
        delay: float = 1.5
    ) -> List[dict]:
        """
        Основная функция массовой рассылки
        
        Args:
            contact_ids: список ID контактов для рассылки
            template_text: текст шаблона
            progress_callback: функция для обновления прогресса
            delay: задержка между сообщениями в секундах
        
        Returns:
            Список результатов отправки
        """
        self.is_sending = True
        self.current_progress = 0
        self.total_recipients = len(contact_ids)
        
        contacts = self.get_contacts()
        selected_contacts = [c for c in contacts if c[1] in contact_ids]
        
        results = []
        
        for i, contact in enumerate(selected_contacts):
            if not self.is_sending:
                break
                
            result = await self.send_to_contact(contact, template_text, delay)
            results.append(result)
            
            self.current_progress = i + 1
            
            # Вызываем callback для обновления прогресса
            if progress_callback:
                await progress_callback(
                    current=self.current_progress,
                    total=self.total_recipients,
                    result=result
                )
            
            # Небольшая пауза каждые 10 сообщений
            if (i + 1) % 10 == 0:
                await asyncio.sleep(2)
        
        self.is_sending = False
        return results
    
    def stop_sending(self):
        """Останавливает рассылку"""
        self.is_sending = False
    
    def get_progress(self) -> dict:
        """Возвращает текущий прогресс"""
        if self.total_recipients == 0:
            return {'percent': 0, 'current': 0, 'total': 0}
        
        percent = (self.current_progress / self.total_recipients) * 100
        return {
            'percent': round(percent, 1),
            'current': self.current_progress,
            'total': self.total_recipients
        }
    
    def create_contact_groups(self, group_size: int = 5) -> List[List[Tuple]]:
        """
        Создает группы контактов для выбора
        """
        contacts = self.get_contacts()
        groups = []
        
        for i in range(0, len(contacts), group_size):
            groups.append(contacts[i:i + group_size])
            
        return groups
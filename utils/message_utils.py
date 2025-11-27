import asyncio
from typing import List, Optional, Dict
from telethon import TelegramClient
from telethon.tl.types import Message
from config import config

class MessageManager:
    def __init__(self, client: TelegramClient):
        self.client = client
        self.last_messages: Dict[str, List[int]] = {}  # {chat_id: [message_ids]}
        self.mailing_messages: Dict[str, List[int]] = {}  # {chat_id: [message_ids]}
        self.menu_messages: Dict[str, int] = {}  # {chat_id: last_menu_message_id}
        self.user_messages: Dict[str, List[int]] = {}  # {chat_id: [user_message_ids]}
    
    async def send_message(self, chat_id: str, text: str, save_message: bool = True, 
                         is_mailing: bool = False, is_menu: bool = False) -> Optional[Message]:
        """Отправляет сообщение и сохраняет его ID для последующего удаления"""
        message = await self.client.send_message(chat_id, text)
        
        if save_message:
            chat_id_str = str(chat_id)
            
            if is_menu:
                # Удаляем предыдущее меню
                if chat_id_str in self.menu_messages:
                    try:
                        await self.client.delete_messages(chat_id, self.menu_messages[chat_id_str])
                    except:
                        pass
                self.menu_messages[chat_id_str] = message.id
                
            elif is_mailing:
                if chat_id_str not in self.mailing_messages:
                    self.mailing_messages[chat_id_str] = []
                self.mailing_messages[chat_id_str].append(message.id)
            else:
                if chat_id_str not in self.last_messages:
                    self.last_messages[chat_id_str] = []
                self.last_messages[chat_id_str].append(message.id)
        
        return message
    
    async def save_user_message(self, chat_id: str, message_id: int):
        """Сохраняет ID сообщения пользователя для последующего удаления"""
        chat_id_str = str(chat_id)
        if chat_id_str not in self.user_messages:
            self.user_messages[chat_id_str] = []
        self.user_messages[chat_id_str].append(message_id)
    
    async def delete_last_messages(self, chat_id: str, keep_last: int = 0, is_mailing: bool = False):
        """Удаляет последние сообщения бота"""
        chat_id_str = str(chat_id)
        messages_dict = self.mailing_messages if is_mailing else self.last_messages
        
        if chat_id_str not in messages_dict or not messages_dict[chat_id_str]:
            return
        
        messages_list = messages_dict[chat_id_str]
        
        # Оставляем указанное количество последних сообщений
        if keep_last > 0 and len(messages_list) > keep_last:
            messages_to_delete = messages_list[:-keep_last]
            messages_dict[chat_id_str] = messages_list[-keep_last:]
        else:
            messages_to_delete = messages_list.copy()
            messages_dict[chat_id_str] = []
        
        for msg_id in messages_to_delete:
            try:
                await self.client.delete_messages(chat_id, msg_id)
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"Не удалось удалить сообщение бота {msg_id}: {e}")
    
    async def delete_user_messages(self, chat_id: str, keep_last: int = 1):
        """Удаляет сообщения пользователя"""
        chat_id_str = str(chat_id)
        
        if chat_id_str not in self.user_messages or not self.user_messages[chat_id_str]:
            return
        
        messages_list = self.user_messages[chat_id_str]
        
        # Оставляем указанное количество последних сообщений
        if keep_last > 0 and len(messages_list) > keep_last:
            messages_to_delete = messages_list[:-keep_last]
            self.user_messages[chat_id_str] = messages_list[-keep_last:]
        else:
            messages_to_delete = messages_list.copy()
            self.user_messages[chat_id_str] = []
        
        for msg_id in messages_to_delete:
            try:
                await self.client.delete_messages(chat_id, msg_id)
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"Не удалось удалить сообщение пользователя {msg_id}: {e}")
    
    async def clear_chat_interface(self, chat_id: str, is_mailing: bool = False):
        """Очищает интерфейс бота в чате - сообщения бота и пользователя"""
        chat_id_str = str(chat_id)
        
        # Удаляем старые сообщения бота (оставляем последние 2)
        await self.delete_last_messages(chat_id, keep_last=2, is_mailing=is_mailing)
        
        # Удаляем сообщения пользователя (оставляем только последнее)
        await self.delete_user_messages(chat_id, keep_last=1)
    
    async def clear_all_messages(self, chat_id: str):
        """Очищает ВСЕ сообщения бота и пользователя в чате"""
        chat_id_str = str(chat_id)
        
        # Удаляем обычные сообщения бота
        if chat_id_str in self.last_messages:
            for msg_id in self.last_messages[chat_id_str]:
                try:
                    await self.client.delete_messages(chat_id, msg_id)
                    await asyncio.sleep(0.1)
                except:
                    pass
            self.last_messages[chat_id_str] = []
        
        # Удаляем сообщения рассылки бота
        if chat_id_str in self.mailing_messages:
            for msg_id in self.mailing_messages[chat_id_str]:
                try:
                    await self.client.delete_messages(chat_id, msg_id)
                    await asyncio.sleep(0.1)
                except:
                    pass
            self.mailing_messages[chat_id_str] = []
        
        # Удаляем меню бота
        if chat_id_str in self.menu_messages:
            try:
                await self.client.delete_messages(chat_id, self.menu_messages[chat_id_str])
            except:
                pass
            self.menu_messages.pop(chat_id_str, None)
        
        # Удаляем сообщения пользователя
        if chat_id_str in self.user_messages:
            for msg_id in self.user_messages[chat_id_str]:
                try:
                    await self.client.delete_messages(chat_id, msg_id)
                    await asyncio.sleep(0.1)
                except:
                    pass
            self.user_messages[chat_id_str] = []

def is_admin_chat(chat_id: str, client_self_id: int) -> bool:
    """Проверяет, является ли чат админским"""
    return chat_id == config.bot.admin_chat_id or (isinstance(chat_id, int) and chat_id == client_self_id)
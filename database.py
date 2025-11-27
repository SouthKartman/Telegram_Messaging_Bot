import sqlite3
from contextlib import contextmanager
from typing import List, Tuple, Optional
from config import config

class DatabaseManager:
    def __init__(self):
        self.db_path = config.database.url.replace('sqlite:///', '')
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица контактов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    phone TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица шаблонов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица отложенных рассылок
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scheduled_mailings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    template_id INTEGER,
                    contacts TEXT,
                    send_time DATETIME,
                    repeat_type TEXT,
                    repeat_count INTEGER,
                    repeat_interval INTEGER,
                    status TEXT DEFAULT 'scheduled',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Стандартные шаблоны
            default_templates = [
                ('later', 'Отвечу позже! Сейчас занят, но обязательно напишу.'),
                ('busy', 'В данный момент занят, отвечу при первой возможности.'),
                ('thanks', 'Спасибо за сообщение! Изучил и скоро отвечу.'),
                ('quick', '⚡ Быстрый ответ: понял вас, подробнее отвечу позже!'),
                ('meeting', 'На совещании, напишу позже.'),
            ]
            
            for name, text in default_templates:
                cursor.execute('''
                    INSERT OR IGNORE INTO templates (name, text) 
                    VALUES (?, ?)
                ''', (name, text))
    
    def get_templates(self) -> List[sqlite3.Row]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, name, text FROM templates ORDER BY name')
            return cursor.fetchall()
    
    def save_template(self, name: str, text: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO templates (name, text)
                VALUES (?, ?)
            ''', (name, text))
    
    def get_contacts(self) -> List[sqlite3.Row]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, user_id, username, first_name, last_name, phone 
                FROM contacts 
                ORDER BY first_name
            ''')
            return cursor.fetchall()
    
    def save_contact(self, user_id: int, username: str, first_name: str, last_name: str, phone: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO contacts (user_id, username, first_name, last_name, phone)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name, phone))
    
    def save_scheduled_mailing(self, name: str, template_id: int, contacts: List[int], 
                             send_time: str, repeat_type: str, repeat_count: int, repeat_interval: int) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO scheduled_mailings 
                (name, template_id, contacts, send_time, repeat_type, repeat_count, repeat_interval)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, template_id, ','.join(map(str, contacts)), send_time, repeat_type, repeat_count, repeat_interval))
            return cursor.lastrowid
    
    def get_scheduled_mailings(self) -> List[sqlite3.Row]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, template_id, contacts, send_time, repeat_type, repeat_count, repeat_interval, status
                FROM scheduled_mailings 
                WHERE status = 'scheduled'
                ORDER BY send_time
            ''')
            return cursor.fetchall()
    
    def update_mailing_status(self, mailing_id: int, status: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE scheduled_mailings 
                SET status = ? 
                WHERE id = ?
            ''', (status, mailing_id))
    
    def update_mailing_time_and_count(self, mailing_id: int, new_send_time: str, new_repeat_count: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE scheduled_mailings 
                SET send_time = ?, repeat_count = ?
                WHERE id = ?
            ''', (new_send_time, new_repeat_count, mailing_id))

# Глобальный экземпляр менеджера БД
db = DatabaseManager()
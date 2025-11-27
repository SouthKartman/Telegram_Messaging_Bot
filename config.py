import os
from dataclasses import dataclass
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

@dataclass
class DatabaseConfig:
    url: str = os.getenv("DATABASE_URL", "sqlite:///telegram_assistant.db")
    
@dataclass
class BotConfig:
    token: str = os.getenv("API_HASH", "")  # Telethon использует API_HASH как токен
    api_id: int = int(os.getenv("API_ID", 0))
    session_name: str = os.getenv("SESSION_NAME", "WaitAssistent")
    admin_chat_id: str = os.getenv("ADMIN_CHAT_ID", "me")
    
@dataclass
class MailingConfig:
    delay_between_messages: int = 2
    check_interval: int = 30
    max_contacts_per_mailing: int = 1000

@dataclass
class Config:
    bot: BotConfig
    database: DatabaseConfig
    mailing: MailingConfig
    
    @classmethod
    def load(cls):
        return cls(
            bot=BotConfig(),
            database=DatabaseConfig(),
            mailing=MailingConfig()
        )

config = Config.load()
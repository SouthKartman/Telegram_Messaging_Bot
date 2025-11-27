from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class Contact(Base):
    __tablename__ = "contacts"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone = Column(String(20))
    created_at = Column(DateTime, default=func.now())
    
    def display_name(self):
        name = self.first_name or ""
        if self.last_name:
            name += f" {self.last_name}"
        return name.strip()

class Template(Base):
    __tablename__ = "templates"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True)
    text = Column(Text)
    created_at = Column(DateTime, default=func.now())

class ScheduledMailing(Base):
    __tablename__ = "scheduled_mailings"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    template_id = Column(Integer)
    contacts = Column(Text)  # JSON string of contact IDs
    send_time = Column(DateTime)
    repeat_type = Column(String(20))  # once, daily, weekly, monthly, interval
    repeat_count = Column(Integer, default=1)
    repeat_interval = Column(Integer)  # in minutes
    status = Column(String(20), default='scheduled')  # scheduled, completed, cancelled, failed
    created_at = Column(DateTime, default=func.now())
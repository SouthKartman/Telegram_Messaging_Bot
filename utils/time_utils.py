import re
from datetime import datetime, timedelta
from typing import Optional

def parse_time_input(time_str: str) -> Optional[datetime]:
    """Парсит ввод времени в различных форматах"""
    time_str = time_str.strip().lower()
    current_time = datetime.now()
    
    try:
        # Формат: ГГГГ-ММ-ДД ЧЧ:ММ
        if re.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}', time_str):
            return datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        
        # Формат: +Nh (часы)
        elif re.match(r'^\+\d+h$', time_str):
            hours = int(time_str[1:-1])
            return current_time + timedelta(hours=hours)
        
        # Формат: +Nm (минуты)
        elif re.match(r'^\+\d+m$', time_str):
            minutes = int(time_str[1:-1])
            return current_time + timedelta(minutes=minutes)
        
        # Формат: +Nd (дни)
        elif re.match(r'^\+\d+d$', time_str):
            days = int(time_str[1:-1])
            return current_time + timedelta(days=days)
        
        # Формат: tomorrow HH:MM
        elif time_str.startswith('tomorrow'):
            try:
                time_part = time_str.split()[1]
                hours, minutes = map(int, time_part.split(':'))
                tomorrow = current_time + timedelta(days=1)
                return tomorrow.replace(hour=hours, minute=minutes, second=0, microsecond=0)
            except:
                return None
        
        # Формат: today HH:MM
        elif time_str.startswith('today'):
            try:
                time_part = time_str.split()[1]
                hours, minutes = map(int, time_part.split(':'))
                result = current_time.replace(hour=hours, minute=minutes, second=0, microsecond=0)
                if result < current_time:
                    result += timedelta(days=1)
                return result
            except:
                return None
        
        # Формат: now (немедленно, для тестирования)
        elif time_str in ['now', 'тест']:
            return current_time + timedelta(seconds=10)
        
        return None
        
    except Exception as e:
        print(f"Ошибка парсинга времени '{time_str}': {e}")
        return None

def calculate_next_send_time(current_send_time: datetime, repeat_type: str, repeat_interval: int) -> datetime:
    """Вычисляет следующее время отправки"""
    if repeat_type == 'daily':
        return current_send_time + timedelta(days=1)
    elif repeat_type == 'weekly':
        return current_send_time + timedelta(weeks=1)
    elif repeat_type == 'monthly':
        return current_send_time + timedelta(days=30)
    elif repeat_type == 'interval':
        return current_send_time + timedelta(minutes=repeat_interval)
    else:
        return current_send_time

def get_repeat_description(repeat_type: str, repeat_count: int, repeat_interval: int) -> str:
    """Возвращает описание повтора"""
    descriptions = {
        'once': "Однократно",
        'daily': f"Ежедневно ({repeat_count} раз)" if repeat_count > 0 else "Ежедневно (бесконечно)",
        'weekly': f"Еженедельно ({repeat_count} раз)" if repeat_count > 0 else "Еженедельно (бесконечно)",
        'monthly': f"Ежемесячно ({repeat_count} раз)" if repeat_count > 0 else "Ежемесячно (бесконечно)",
    }
    
    if repeat_type in descriptions:
        return descriptions[repeat_type]
    elif repeat_type == 'interval':
        if repeat_interval < 60:
            interval_desc = f"{repeat_interval} мин"
        elif repeat_interval < 1440:
            interval_desc = f"{repeat_interval // 60} ч"
        else:
            interval_desc = f"{repeat_interval // 1440} дн"
        
        if repeat_count > 0:
            return f"Каждые {interval_desc} ({repeat_count} раз)"
        else:
            return f"Каждые {interval_desc} (бесконечно)"
    
    return "Неизвестно"
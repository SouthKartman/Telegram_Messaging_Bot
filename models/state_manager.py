from typing import Dict, Any, Optional

class StateManager:
    def __init__(self):
        self._user_states: Dict[str, str] = {}
        self._user_data: Dict[str, Dict[str, Any]] = {}
    
    def get_state(self, user_id: str) -> Optional[str]:
        return self._user_states.get(user_id)
    
    def set_state(self, user_id: str, state: str):
        self._user_states[user_id] = state
    
    def clear_state(self, user_id: str):
        self._user_states.pop(user_id, None)
        self._user_data.pop(user_id, None)
    
    def get_data(self, user_id: str, key: str, default: Any = None) -> Any:
        return self._user_data.get(user_id, {}).get(key, default)
    
    def set_data(self, user_id: str, key: str, value: Any):
        if user_id not in self._user_data:
            self._user_data[user_id] = {}
        self._user_data[user_id][key] = value
    
    def clear_data(self, user_id: str, key: str):
        if user_id in self._user_data and key in self._user_data[user_id]:
            del self._user_data[user_id][key]

# Глобальный экземпляр менеджера состояний
state_manager = StateManager()
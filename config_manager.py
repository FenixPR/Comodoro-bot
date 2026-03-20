import json
import os
import logging
from typing import Dict, Any, Optional

class ConfigManager:
    def __init__(self, config_file: Optional[str] = None):
        if config_file is None:
            # Padrão para o diretório onde o script está localizado
            script_dir = os.path.dirname(os.path.abspath(__file__))
            self.config_file = os.path.join(script_dir, "bot_config.json")
        else:
            self.config_file = config_file
            
        self.logger = logging.getLogger(__name__)
        self.default_config = {
            "trading": {
                "symbol": "R_75",
                "stake_amount": 0.80,
                "max_loss": 0.80,
                "target_profit": 7.0,
                "martingale_multiplier": 4.1,
                "signal_cooldown": 60,
                "max_reentries": 2,
                "martingale_max_consecutive_losses": 5
            },
            "strategy": {
                "target_digits": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                "confidence_threshold": 0.6,
                "use_martingale": True,
                "risk_management": True
            },
            "notifications": {
                "send_statistics": True,
                "statistics_interval": 3600,
                "send_errors": True,
                "send_startup": True
            },
            "advanced": {
                "max_signals_per_hour": 10,
                "enable_backtesting": False,
                "log_level": "INFO",
                "auto_restart": True
            },
            "telegram": {
                "bot_token": "",
                "chat_id": ""
            },
            "deriv": {
                "app_id": "",
                "api_token": ""
            },
            "ai": {
                "openai_api_key": "",
                "openai_base_url": "https://api.openai.com/v1",
                "model": "gemini-2.5-flash"
            }
        }
        
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return self._merge_configs(self.default_config, config)
            return self.default_config.copy()
        except Exception as e:
            self.logger.error(f"Erro ao carregar config: {e}")
            return self.default_config.copy()
    
    def save_config(self, config: Optional[Dict[str, Any]] = None):
        try:
            config_to_save = config or self.config
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Erro ao salvar config: {e}")
    
    def _merge_configs(self, default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        merged = default.copy()
        for key, value in user.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_configs(merged[key], value)
            else:
                merged[key] = value
        return merged
    
    def get(self, key_path: str, default: Any = None) -> Any:
        try:
            keys = key_path.split('.')
            value = self.config
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key_path: str, value: Any):
        try:
            keys = key_path.split('.')
            config = self.config
            for key in keys[:-1]:
                if key not in config:
                    config[key] = {}
                config = config[key]
            config[keys[-1]] = value
        except Exception as e:
            self.logger.error(f"Erro ao definir config {key_path}: {e}")

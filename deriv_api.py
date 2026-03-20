# deriv_api.py - Versão Robusta com Reconexão Automática

import websocket
import json
import threading
import time
import logging
from typing import Callable, Optional
import asyncio

class DerivAPI:
    def __init__(self, app_id: str, api_token: Optional[str] = None):
        if not app_id or not api_token:
            raise ValueError("App ID e API Token da Deriv não podem ser nulos.")
        self.app_id = app_id
        self.api_token = api_token
        self.ws_url = f"wss://ws.derivws.com/websockets/v3?app_id={app_id}"
        self.ws = None
        self.is_connected = False
        self.callbacks = {}
        self.logger = logging.getLogger(__name__)
        self.loop = None
        self.active_contract_id = None
        self.ws_thread = None
        self.should_reconnect = True

    def connect(self):
        self.logger.info("A tentar conectar à Deriv API...")
        try:
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            self.ws_thread = threading.Thread(target=self.ws.run_forever)
            self.ws_thread.daemon = True
            self.ws_thread.start()
            
            # Espera um pouco para a conexão ser estabelecida
            for _ in range(10):
                if self.is_connected:
                    break
                time.sleep(1)
            
            if not self.is_connected:
                self.logger.error("Falha ao conectar com a Deriv API no tempo esperado.")
                return False
                
            self.logger.info("Conectado à Deriv API com sucesso")
            return True
        except Exception as e:
            self.logger.error(f"Erro ao conectar à Deriv API: {e}")
            return False

    def _on_open(self, ws):
        self.is_connected = True
        self.logger.info("Conexão WebSocket aberta")
        if self.api_token:
            self.authorize()

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            msg_type = data.get("msg_type")

            if msg_type == "tick":
                if "tick" in self.callbacks and self.loop:
                    asyncio.run_coroutine_threadsafe(self.callbacks["tick"](data.get("tick")), self.loop)
            
            elif msg_type == "authorize":
                if not data.get("error"):
                    self.logger.info("Autorização bem-sucedida")
                else:
                    self.logger.error(f"Erro de autorização: {data['error']['message']}")
            
            elif msg_type == "buy":
                if data.get("error"):
                    self.logger.error(f"Erro ao comprar contrato: {data['error']['message']}")
                else:
                    contract_id = data.get("buy", {}).get("contract_id")
                    if contract_id:
                        self.active_contract_id = contract_id
                        self.send_message({"proposal_open_contract": 1, "contract_id": self.active_contract_id, "subscribe": 1})

            elif msg_type == "proposal_open_contract":
                poc = data.get("proposal_open_contract", {})
                if poc.get("is_sold"):
                    if "trade_result" in self.callbacks and self.loop:
                        result = "WIN" if poc.get("profit", 0) > 0 else "LOSS"
                        asyncio.run_coroutine_threadsafe(self.callbacks["trade_result"](result, poc), self.loop)
                    self.active_contract_id = None
        
        except Exception as e:
            self.logger.error(f"Erro ao processar mensagem: {e}")

    def _on_error(self, ws, error):
        self.logger.error(f"Erro de WebSocket: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        self.is_connected = False
        if self.should_reconnect:
            self.logger.warning("Conexão WebSocket fechada. A tentar reconectar em 5 segundos...")
            time.sleep(5)
            # Reconectar em uma nova thread para não bloquear a thread de fechamento
            threading.Thread(target=self.connect).start()

    def authorize(self):
        message = {"authorize": self.api_token}
        self.send_message(message)

    def send_message(self, message: dict):
        if not self.is_connected or not self.ws:
            self.logger.error("WebSocket não está conectado. Mensagem não enviada.")
            return False
        try:
            self.ws.send(json.dumps(message))
            return True
        except Exception as e:
            self.logger.error(f"Erro ao enviar mensagem: {e}")
            return False

    def subscribe_to_ticks(self, symbol: str):
        message = {"ticks": symbol, "subscribe": 1}
        return self.send_message(message)
        
    def buy_contract(self, contract_type: str, amount: float, barrier: str, 
                     duration: int, duration_unit: str, symbol: str):
        """Função correta para comprar um contrato de dígito."""
        self.logger.info(f"A enviar ordem de compra: {contract_type} {symbol} | Barreira: {barrier} | Valor: {amount}")
        message = {
            "buy": 1,
            "price": 10000, # Um valor alto para garantir que o preço seja aceite
            "parameters": {
                "amount": amount,
                "basis": "stake",
                "contract_type": contract_type,
                "currency": "USD",
                "duration": duration,
                "duration_unit": duration_unit,
                "symbol": symbol,
                "barrier": barrier
            }
        }
        return self.send_message(message)

    def set_callback(self, event_type: str, callback: Callable, loop: asyncio.AbstractEventLoop):
        self.callbacks[event_type] = callback
        self.loop = loop

    def disconnect(self):
        self.should_reconnect = False
        if self.ws:
            self.ws.close()

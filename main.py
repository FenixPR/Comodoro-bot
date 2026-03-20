import logging
import os
import sys
import signal
import time
import asyncio
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

from deriv_api import DerivAPI
from telegram_bot import TelegramTradingBot
from trading_strategy import TradingStrategy
from config_manager import ConfigManager

# Servidor Keep-Alive para o Render
app = Flask('')
@app.route('/')
def health_check():
    return "Bot Kratos está online e operando!", 200

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

class TradingBotMain:
    def __init__(self):
        load_dotenv()
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, "bot_config.json")
        self.config_manager = ConfigManager(config_path)

        # Atualiza configurações via Variáveis de Ambiente
        env_vars = {
            "telegram.bot_token": os.getenv("TELEGRAM_BOT_TOKEN"),
            "telegram.chat_id": os.getenv("TELEGRAM_CHAT_ID"),
            "deriv.app_id": os.getenv("DERIV_APP_ID"),
            "deriv.api_token": os.getenv("DERIV_API_TOKEN"),
            "trading.stake_amount": os.getenv("STAKE_AMOUNT"),
            "trading.martingale_multiplier": os.getenv("MARTINGALE_MULTIPLIER")
        }
        for k, v in env_vars.items():
            if v: self.config_manager.set(k, v)
        
        self.config_manager.save_config()

        self.deriv_api = DerivAPI(
            app_id=self.config_manager.get("deriv.app_id"),
            api_token=self.config_manager.get("deriv.api_token")
        )
        
        self.telegram_bot = TelegramTradingBot(
            bot_token=self.config_manager.get("telegram.bot_token"),
            chat_id=self.config_manager.get("telegram.chat_id"),
            start_callback=self.start_trading,
            stop_callback=self.stop_trading,
            profit_callback=self.set_target_profit,
            loss_callback=self.set_max_loss
        )
        self.trading_strategy = TradingStrategy(self.config_manager)
        
        self.total_profit = 0.0
        self.target_profit = float(self.config_manager.get('trading.target_profit', 100.0))
        self.max_loss = -abs(float(self.config_manager.get('trading.max_loss', 1000.0)))

        self.is_running = False
        self.is_trade_in_progress = False
        self.shutdown_requested = False
        self.is_paused = False
        self.pause_end_time = 0

        signal.signal(signal.SIGINT, self.signal_handler)

    def setup_logging(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s',
                            handlers=[logging.StreamHandler(sys.stdout)])

    def signal_handler(self, signum, frame):
        self.stop()

    async def start_trading(self):
        self.is_running = True
        await self.telegram_bot.send_status_message("✅ Bot Iniciado.")

    async def stop_trading(self):
        self.is_running = False
        await self.telegram_bot.send_status_message("🛑 Bot Parado.")

    async def set_target_profit(self, val): self.target_profit = val
    async def set_max_loss(self, val): self.max_loss = -abs(val)
    
    async def start(self):
        try:
            if not await self.telegram_bot.test_connection(): raise Exception("Erro Telegram")
            if not self.deriv_api.connect(): raise Exception("Erro Deriv")
            
            self.deriv_api.set_callback("tick", self.on_tick_received, asyncio.get_running_loop())
            self.deriv_api.set_callback("trade_result", self.on_trade_result, asyncio.get_running_loop())

            for s in ["R_100", "R_75", "R_50"]: self.deriv_api.subscribe_to_ticks(s)
            
            asyncio.create_task(self.telegram_bot.run_polling())
            
            while not self.shutdown_requested:
                # Retomada automática após pausa
                if self.is_running and self.is_paused and time.time() >= self.pause_end_time:
                    self.is_paused = False
                    self.trading_strategy.reset()
                    self.logger.info("Retomando operações automaticamente.")
                await asyncio.sleep(2)
        finally: self.stop()
    
    async def on_tick_received(self, tick_data):
        if not self.is_running or self.is_trade_in_progress or self.is_paused: return
        trade_signal = self.trading_strategy.analyze_tick(tick_data)
        if trade_signal:
            self.is_trade_in_progress = True
            await self.telegram_bot.send_trade_notification(trade_signal)
            self.deriv_api.buy_contract(**trade_signal)

    async def on_trade_result(self, result: str, details: dict):
        profit = float(details.get('profit', 0.0))
        self.total_profit += profit
        await self.telegram_bot.send_result_notification(result, profit, self.total_profit)
        
        self.trading_strategy.on_trade_result(result)
        self.is_trade_in_progress = False # CORREÇÃO: Libera a trava sempre

        # Pausa de segurança após 2 losses
        if self.trading_strategy.consecutive_losses >= 2:
            self.is_paused = True
            self.pause_end_time = time.time() + 300
            await self.telegram_bot.send_status_message("⚠️ Pausa de 5 min (2 Losses). Aguarde.")
        
        elif self.total_profit >= self.target_profit or self.total_profit <= self.max_loss:
            self.is_running = False
            await self.telegram_bot.send_status_message("🏁 Meta atingida ou Stop Loss. Bot offline.")

    def stop(self):
        self.shutdown_requested = True
        self.deriv_api.disconnect()

if __name__ == "__main__":
    # Inicia Web Server para o Render
    Thread(target=run_web_server, daemon=True).start()
    
    bot = TradingBotMain()
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        bot.stop()

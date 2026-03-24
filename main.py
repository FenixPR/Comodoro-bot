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

app = Flask('')
@app.route('/')
def home(): return "Kratos Xeque-Mate Online!", 200

def run_web():
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

        deriv_app_id = os.getenv("DERIV_APP_ID") or self.config_manager.get("deriv.app_id")
        deriv_token = os.getenv("DERIV_API_TOKEN") or self.config_manager.get("deriv.api_token")
        tg_token = os.getenv("TELEGRAM_BOT_TOKEN") or self.config_manager.get("telegram.bot_token")
        tg_chat_id = os.getenv("TELEGRAM_CHAT_ID") or self.config_manager.get("telegram.chat_id")

        self.deriv_api = DerivAPI(app_id=deriv_app_id, api_token=deriv_token)
        self.telegram_bot = TelegramTradingBot(bot_token=tg_token, chat_id=tg_chat_id, 
                                             start_callback=self.start_trading, stop_callback=self.stop_trading)
        self.trading_strategy = TradingStrategy(self.config_manager)
        
        self.total_profit = 0.0
        self.total_wins = 0
        self.total_losses = 0
        self.is_running = False
        self.is_trade_in_progress = False
        self.shutdown_requested = False
        self.is_paused = False
        self.pause_end_time = 0

    def setup_logging(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', handlers=[logging.StreamHandler(sys.stdout)])

    async def start(self):
        try:
            if not self.deriv_api.connect(): raise Exception("Erro Deriv")
            self.deriv_api.set_callback("tick", self.on_tick_received, asyncio.get_running_loop())
            self.deriv_api.set_callback("trade_result", self.on_trade_result, asyncio.get_running_loop())

            # ATIVOS REATIVADOS
            for s in ["R_100", "R_75", "R_50", "R_25", "R_10"]: self.deriv_api.subscribe_to_ticks(s)
            
            asyncio.create_task(self.telegram_bot.run_polling())
            asyncio.create_task(self.hourly_report_loop())
            
            while not self.shutdown_requested:
                if self.is_running and self.is_paused and time.time() >= self.pause_end_time:
                    self.is_paused = False
                    self.trading_strategy.reset()
                await asyncio.sleep(1)
        finally: self.stop()

    async def hourly_report_loop(self):
        while not self.shutdown_requested:
            await asyncio.sleep(3600)
            if self.total_wins + self.total_losses > 0:
                await self.telegram_bot.send_hourly_report(self.total_profit, self.total_wins, self.total_losses)

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
        if result == "WIN": self.total_wins += 1
        else: self.total_losses += 1
        await self.telegram_bot.send_result_notification(result, profit, self.total_profit)
        self.trading_strategy.on_trade_result(result)
        self.is_trade_in_progress = False

    async def start_trading(self): self.is_running = True
    async def stop_trading(self): self.is_running = False
    def stop(self): self.shutdown_requested = True; self.deriv_api.disconnect()

if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    bot = TradingBotMain()
    try: asyncio.run(bot.start())
    except KeyboardInterrupt: bot.stop()

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

# Servidor Flask para Render e UptimeRobot
app = Flask('')
@app.route('/')
def home(): return "Kratos Bot Online!", 200

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

        # --- FORÇA A LEITURA DAS VARIÁVEIS DO RENDER ---
        # Se estas variáveis existirem no Render, elas SOBRESCREVEM o arquivo JSON
        deriv_app_id = os.getenv("DERIV_APP_ID")
        deriv_token = os.getenv("DERIV_API_TOKEN")
        tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
        tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not deriv_app_id or not deriv_token:
            self.logger.error("ERRO CRÍTICO: DERIV_APP_ID ou DERIV_API_TOKEN não encontrados no Render!")
            # Tenta pegar do config manager como última esperança
            deriv_app_id = deriv_app_id or self.config_manager.get("deriv.app_id")
            deriv_token = deriv_token or self.config_manager.get("deriv.api_token")

        self.deriv_api = DerivAPI(app_id=deriv_app_id, api_token=deriv_token)
        
        self.telegram_bot = TelegramTradingBot(
            bot_token=tg_token or self.config_manager.get("telegram.bot_token"),
            chat_id=tg_chat_id or self.config_manager.get("telegram.chat_id"),
            start_callback=self.start_trading,
            stop_callback=self.stop_trading
        )
        
        self.trading_strategy = TradingStrategy(self.config_manager)
        
        # Estatísticas para o relatório de 1 hora
        self.total_profit = 0.0
        self.total_wins = 0
        self.total_losses = 0

        self.is_running = False
        self.is_trade_in_progress = False
        self.shutdown_requested = False
        self.is_paused = False
        self.pause_end_time = 0

    def setup_logging(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s',
                            handlers=[logging.StreamHandler(sys.stdout)])

    async def start(self):
        try:
            self.logger.info("Iniciando conexão com Deriv...")
            if not self.deriv_api.connect(): 
                raise Exception("Não foi possível conectar à Deriv. Verifique o Token e o App ID.")
            
            self.deriv_api.set_callback("tick", self.on_tick_received, asyncio.get_running_loop())
            self.deriv_api.set_callback("trade_result", self.on_trade_result, asyncio.get_running_loop())

            for s in ["R_100", "R_75", "R_50"]: self.deriv_api.subscribe_to_ticks(s)
            
            asyncio.create_task(self.telegram_bot.run_polling())
            asyncio.create_task(self.hourly_report_loop())
            
            self.logger.info("Bot pronto! Aguardando comando /start_bot no Telegram.")
            
            while not self.shutdown_requested:
                if self.is_running and self.is_paused and time.time() >= self.pause_end_time:
                    self.is_paused = False
                    self.trading_strategy.reset()
                await asyncio.sleep(1)
        except Exception as e:
            self.logger.error(f"Erro no loop principal: {e}")
        finally: self.stop()

    async def hourly_report_loop(self):
        while not self.shutdown_requested:
            await asyncio.sleep(3600) # 1 hora
            if self.total_wins + self.total_losses > 0:
                await self.telegram_bot.send_hourly_report(
                    self.total_profit, self.total_wins, self.total_losses
                )

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

        if self.trading_strategy.consecutive_losses >= 2:
            self.is_paused = True
            self.pause_end_time = time.time() + 300
            await self.telegram_bot.send_status_message("⚠️ Pausa de 5 min (2 Losses consecutivas).")

    async def start_trading(self): 
        self.is_running = True
        self.logger.info("Operações iniciadas via Telegram.")

    async def stop_trading(self): 
        self.is_running = False
        self.logger.info("Operações paradas via Telegram.")

    def stop(self): 
        self.shutdown_requested = True
        self.deriv_api.disconnect()

if __name__ == "__main__":
    # Inicia Web Server para o Render/UptimeRobot
    Thread(target=run_web, daemon=True).start()
    
    bot = TradingBotMain()
    try: 
        asyncio.run(bot.start())
    except KeyboardInterrupt: 
        bot.stop()

import logging
import os
import sys
import signal
import time
import asyncio
from dotenv import load_dotenv
from aiohttp import web

from deriv_api import DerivAPI
from telegram_bot import TelegramTradingBot
from trading_strategy import TradingStrategy
from config_manager import ConfigManager

class TradingBotMain:
    def __init__(self):
        load_dotenv()
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Obter o caminho absoluto para o diretório do script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, "bot_config.json")
        
        self.config_manager = ConfigManager(config_path)
        # Carrega valores do .env apenas se eles existirem
        env_vars = {
            "telegram.bot_token": os.getenv("TELEGRAM_BOT_TOKEN"),
            "telegram.chat_id": os.getenv("TELEGRAM_CHAT_ID"),
            "deriv.app_id": os.getenv("DERIV_APP_ID"),
            "deriv.api_token": os.getenv("DERIV_API_TOKEN"),
            "ai.openai_api_key": os.getenv("OPENAI_API_KEY"),
            "ai.openai_base_url": os.getenv("OPENAI_BASE_URL"),
            "ai.model": os.getenv("AI_MODEL"),
            "trading.symbol": os.getenv("SYMBOL"),
            "trading.stake_amount": os.getenv("STAKE_AMOUNT"),
            "trading.target_profit": os.getenv("TARGET_PROFIT"),
            "trading.martingale_multiplier": os.getenv("MARTINGALE_MULTIPLIER"),
            "trading.martingale_max_consecutive_losses": os.getenv("MARTINGALE_MAX_CONSECUTIVE_LOSSES")
        }
        
        for key, value in env_vars.items():
            if value is not None:
                self.config_manager.set(key, value)
        
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
        self.total_wins = 0
        self.total_losses = 0
        self.last_report_time = time.time()
        
        self.target_profit = float(self.config_manager.get('trading.target_profit', 100.0))
        self.max_loss = -abs(float(self.config_manager.get('trading.max_loss', 1000.0)))

        self.is_running = False
        self.is_trade_in_progress = False
        self.shutdown_requested = False
        self.is_paused = False
        self.pause_end_time = 0

        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def setup_logging(self):
        # Configuração simplificada para evitar erro de disco cheio no Windows
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                            handlers=[logging.StreamHandler(sys.stdout)])

    def signal_handler(self, signum, frame):
        self.logger.info("Sinal de encerramento recebido.")
        self.stop()

    async def start_trading(self):
        if self.is_running: return
        self.is_running = True
        await self.telegram_bot.send_status_message("✅ Bot iniciado e a monitorar múltiplos ativos.")

    async def stop_trading(self):
        if not self.is_running: return
        self.is_running = False
        await self.telegram_bot.send_status_message("🛑 Bot parado.")

    async def set_target_profit(self, new_profit: float):
        self.target_profit = new_profit
        await self.telegram_bot.send_status_message(f"✅ Meta de lucro: ${new_profit:.2f}")

    async def set_max_loss(self, new_loss: float):
        self.max_loss = -abs(new_loss)
        await self.telegram_bot.send_status_message(f"✅ Stop Loss: ${new_loss:.2f}")
    
    # --- NOVA FUNÇÃO DO SERVIDOR WEB ---
    async def web_server(self):
        """Mini servidor para enganar o Render e manter o bot acordado."""
        async def health_check(request):
            return web.Response(text="Bot Kratos 100% Online e Operando!")
            
        app = web.Application()
        app.router.add_get('/', health_check)
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        # O Render fornece a porta automaticamente nesta variável de ambiente
        port = int(os.environ.get("PORT", 8080))
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        self.logger.info(f"🌐 Servidor Web de Manutenção rodando na porta {port}")

    async def start(self):
        try:
            if not await self.telegram_bot.test_connection(): raise Exception("Falha Telegram")
            if not self.deriv_api.connect(): raise Exception("Falha Deriv")
            
            self.deriv_api.set_callback("tick", self.on_tick_received, asyncio.get_running_loop())
            self.deriv_api.set_callback("trade_result", self.on_trade_result, asyncio.get_running_loop())

            symbols = ["R_100", "R_75", "R_50", "R_25", "R_10"]
            for s in symbols: self.deriv_api.subscribe_to_ticks(s)
            
            # --- INICIA O SERVIDOR WEB JUNTO COM O BOT ---
            asyncio.create_task(self.web_server())
            
            telegram_task = asyncio.create_task(self.telegram_bot.run_polling())
            await self.telegram_bot.send_status_message("🤖 Bot Conectado. \nDefina o valor inicial com /set_stake 1.00\nInicie com /start_bot")
            
            while not self.shutdown_requested:
                current_time = time.time()
                
                if self.is_running and (current_time - self.last_report_time) >= 300:
                    self.last_report_time = current_time
                    await self.telegram_bot.send_periodic_report(self.total_profit, self.total_wins, self.total_losses)
                
                await asyncio.sleep(5)
            telegram_task.cancel()
        except Exception as e:
            self.logger.error(f"Erro: {e}")
        finally: self.stop()
    
    async def on_tick_received(self, tick_data):
        if not self.is_running or self.is_trade_in_progress or self.is_paused: return
        try:
            trade_signal = self.trading_strategy.analyze_tick(tick_data)
            if trade_signal:
                self.is_trade_in_progress = True
                await self.telegram_bot.send_trade_notification(trade_signal)
                self.deriv_api.buy_contract(**trade_signal)
        except Exception as e:
            self.logger.error(f"Erro tick: {e}")
            self.is_trade_in_progress = False

    async def on_trade_result(self, result: str, details: dict):
        try:
            profit = float(details.get('profit', 0.0))
            self.total_profit += profit
            if result == "WIN": self.total_wins += 1
            else: self.total_losses += 1

            await self.telegram_bot.send_result_notification(result, profit, self.total_profit)
            self.trading_strategy.on_trade_result(result)

            # LIBERA SEMPRE A OPERAÇÃO APÓS O RESULTADO
            self.is_trade_in_progress = False

            if self.trading_strategy.consecutive_losses >= 2:
                self.is_paused = True
                self.pause_end_time = time.time() + 300
                self.is_trade_in_progress = True # Mantém travado durante a pausa
                await self.telegram_bot.send_status_message("⚠️ Pausa de 5 min (2 perdas).")
            elif self.total_profit >= self.target_profit or self.total_profit <= self.max_loss:
                self.is_running = False
                await self.telegram_bot.send_status_message(f"🏁 Meta/Stop atingido. Lucro: {self.total_profit:.2f}")
        except Exception as e:
            self.logger.error(f"Erro resultado: {e}")
            self.is_trade_in_progress = False

    def stop(self):
        self.shutdown_requested = True
        self.deriv_api.disconnect()

if __name__ == "__main__":
    bot = TradingBotMain()
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        bot.stop()

# telegram_bot.py - Versão Sniper com Emoji de Grana e Relatórios
import logging
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError
from typing import Callable, Awaitable, Optional

class TelegramTradingBot:
    def __init__(self, bot_token: str, chat_id: str, 
                 start_callback: Optional[Callable[[], Awaitable[None]]] = None, 
                 stop_callback: Optional[Callable[[], Awaitable[None]]] = None,
                 profit_callback: Optional[Callable[[float], Awaitable[None]]] = None,
                 loss_callback: Optional[Callable[[float], Awaitable[None]]] = None):
        if not bot_token or not chat_id:
            raise ValueError("O token do bot e o chat_id não podem ser nulos.")
        
        self.bot_token = bot_token
        self.chat_id = str(chat_id)
        self.bot = Bot(token=bot_token)
        self.logger = logging.getLogger(__name__)

        self.application = Application.builder().token(bot_token).build()

        # Callbacks de controle
        self.start_callback = start_callback
        self.stop_callback = stop_callback
        self.profit_callback = profit_callback
        self.loss_callback = loss_callback

        # Handlers de comando
        self.application.add_handler(CommandHandler("start_bot", self.start_command))
        self.application.add_handler(CommandHandler("stop_bot", self.stop_command))
        self.application.add_handler(CommandHandler("set_profit", self.set_profit_command))
        self.application.add_handler(CommandHandler("set_loss", self.set_loss_command))

    def is_authorized(self, update: Update) -> bool:
        return str(update.effective_chat.id) == self.chat_id

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized(update): return
        await update.message.reply_text("▶️ Comando recebido. Iniciando operações Sniper...")
        if self.start_callback: await self.start_callback()

    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized(update): return
        await update.message.reply_text("⏸️ Comando recebido. Parando o bot...")
        if self.stop_callback: await self.stop_callback()

    async def set_profit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized(update): return
        try:
            val = float(context.args[0])
            if self.profit_callback: await self.profit_callback(val)
            await update.message.reply_text(f"✅ Nova meta de lucro: ${val:.2f}")
        except: await update.message.reply_text("Uso: /set_profit 100")

    async def set_loss_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized(update): return
        try:
            val = float(context.args[0])
            if self.loss_callback: await self.loss_callback(val)
            await update.message.reply_text(f"✅ Novo Stop Loss: ${val:.2f}")
        except: await update.message.reply_text("Uso: /set_loss 50")

    async def run_polling(self):
        self.logger.info("O bot do Telegram está ouvindo comandos...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

    async def send_status_message(self, status: str):
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=status, parse_mode='HTML')
        except Exception as e:
            self.logger.error(f"Erro ao enviar status: {e}")

    async def send_trade_notification(self, trade_params: dict):
        """Notifica a execução de uma nova ordem Sniper."""
        message = f"""
🎯 <b>Sniper: Nova Operação</b> 🎯

• <b>Ativo:</b> {trade_params['symbol']}
• <b>Tipo:</b> {trade_params['contract_type']}
• <b>Valor:</b> ${trade_params['amount']:.2f}
• <b>Barreira:</b> {trade_params['barrier']}
        """
        await self.send_status_message(message)

    async def send_result_notification(self, result: str, profit: float, total_profit: float):
        """Notifica o resultado com o emoji de grana solicitado."""
        # Lógica visual para WIN 💰
        if result == "WIN":
            emoji_header = "💰💰💰 WIN! 💰💰💰"
            profit_text = f"+${profit:.2f}"
        else:
            emoji_header = "❌ LOSS"
            profit_text = f"-${abs(profit):.2f}"

        message = f"""
        -- <b>Resultado da Operação</b> --
<b>{emoji_header}</b>
<b>Lucro/Perda:</b> {profit_text}
<b>Saldo Acumulado:</b> ${total_profit:.2f}
        """
        await self.send_status_message(message)

    async def send_hourly_report(self, total_profit: float, total_wins: int, total_losses: int):
        """Relatório automático enviado a cada 1 hora."""
        win_rate = (total_wins / (total_wins + total_losses) * 100) if (total_wins + total_losses) > 0 else 0
        status_emoji = "💰" if total_profit >= 0 else "📉"
        
        message = f"""
⏱️ <b>Relatório Horário Sniper</b> ⏱️

<b>Saldo Total:</b> {status_emoji} ${total_profit:.2f}

✅ <b>Vitórias:</b> {total_wins}
❌ <b>Derrotas:</b> {total_losses}
📈 <b>Taxa de Acerto:</b> {win_rate:.2f}%
        """
        await self.send_status_message(message)

    async def test_connection(self):
        try:
            await self.bot.get_me()
            return True
        except: return False

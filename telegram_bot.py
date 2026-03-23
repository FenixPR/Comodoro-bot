import logging
from telegram import Bot
from telegram.error import TelegramError

class TelegramTradingBot:
    def __init__(self, bot_token: str, chat_id: str):
        self.logger = logging.getLogger(__name__)
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id
        self.is_connected = False

    async def send_status_message(self, text: str):
        """Envia uma mensagem de status simples."""
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode='Markdown')
        except TelegramError as e:
            self.logger.error(f"Erro ao enviar mensagem Telegram: {e}")

    async def send_trade_notification(self, trade_data: dict):
        """Notifica o início de uma operação."""
        msg = (
            f"🎬 *Nova Operação Iniciada*\n"
            f"Ativo: `{trade_data['symbol']}`\n"
            f"Tipo: `{trade_data['contract_type']}`\n"
            f"Valor: `${trade_data['amount']:.2f}`\n"
            f"Barreira: `{trade_data['barrier']}`"
        )
        await self.send_status_message(msg)

    async def send_result_notification(self, result: str, profit: float, total_profit: float):
        """Notifica o resultado com o emoji solicitado."""
        
        # --- NOVO: ALTERAÇÃO DO EMOJI DE WIN ---
        if result == "WIN":
            # Substitui "WIN" por um emoji de grana chamativo
            result_text = "💰💰💰 WIN! 💰💰💰"
            profit_prefix = "+"
        else: # LOSS
            result_text = "😡 LOSS"
            profit_prefix = ""

        msg = (
            f"🏁 *Resultado da Operação*\n"
            f"Resultado: *{result_text}*\n"
            f"Lucro/Perda: `{profit_prefix}${profit:.2f}`\n"
            f"Saldo Acumulado: `${total_profit:.2f}`"
        )
        await self.send_status_message(msg)

    async def send_hourly_report(self, total_profit: float, wins: int, losses: int):
        """Envia o relatório horário."""
        total_ops = wins + losses
        win_rate = (wins / total_ops * 100) if total_ops > 0 else 0
        
        # Emoji no relatório também
        profit_emoji = "💰" if total_profit >= 0 else "😡"

        msg = (
            f"📊 *Relatório Horário de Operações*\n"
            f"Saldo Total: {profit_emoji} `${total_profit:.2f}`\n"
            f"Vitórias (Wins): `{wins}`\n"
            f"Derrotas (Losses): `{losses}`\n"
            f"Taxa de Acerto: `{win_rate:.2f}%`"
        )
        await self.send_status_message(msg)            self.logger.error(f"Erro ao enviar mensagem de erro: {e}")

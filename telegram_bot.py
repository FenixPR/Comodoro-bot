# telegram_bot.py - Versão com Comandos para Definir Lucro e Perda

import logging
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from typing import Callable, Awaitable, Optional

class TelegramTradingBot:
    def __init__(self, bot_token: str, chat_id: str, 
                 start_callback: Callable[[], Awaitable[None]], 
                 stop_callback: Callable[[], Awaitable[None]],
                 # --- NOVOS PARÂMETROS ---
                 profit_callback: Optional[Callable[[float], Awaitable[None]]] = None,
                 loss_callback: Optional[Callable[[float], Awaitable[None]]] = None):
        if not bot_token or not chat_id:
            raise ValueError("O token do bot e o chat_id não podem ser nulos.")
        
        self.bot_token = bot_token
        self.chat_id = str(chat_id)
        self.bot = Bot(token=bot_token)
        self.logger = logging.getLogger(__name__)

        self.application = Application.builder().token(bot_token).build()

        # Callbacks de controlo
        self.start_callback = start_callback
        self.stop_callback = stop_callback
        # --- NOVOS CALLBACKS ---
        self.profit_callback = profit_callback
        self.loss_callback = loss_callback

        # Handlers de comando
        self.application.add_handler(CommandHandler("start_bot", self.start_command))
        self.application.add_handler(CommandHandler("stop_bot", self.stop_command))
        # --- NOVOS HANDLERS ---
        self.application.add_handler(CommandHandler("set_profit", self.set_profit_command))
        self.application.add_handler(CommandHandler("set_loss", self.set_loss_command))

    def is_authorized(self, update: Update) -> bool:
        """Verifica se o comando vem do chat_id autorizado."""
        return str(update.effective_chat.id) == self.chat_id

    async def handle_unauthorized(self, update: Update):
        """Envia mensagem padrão para chats não autorizados."""
        chat_id_recebido = update.effective_chat.id
        self.logger.warning(f"Comando ignorado do chat_id não autorizado: {chat_id_recebido}")
        await update.message.reply_text(
            f"❌ **Não Autorizado** ❌\n\n"
            f"Não tens permissão para usar este comando.\n"
            f"`O teu Chat ID é: {chat_id_recebido}`\n\n"
            f"Por favor, verifica se o `TELEGRAM_CHAT_ID` no ficheiro de configuração está correto.",
            parse_mode='Markdown'
        )

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized(update):
            await self.handle_unauthorized(update)
            return
        
        self.logger.info("Comando /start_bot recebido do chat autorizado.")
        await update.message.reply_text("▶️ Comando para iniciar as operações recebido. A iniciar o bot...")
        await self.start_callback()

    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized(update):
            await self.handle_unauthorized(update)
            return
            
        self.logger.info("Comando /stop_bot recebido do chat autorizado.")
        await update.message.reply_text("⏸️ Comando para parar as operações recebido. A parar o bot...")
        await self.stop_callback()

    # --- NOVAS FUNÇÕES DE COMANDO ---
    async def set_profit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para o comando /set_profit."""
        if not self.is_authorized(update):
            await self.handle_unauthorized(update)
            return
        
        try:
            # Pega o valor passado junto com o comando (ex: /set_profit 150)
            new_profit = float(context.args[0])
            if new_profit <= 0:
                await update.message.reply_text("❌ Erro: O valor do lucro deve ser maior que zero.")
                return
            
            if self.profit_callback:
                await self.profit_callback(new_profit)
            else:
                await update.message.reply_text("Funcionalidade de definir lucro não configurada.")

        except (IndexError, ValueError):
            await update.message.reply_text("⚠️ **Uso incorreto.**\nPor favor, use o formato: `/set_profit <valor>`\n\n*Exemplo: /set_profit 150*")

    async def set_loss_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para o comando /set_loss."""
        if not self.is_authorized(update):
            await self.handle_unauthorized(update)
            return
        
        try:
            # Pega o valor passado junto com o comando (ex: /set_loss 75)
            new_loss = float(context.args[0])
            if new_loss <= 0:
                await update.message.reply_text("❌ Erro: O valor da perda máxima deve ser maior que zero.")
                return

            if self.loss_callback:
                await self.loss_callback(new_loss)
            else:
                await update.message.reply_text("Funcionalidade de definir perda não configurada.")
        
        except (IndexError, ValueError):
            await update.message.reply_text("⚠️ **Uso incorreto.**\nPor favor, use o formato: `/set_loss <valor>`\n\n*Exemplo: /set_loss 75*")


    async def run_polling(self):
        """Inicia o 'polling' para ouvir os comandos do Telegram."""
        self.logger.info("O bot do Telegram está a ouvir por comandos...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

    # --- O RESTO DAS FUNÇÕES PERMANECE IGUAL ---

    async def send_hourly_report(self, total_profit: float, total_wins: int, total_losses: int):
        try:
            win_rate = (total_wins / (total_wins + total_losses) * 100) if (total_wins + total_losses) > 0 else 0
            message = f"""
 Bip Bop...  Relatório Horário 

Saldo Total: ${total_profit:.2f}

Vitórias (Win): {total_wins}
Derrotas (Loss): {total_losses}
Taxa de Acerto: {win_rate:.2f}%
            """
            await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode='HTML')
            self.logger.info("Relatório horário enviado com sucesso.")
            return True
        except Exception as e:
            self.logger.error(f"Erro ao enviar o relatório horário: {e}")
            return False

    async def send_trade_notification(self, trade_params: dict):
        try:
            contract_type = trade_params['contract_type']
            amount = trade_params['amount']
            barrier = trade_params['barrier']
            symbol = trade_params['symbol']
            message = f"""
             Executando 
📈 **Nova Operação Executada** 📈

- **Ativo:** {symbol}
- **Contrato:** {contract_type}
- **Barreira:** {barrier}
- **Valor:** ${amount:.2f}
            """
            await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode='HTML')
            self.logger.info(f"Notificação de operação enviada: {contract_type} em {symbol}")
            return True
        except Exception as e:
            self.logger.error(f"Erro ao enviar notificação de operação: {e}")
            return False

    async def send_result_notification(self, result: str, profit: float, total_profit: float):
        try:
            emoji = "✅ WIN" if result == "WIN" else "❌ LOSS"
            profit_text = f"+${profit:.2f}" if profit > 0 else f"${profit:.2f}"

            message = f"""
            -- **Resultado da Operação** --
{emoji} **{result}**
Lucro/Perda: {profit_text}
Saldo Total: ${total_profit:.2f}
            """
            await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode='HTML')
            return True
        except Exception as e:
            self.logger.error(f"Erro ao enviar notificação de resultado: {e}")
            return False
            
    async def send_status_message(self, status: str):
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=status, parse_mode='HTML')
        except Exception as e:
            self.logger.error(f"Erro ao enviar status: {e}")

    async def test_connection(self):
        try:
            await self.bot.get_me()
            self.logger.info("Conexão com a API do Telegram bem-sucedida.")
            return True
        except Exception as e:
            self.logger.error(f"Erro ao testar conexão com o Telegram: {e}")
            return False
    
    async def send_error_message(self, error: str):
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=f"❌ <b>Erro Crítico:</b> {error}", parse_mode='HTML')
        except Exception as e:
            self.logger.error(f"Erro ao enviar mensagem de erro: {e}")
import logging
import time
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from technical_analyzer import TechnicalAnalyzer

class TradingStrategy:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.tech_analyzer = TechnicalAnalyzer()

        # === CONFIGURAÇÕES SEGURAS ===
        self.initial_stake = float(self.config_manager.get('trading.stake_amount', 0.60))
        self.sequence_1236 = [1.0, 3.0, 2.0, 6.0]   # Progressão 1-3-2-6
        self.current_level = 0
        self.current_stake = self.initial_stake

        self.max_daily_loss = float(self.config_manager.get('trading.max_daily_loss', 8.0))   # % da banca
        self.max_daily_trades = int(self.config_manager.get('trading.max_daily_trades', 15))
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.last_reset_day = date.today()

        self.tick_histories: Dict[str, List[float]] = {}
        self.global_pause_until = 0
        self.reset()

    def reset(self):
        self.current_level = 0
        self.current_stake = self.initial_stake
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.last_reset_day = date.today()

    def check_daily_risk(self):
        if date.today() != self.last_reset_day:
            self.reset()
        if self.daily_trades >= self.max_daily_trades or self.daily_pnl <= -self.max_daily_loss:
            self.logger.warning("🛑 Limite diário atingido (trades ou loss). Bot pausado até amanhã.")
            self.global_pause_until = time.time() + 86400  # 24h
            return False
        return True

    def analyze_tick(self, tick_data: dict) -> Optional[Dict[str, Any]]:
        if time.time() < self.global_pause_until:
            return None
        if not self.check_daily_risk():
            return None

        symbol = tick_data.get('symbol', 'Unknown')
        quote = float(tick_data.get('quote', 0))

        if symbol not in self.tick_histories:
            self.tick_histories[symbol] = []
        self.tick_histories[symbol].append(quote)

        if len(self.tick_histories[symbol]) >= 60:
            analysis = self.tech_analyzer.analyze_trend(symbol, self.tick_histories[symbol], quote)

            if analysis["status"] != "NEUTRAL" and analysis["confianca_score"] >= 9.5:
                operational_stake = round(self.initial_stake * self.sequence_1236[self.current_level], 2)

                self.logger.info(f"🚀 SINAL CERTO! {analysis['status']} | Confluências: {analysis['confluences']} | Score: {analysis['confianca_score']} | Stake: ${operational_stake}")

                if analysis["status"] == "OVERBOUGHT":
                    return self._create_trade_signal("DIGITUNDER", symbol, 8, operational_stake)
                elif analysis["status"] == "OVERSOLD":
                    return self._create_trade_signal("DIGITOVER", symbol, 1, operational_stake)

        return None

    def on_trade_result(self, result: str, profit: float = 0.0):
        self.daily_trades += 1
        self.daily_pnl += profit

        current_time = time.time()
        self.tick_histories.clear()

        if result == "WIN":
            self.logger.info("🎉 WIN! Subindo nível 1-3-2-6")
            self.current_level = (self.current_level + 1) % 4
            self.global_pause_until = current_time + 45
        else:
            self.logger.info("❌ LOSS – Resetando para stake inicial")
            self.current_level = 0
            self.global_pause_until = current_time + 90  # pausa maior após loss

        self.current_stake = round(self.initial_stake * self.sequence_1236[self.current_level], 2)

    def _create_trade_signal(self, contract_type, symbol, barrier, amount):
        return {
            "contract_type": contract_type,
            "amount": amount,
            "barrier": str(barrier),
            "duration": 1,
            "duration_unit": "t",
            "symbol": symbol
        }

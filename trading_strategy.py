import logging
import time
from typing import Optional, Dict, Any, List
from technical_analyzer import TechnicalAnalyzer

class TradingStrategy:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.tech_analyzer = TechnicalAnalyzer(rsi_period=14)

        # === CONFIGURAÇÕES CONSERVADORAS ===
        self.initial_stake = float(self.config_manager.get('trading.stake_amount', 0.60))
        self.martingale_multiplier = 2.0          # ← muito mais seguro
        self.max_recovery_attempts = 2            # ← máximo 2 recuperações
        self.max_stake_multiplier = 4.0           # ← nunca passa de 4x o inicial

        self.current_stake = self.initial_stake
        self.consecutive_losses = 0
        self.tick_histories: Dict[str, List[float]] = {}
        self.global_pause_until = 0
        self.reset()

    def reset(self):
        self.current_stake = self.initial_stake
        self.consecutive_losses = 0
        self.tick_histories.clear()

    def analyze_tick(self, tick_data: dict) -> Optional[Dict[str, Any]]:
        if time.time() < self.global_pause_until:
            return None

        symbol = tick_data.get('symbol', 'Unknown')
        quote = float(tick_data.get('quote', 0))

        if symbol not in self.tick_histories:
            self.tick_histories[symbol] = []
        self.tick_histories[symbol].append(quote)

        # Agora usa 60 ticks (mais robusto que 40)
        if len(self.tick_histories[symbol]) >= 60:
            analysis = self.tech_analyzer.analyze_trend(self.tick_histories[symbol])
            score = analysis.get("confianca_score", 0)

            # === SÓ OPERA COM CERTEZA ABSOLUTA ===
            if score >= 9.5:
                operational_stake = self.current_stake

                # XEQUE-MATE (score 10) → dobra a stake com segurança
                if score >= 10:
                    operational_stake = round(self.current_stake * 2.0, 2)
                    self.logger.info(f"🚀 XEQUE-MATE PERFEITO! Score {score} | Stake: ${operational_stake}")

                if analysis["status"] == "OVERBOUGHT":
                    return self._create_trade_signal("DIGITUNDER", symbol, 8, operational_stake)
                elif analysis["status"] == "OVERSOLD":
                    return self._create_trade_signal("DIGITOVER", symbol, 1, operational_stake)

        return None

    def on_trade_result(self, result: str):
        current_time = time.time()
        self.tick_histories.clear()

        if result == "WIN":
            self.logger.info("🎉 [WIN!] Operação com certeza total!")
            self.global_pause_until = current_time + 45
            self.reset()                     # reseta tudo
        else:
            self.consecutive_losses += 1
            self.logger.info(f"❌ [LOSS] Pausa de 75s + recalibrando Sniper...")

            self.global_pause_until = current_time + 75  # pausa maior após loss

            if self.consecutive_losses <= self.max_recovery_attempts:
                # Martingale seguro
                new_stake = round(self.current_stake * self.martingale_multiplier, 2)
                max_allowed = round(self.initial_stake * self.max_stake_multiplier, 2)
                self.current_stake = min(new_stake, max_allowed)
                self.logger.info(f"🔄 Martingale nível {self.consecutive_losses} → Stake: ${self.current_stake}")
            else:
                self.logger.warning("🛑 Máximo de recuperações atingido. Resetando para proteger banca.")
                self.reset()

    def _create_trade_signal(self, contract_type, symbol, barrier, amount):
        return {
            "contract_type": contract_type,
            "amount": amount,
            "barrier": str(barrier),
            "duration": 1,
            "duration_unit": "t",
            "symbol": symbol
        }

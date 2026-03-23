import logging
import time
from typing import Optional, Dict, Any, List
from technical_analyzer import TechnicalAnalyzer

class TradingStrategy:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.tech_analyzer = TechnicalAnalyzer(rsi_period=14)

        # Configurações base
        self.initial_stake = float(self.config_manager.get('trading.stake_amount', 0.6))
        self.martingale_multiplier = float(self.config_manager.get('trading.martingale_multiplier', 3.5))
        self.martingale_max_consecutive_losses = int(self.config_manager.get('trading.martingale_max_consecutive_losses', 5))

        self.current_stake = self.initial_stake
        self.tick_histories: Dict[str, List[float]] = {}
        self.global_pause_until = 0 
        
        self.reset()

    def reset(self):
        """Reseta para o estado inicial."""
        self.current_stake = self.initial_stake
        self.tick_histories.clear()

    def analyze_tick(self, tick_data: dict) -> Optional[Dict[str, Any]]:
        if time.time() < self.global_pause_until:
            return None

        symbol = tick_data.get('symbol', 'Unknown')
        quote = float(tick_data.get('quote', 0))
        
        if symbol not in self.tick_histories:
            self.tick_histories[symbol] = []
        
        self.tick_histories[symbol].append(quote)
        
        # Sniper precisa de um histórico sólido para calcular o RSI corretamente
        if len(self.tick_histories[symbol]) > 50:
            self.tick_histories[symbol].pop(0)

        if len(self.tick_histories[symbol]) >= 30:
            analysis = self.tech_analyzer.analyze_trend(self.tick_histories[symbol])
            score = analysis.get("confianca_score", 0)
            
            # SÓ ENTRA SE O SCORE FOR 7 OU MAIS (FILTRO SNIPER)
            if score >= 7:
                operational_stake = self.current_stake
                
                # LÓGICA DE CONFIANÇA: Se score >= 8, dobra a entrada (ex: 0.60 -> 1.20)
                if score >= 8:
                    operational_stake = round(self.current_stake * 2.0, 2)
                    self.logger.info(f"🎯 Sniper focado! Confiança Score {score}. Aumentando stake para ${operational_stake}")

                if analysis["status"] == "OVERBOUGHT":
                    return self._create_trade_signal("DIGITUNDER", symbol, 8, operational_stake)
                elif analysis["status"] == "OVERSOLD":
                    return self._create_trade_signal("DIGITOVER", symbol, 1, operational_stake)
        
        return None

    def on_trade_result(self, result: str):
        """Gerencia o pós-operação com emojis e pausas."""
        current_time = time.time()
        self.tick_histories.clear() # Limpa para nova análise Sniper do zero

        if result == "WIN":
            self.logger.info("--- [💰💰💰 WIN!] Alvo atingido. Resetando stake. ---")
            self.global_pause_until = current_time + 30
            self.current_stake = self.initial_stake
        else:
            self.logger.info("--- [😡 LOSS] Falha no disparo. Iniciando recuperação. ---")
            self.global_pause_until = current_time + 60 
            # Martingale aplicado sobre o stake base
            self.current_stake = round(self.current_stake * self.martingale_multiplier, 2)

    def _create_trade_signal(self, contract_type: str, symbol: str, barrier: Any, amount: float) -> Dict[str, Any]:
        return {
            "contract_type": contract_type,
            "amount": float(amount),
            "barrier": str(barrier),
            "duration": 1,
            "duration_unit": "t",
            "symbol": symbol
        }

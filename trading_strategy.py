import logging
import time
from typing import Optional, Dict, Any, List
from technical_analyzer import TechnicalAnalyzer

class TradingStrategy:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.tech_analyzer = TechnicalAnalyzer(rsi_period=14)

        # Configurações de Stake e Martingale Controlado
        self.initial_stake = float(self.config_manager.get('trading.stake_amount', 0.6))
        self.martingale_multiplier = 3.5 
        self.max_recovery_attempts = 3 # Limite de tentativas para proteger a banca

        self.current_stake = self.initial_stake
        self.consecutive_losses = 0
        self.tick_histories: Dict[str, List[float]] = {}
        self.global_pause_until = 0 
        
        self.reset()

    def reset(self):
        """Retorna ao estado inicial e limpa dados antigos."""
        self.logger.info("Estratégia Sniper resetada para o padrão.")
        self.current_stake = self.initial_stake
        self.consecutive_losses = 0
        self.tick_histories.clear()

    def analyze_tick(self, tick_data: dict) -> Optional[Dict[str, Any]]:
        # Verifica se o bot está em pausa de segurança (60s pós-loss)
        if time.time() < self.global_pause_until:
            return None

        symbol = tick_data.get('symbol', 'Unknown')
        quote = float(tick_data.get('quote', 0))
        
        if symbol not in self.tick_histories:
            self.tick_histories[symbol] = []
        
        self.tick_histories[symbol].append(quote)
        
        # Mantém histórico suficiente para análise precisa
        if len(self.tick_histories[symbol]) > 50:
            self.tick_histories[symbol].pop(0)

        # ANÁLISE CUIDADOSA: Requer 30 ticks de dados novos para agir
        if len(self.tick_histories[symbol]) >= 30:
            analysis = self.tech_analyzer.analyze_trend(self.tick_histories[symbol])
            score = analysis.get("confianca_score", 0)
            
            # SÓ ENTRA SE O SCORE FOR 7 OU MAIS
            if score >= 7:
                operational_stake = self.current_stake
                
                # LÓGICA DE CONFIANÇA: Se score >= 9, dobra a aposta (ex: 0.60 -> 1.20)
                if score >= 9:
                    operational_stake = round(self.current_stake * 2.0, 2)
                    self.logger.info(f"🚀 Sniper Confirmado! Score {score}. Stake: ${operational_stake}")

                if analysis["status"] == "OVERBOUGHT":
                    return self._create_trade_signal("DIGITUNDER", symbol, 8, operational_stake)
                elif analysis["status"] == "OVERSOLD":
                    return self._create_trade_signal("DIGITOVER", symbol, 1, operational_stake)
        
        return None

    def on_trade_result(self, result: str):
        """Processa o resultado e aplica a pausa de 1 minuto após perda."""
        current_time = time.time()
        self.tick_histories.clear() # Limpa histórico para forçar nova análise cuidadosa

        if result == "WIN":
            self.logger.info("--- [💰💰💰 WIN!] Lucro garantido. ---")
            self.global_pause_until = current_time + 45 # Pausa curta pós-win
            self.reset()
        else:
            self.consecutive_losses += 1
            # PAUSA OBRIGATÓRIA DE 60 SEGUNDOS APÓS LOSS
            self.logger.info(f"--- [😡 LOSS] Pausa de 60s. Analisando o mercado com cautela... ---")
            self.global_pause_until = current_time + 60 
            
            if self.consecutive_losses <= self.max_recovery_attempts:
                # Aplica Martingale controlado de 3.5x
                self.current_stake = round(self.current_stake * self.martingale_multiplier, 2)
            else:
                self.logger.warning("ALERTA: Stop Loss de recuperação atingido para proteger banca.")
                self.reset()

    def _create_trade_signal(self, contract_type, symbol, barrier, amount) -> Dict[str, Any]:
        return {
            "contract_type": contract_type,
            "amount": float(amount),
            "barrier": str(barrier),
            "duration": 1,
            "duration_unit": "t",
            "symbol": symbol
        }

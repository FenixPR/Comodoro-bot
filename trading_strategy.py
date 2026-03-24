import logging
import time
from typing import Optional, Dict, Any, List
from technical_analyzer import TechnicalAnalyzer

class TradingStrategy:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.tech_analyzer = TechnicalAnalyzer(rsi_period=14)

        self.initial_stake = float(self.config_manager.get('trading.stake_amount', 0.6))
        # Martingale fixo para recuperação, SEM dobrar descontroladamente
        self.martingale_multiplier = 3.5 
        self.max_recovery_attempts = 3 # Limite de tentativas de recuperação

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
        # TRAVA DE SEGURANÇA: Se estiver em pausa, o bot nem olha o gráfico
        if time.time() < self.global_pause_until:
            return None

        symbol = tick_data.get('symbol', 'Unknown')
        quote = float(tick_data.get('quote', 0))
        
        if symbol not in self.tick_histories:
            self.tick_histories[symbol] = []
        self.tick_histories[symbol].append(quote)
        
        if len(self.tick_histories[symbol]) > 50:
            self.tick_histories[symbol].pop(0)

        # ANÁLISE CUIDADOSA: Exige 30 ticks de dados novos após um Loss
        if len(self.tick_histories[symbol]) >= 30:
            analysis = self.tech_analyzer.analyze_trend(self.tick_histories[symbol])
            score = analysis.get("confianca_score", 0)
            
            # Só entra se o Sniper tiver Score 8 ou mais (Certeza alta)
            if score >= 8:
                # Se for Score 9 ou 10, usamos o stake dobrado (0.60 -> 1.20)
                operational_stake = self.current_stake
                if score >= 9:
                    operational_stake = round(self.current_stake * 2.0, 2)
                    self.logger.info(f"🚀 Score Máximo {score}! Entrada de confiança: ${operational_stake}")

                if analysis["status"] == "OVERBOUGHT":
                    return self._create_trade_signal("DIGITUNDER", symbol, 8, operational_stake)
                elif analysis["status"] == "OVERSOLD":
                    return self._create_trade_signal("DIGITOVER", symbol, 1, operational_stake)
        return None

    def on_trade_result(self, result: str):
        current_time = time.time()
        # Após qualquer resultado, limpa os dados para forçar nova análise cuidadosa
        self.tick_histories.clear()

        if result == "WIN":
            self.logger.info("--- [💰💰💰 WIN!] Recuperação completa ou lucro obtido. ---")
            self.global_pause_until = current_time + 45 # Pausa de 45s após Win
            self.reset()
        else:
            self.consecutive_losses += 1
            # PAUSA OBRIGATÓRIA DE 1 MINUTO APÓS LOSS
            self.logger.info(f"--- [😡 LOSS] Pausa de 60s. Analisando cuidadosamente a próxima... ---")
            self.global_pause_until = current_time + 60 
            
            if self.consecutive_losses <= self.max_recovery_attempts:
                # Martingale controlado
                self.current_stake = round(self.current_stake * self.martingale_multiplier, 2)
            else:
                self.logger.warning("Limite de segurança atingido. Resetando para evitar quebra da banca.")
                self.reset()

    def _create_trade_signal(self, contract_type, symbol, barrier, amount):
        return {"contract_type": contract_type, "amount": amount, "barrier": str(barrier),
                "duration": 1, "duration_unit": "t", "symbol": symbol}

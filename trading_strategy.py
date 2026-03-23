import logging
import time
from typing import Optional, Dict, Any, List
from technical_analyzer import TechnicalAnalyzer

class TradingStrategy:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Analisador técnico com RSI 14
        self.tech_analyzer = TechnicalAnalyzer(rsi_period=14)

        # Configurações de stake e martingale (3.5x conforme solicitado anteriormente)
        self.initial_stake = float(self.config_manager.get('trading.stake_amount', 0.6))
        self.martingale_multiplier = float(self.config_manager.get('trading.martingale_multiplier', 3.5))
        self.martingale_max_consecutive_losses = int(self.config_manager.get('trading.martingale_max_consecutive_losses', 5))

        self.current_stake = self.initial_stake
        self.consecutive_losses = 0
        
        self.tick_histories: Dict[str, List[float]] = {}
        self.max_history = 100
        self.global_pause_until = 0 

        self.reset()

    def reset(self):
        """Reseta o estado da estratégia."""
        self.logger.info("Estratégia redefinida para o estado inicial.")
        self.current_stake = self.initial_stake
        self.consecutive_losses = 0
        self.tick_histories.clear()

    def analyze_tick(self, tick_data: dict) -> Optional[Dict[str, Any]]:
        current_time = time.time()
        
        # Verifica pausa global
        if current_time < self.global_pause_until:
            return None

        symbol = tick_data.get('symbol', 'Unknown')
        try:
            if not tick_data or 'quote' not in tick_data:
                return None
            
            quote = float(tick_data['quote'])
            
            if symbol not in self.tick_histories:
                self.tick_histories[symbol] = []
                
            self.tick_histories[symbol].append(quote)
            
            if len(self.tick_histories[symbol]) > self.max_history:
                self.tick_histories[symbol].pop(0)

            # Análise Elaborada: Espera acumular 20 ticks novos
            if len(self.tick_histories[symbol]) >= 20:
                # Recebe a análise técnica robusta
                tech_analysis = self.tech_analyzer.analyze_trend(self.tick_histories[symbol])
                
                # --- NOVO: SISTEMA DE SCORE DE CONFIANÇA ---
                # tech_analysis agora deve retornar um dicionário com:
                # { "status": "OVERBOUGHT", "rsi": 75, "confianca_score": 8 }
                
                rsi_status = tech_analysis.get("status")
                # Score de 0 a 10 (calculado no TechnicalAnalyzer)
                confidence_score = tech_analysis.get("confianca_score", 0) 

                # Define o stake da operação baseado no Score
                operational_stake = self.current_stake
                
                # Se a confiança for ALTA (Score >= 8), DOBRA o valor da entrada
                if confidence_score >= 8:
                    operational_stake = round(self.current_stake * 2.0, 2)
                    self.logger.info(f"🚀 Alta Confiança (Score {confidence_score})! Entrada dobrada: ${operational_stake}")
                else:
                    self.logger.info(f"📊 Confiança Média (Score {confidence_score}). Entrada padrão: ${operational_stake}")

                if rsi_status == "OVERBOUGHT": # RSI alto, entra UNDER 8
                    return self._create_trade_signal("DIGITUNDER", symbol, 8, operational_stake)
                elif rsi_status == "OVERSOLD": # RSI baixo, entra OVER 1
                    return self._create_trade_signal("DIGITOVER", symbol, 1, operational_stake)

        except Exception as e:
            self.logger.error(f"Erro ao analisar tick [{symbol}]: {e}")
        
        return None

    def on_trade_result(self, result: str):
        """Atualiza o estado e aplica pausa de 1 minuto após Loss."""
        current_time = time.time()
        self.tick_histories.clear() # Força nova análise elaborada

        if result == "WIN":
            # O emoji de grana será alterado no TelegramBot
            self.logger.info("--- [💰 WIN] Resetando stake e aguardando 30s. ---")
            self.global_pause_until = current_time + 30
            self.reset()
        else: # LOSS
            self.consecutive_losses += 1
            self.logger.info(f"--- [😡 LOSS] Pausa de 60s para nova análise. ---")
            self.global_pause_until = current_time + 60 
            
            if self.consecutive_losses <= self.martingale_max_consecutive_losses:
                # Multiplicador de 3.5x (mantido da lógica anterior)
                self.current_stake = round(self.current_stake * self.martingale_multiplier, 2)
                self.logger.info(f"Modo Recuperação (Martingale 3.5x). Novo Stake Base: ${self.current_stake}")
            else:
                self.logger.warning("Limite Martingale atingido. Resetando por segurança.")
                self.global_pause_until = current_time + 300 
                self.reset()

    def _create_trade_signal(self, contract_type: str, symbol: str, barrier: Any, amount: float) -> Dict[str, Any]:
        return {
            "contract_type": contract_type,
            "amount": float(amount), # Usa o stake operacional (que pode ser dobrado)
            "barrier": str(barrier),
            "duration": 1,
            "duration_unit": "t",
            "symbol": symbol
                }

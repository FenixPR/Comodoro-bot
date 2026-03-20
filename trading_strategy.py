import logging
import time
from typing import Optional, Dict, Any, List
from technical_analyzer import TechnicalAnalyzer

class TradingStrategy:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        self.tech_analyzer = TechnicalAnalyzer(rsi_period=14)

        # Configurações carregadas do config/env
        self.initial_stake = float(self.config_manager.get('trading.stake_amount', 0.6))
        self.martingale_multiplier = float(self.config_manager.get('trading.martingale_multiplier', 3.5))
        self.martingale_max_consecutive_losses = int(self.config_manager.get('trading.martingale_max_consecutive_losses', 5))

        self.current_stake = self.initial_stake
        self.is_recovery_mode = False
        self.consecutive_losses = 0
        self.tick_histories: Dict[str, List[float]] = {}
        self.max_history = 100
        self.global_pause_until = 0 

        self.reset()

    def reset(self):
        """Reseta o estado da estratégia para o inicial."""
        self.logger.info("Estratégia redefinida para o valor inicial.")
        self.current_stake = self.initial_stake
        self.is_recovery_mode = False
        self.consecutive_losses = 0
        self.tick_histories.clear()

    def analyze_tick(self, tick_data: dict) -> Optional[Dict[str, Any]]:
        current_time = time.time()
        
        # Bloqueio de tempo (Pausa de 1 min ou pausa de 5 min)
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

            # Só opera se tiver acumulado 20 novos ticks (Análise Elaborada)
            if len(self.tick_histories[symbol]) >= 20:
                tech_analysis = self.tech_analyzer.analyze_trend(self.tick_histories[symbol])
                rsi_status = tech_analysis.get("status")
                
                if rsi_status == "OVERBOUGHT": 
                    return self._create_trade_signal("DIGITUNDER", symbol, 8)
                elif rsi_status == "OVERSOLD": 
                    return self._create_trade_signal("DIGITOVER", symbol, 1)

        except Exception as e:
            self.logger.error(f"Erro ao analisar tick [{symbol}]: {e}")
        
        return None

    def on_trade_result(self, result: str):
        """Aplica o Martingale de 3.5x e define a pausa de 1 minuto."""
        current_time = time.time()
        
        # Limpa histórico para forçar nova análise do zero
        self.tick_histories.clear()

        if result == "WIN":
            self.logger.info("--- [WIN] Sucesso! Pausa de 30s para novo cenário. ---")
            self.global_pause_until = current_time + 30
            self.reset()
            
        else: # LOSS
            self.consecutive_losses += 1
            # Pausa de 1 minuto conforme solicitado
            self.logger.info(f"--- [LOSS] Pausa de 60s para análise elaborada antes do Martingale. ---")
            self.global_pause_until = current_time + 60 
            
            if self.consecutive_losses <= self.martingale_max_consecutive_losses:
                # Aplica o multiplicador customizado (3.5)
                self.current_stake = round(self.current_stake * self.martingale_multiplier, 2)
                self.is_recovery_mode = True
                self.logger.info(f"Modo Recuperação Ativo. Novo Stake: ${self.current_stake}")
            else:
                self.logger.warning("Limite de Martingale atingido. Resetando por segurança.")
                self.global_pause_until = current_time + 300 
                self.reset()

    def _create_trade_signal(self, contract_type: str, symbol: str, barrier: Any) -> Dict[str, Any]:
        return {
            "contract_type": contract_type,
            "amount": float(self.current_stake),
            "barrier": str(barrier),
            "duration": 1,
            "duration_unit": "t",
            "symbol": symbol
        }

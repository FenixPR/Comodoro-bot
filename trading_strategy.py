import logging
import time
from typing import Optional, Dict, Any, List
from technical_analyzer import TechnicalAnalyzer

class TradingStrategy:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Inicializa apenas o analisador gráfico
        self.tech_analyzer = TechnicalAnalyzer(rsi_period=14)

        # Configurações de stake e martingale
        self.initial_stake = float(self.config_manager.get('trading.stake_amount', 0.6))
        self.martingale_multiplier = float(self.config_manager.get('trading.martingale_multiplier', 3.5))
        self.martingale_max_consecutive_losses = int(self.config_manager.get('trading.martingale_max_consecutive_losses', 5))

        # Variáveis de estado da estratégia
        self.current_stake = self.initial_stake
        self.is_recovery_mode = False
        self.consecutive_losses = 0
        
        # Histórico por ativo
        self.tick_histories: Dict[str, List[float]] = {}
        self.max_history = 100
        
        # --- NOVOS CONTROLES DE TEMPO E PAUSA ---
        self.global_pause_until = 0  # Trava global para todos os ativos

        self.reset()

    def reset(self):
        """Reseta o estado da estratégia."""
        self.logger.info("Estratégia redefinida para o estado inicial.")
        self.current_stake = self.initial_stake
        self.is_recovery_mode = False
        self.consecutive_losses = 0

    def analyze_tick(self, tick_data: dict) -> Optional[Dict[str, Any]]:
        current_time = time.time()
        
        # 1. Verifica se o bot está em pausa obrigatória (Global Cooldown)
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
            
            # Limita o tamanho do histórico na memória
            if len(self.tick_histories[symbol]) > self.max_history:
                self.tick_histories[symbol].pop(0)

            # Garante que temos dados suficientes (pelo menos 20 ticks novos)
            if len(self.tick_histories[symbol]) >= 20:
                
                tech_analysis = self.tech_analyzer.analyze_trend(self.tick_histories[symbol])
                rsi_status = tech_analysis.get("status")
                rsi_value = tech_analysis.get("rsi", 50)
                
                # --- LÓGICA DE ENTRADA BASEADA NO RSI ---
                if rsi_status == "OVERBOUGHT": # RSI >= 70
                    self.logger.info(f"[{symbol}] Oportunidade Encontrada! RSI: {rsi_value:.2f} (Sobrecomprado -> DIGITUNDER).")
                    return self._create_trade_signal("DIGITUNDER", symbol, 8)
                    
                elif rsi_status == "OVERSOLD": # RSI <= 30
                    self.logger.info(f"[{symbol}] Oportunidade Encontrada! RSI: {rsi_value:.2f} (Sobrevendido -> DIGITOVER).")
                    return self._create_trade_signal("DIGITOVER", symbol, 1)

        except Exception as e:
            self.logger.error(f"Erro ao analisar tick [{symbol}]: {e}")
        
        return None

    def on_trade_result(self, result: str):
        """Atualiza o estado após a operação com foco em análise elaborada."""
        current_time = time.time()
        
        # Limpa o histórico para forçar a coleta de novos dados (Análise Elaborada)
        # Isso obriga o bot a acumular pelo menos 20 novos ticks antes de agir.
        self.tick_histories.clear()

        if result == "WIN":
            self.logger.info("--- [WIN] Retornando ao stake inicial e aguardando 30s. ---")
            self.global_pause_until = current_time + 30
            self.reset() # Reseta stake e perdas
            
        else: # LOSS
            self.consecutive_losses += 1
            # Define a pausa de 1 minuto conforme solicitado
            self.logger.info(f"--- [LOSS] Pausa de 60s para nova análise do mercado. ---")
            self.global_pause_until = current_time + 60 
            
            if self.consecutive_losses <= self.martingale_max_consecutive_losses:
                # Aplica o multiplicador configurado (ex: 3.5x) em vez de dobrar 
                new_stake = self.current_stake * self.martingale_multiplier
                self.current_stake = round(new_stake, 2)
                self.is_recovery_mode = True
                self.logger.info(f"Modo Recuperação: Novo Stake: ${self.current_stake}")
            else:
                self.logger.warning("Limite de Martingale atingido. Resetando para proteger banca.")
                self.global_pause_until = current_time + 300 # Pausa maior de 5min após estourar
                self.reset()

    def _create_trade_signal(self, contract_type: str, symbol: str, barrier: Any) -> Dict[str, Any]:
        return {
            "contract_type": contract_type,
            "amount": round(float(self.current_stake), 2),
            "barrier": str(barrier),
            "duration": 1,
            "duration_unit": "t",
            "symbol": symbol
        }
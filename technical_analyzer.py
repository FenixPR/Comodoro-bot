import logging

class TechnicalAnalyzer:
    def __init__(self, rsi_period=14):
        self.logger = logging.getLogger(__name__)
        self.rsi_period = rsi_period

    def calculate_rsi(self, prices):
        """
        Calcula o RSI (Relative Strength Index) baseado numa lista de preços.
        """
        if len(prices) < self.rsi_period + 1:
            return None
        
        # Calcula as diferenças de preço entre ticks consecutivos
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        # Média de ganhos e perdas
        avg_gain = sum(gains[-self.rsi_period:]) / self.rsi_period
        avg_loss = sum(losses[-self.rsi_period:]) / self.rsi_period

        if avg_loss == 0:
            return 100.0 # Se não houver perdas, RSI é 100 (força compradora máxima)
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi

    def analyze_trend(self, prices):
        """
        Retorna uma análise baseada nos indicadores gráficos.
        """
        rsi = self.calculate_rsi(prices)
        
        if rsi is None:
            return {"status": "WAIT", "reason": "Dados insuficientes para RSI"}

        self.logger.info(f"Análise Gráfica - RSI Atual: {rsi:.2f}")

        # Regras de filtro baseadas no RSI
        if rsi >= 70:
            return {"status": "OVERBOUGHT", "rsi": rsi, "reason": "Mercado sobrecomprado (Risco de queda)"}
        elif rsi <= 30:
            return {"status": "OVERSOLD", "rsi": rsi, "reason": "Mercado sobrevendido (Risco de alta)"}
        else:
            return {"status": "NEUTRAL", "rsi": rsi, "reason": "Mercado neutro"}
import logging

class TechnicalAnalyzer:
    def __init__(self, rsi_period=14):
        self.logger = logging.getLogger(__name__)
        self.rsi_period = rsi_period

    def calculate_rsi(self, prices):
        """Calcula o RSI baseado em uma lista de preços."""
        if len(prices) < self.rsi_period + 1:
            return None
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        avg_gain = sum(gains[-self.rsi_period:]) / self.rsi_period
        avg_loss = sum(losses[-self.rsi_period:]) / self.rsi_period

        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def analyze_trend(self, prices):
        """
        Retorna análise detalhada com Score de Confiança (0 a 10).
        Baseado na exaustão do RSI e na persistência da tendência.
        """
        rsi = self.calculate_rsi(prices)
        if rsi is None:
            return {"status": "WAIT", "reason": "Dados insuficientes", "confianca_score": 0}

        score = 0
        status = "NEUTRAL"

        # --- LÓGICA DE SCORE PARA SOBRECOMPRA (DIGITUNDER) ---
        if rsi >= 70:
            status = "OVERBOUGHT"
            score = 6 # Score base para RSI > 70
            if rsi >= 80: score += 2 # Bônus de exaustão extrema
            if rsi >= 90: score += 2 # "Certeza" estatística máxima
            
        # --- LÓGICA DE SCORE PARA SOBREVENDA (DIGITOVER) ---
        elif rsi <= 30:
            status = "OVERSOLD"
            score = 6 # Score base para RSI < 30
            if rsi <= 20: score += 2 # Bônus de exaustão extrema
            if rsi <= 10: score += 2 # "Certeza" estatística máxima

        # Filtro de tendência: Se os últimos 5 ticks confirmam a direção, +1 no score
        if len(prices) >= 5:
            last_ticks = prices[-5:]
            if status == "OVERBOUGHT" and all(last_ticks[i] >= last_ticks[i-1] for i in range(1, 5)):
                score = min(10, score + 1) # Tendência de alta forte confirmada
            elif status == "OVERSOLD" and all(last_ticks[i] <= last_ticks[i-1] for i in range(1, 5)):
                score = min(10, score + 1) # Tendência de queda forte confirmada

        self.logger.info(f"Análise: RSI {rsi:.2f} | Status: {status} | Score: {score}/10")
        
        return {
            "status": status,
            "rsi": rsi,
            "confianca_score": score,
            "reason": f"Mercado {status} com confiança {score}"
        }

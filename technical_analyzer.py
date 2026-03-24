import logging

class TechnicalAnalyzer:
    def __init__(self, rsi_period=14):
        self.logger = logging.getLogger(__name__)
        self.rsi_period = rsi_period

    def calculate_rsi(self, prices):
        if len(prices) < self.rsi_period + 1: return None
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        avg_gain = sum(gains[-self.rsi_period:]) / self.rsi_period
        avg_loss = sum(losses[-self.rsi_period:]) / self.rsi_period
        if avg_loss == 0: return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def analyze_trend(self, prices):
        """Lógica Xeque-Mate: Exaustão absoluta e Score de Confiança."""
        rsi = self.calculate_rsi(prices)
        if rsi is None: return {"status": "WAIT", "confianca_score": 0}
        
        score = 0
        status = "NEUTRAL"

        # --- FILTRO XEQUE-MATE (Níveis de elite 85/15) ---
        if rsi >= 85: 
            status = "OVERBOUGHT"
            score = 7 
            if rsi >= 90: score += 2 
            if rsi >= 94: score += 1
        elif rsi <= 15:
            status = "OVERSOLD"
            score = 7
            if rsi <= 10: score += 2
            if rsi <= 6: score += 1

        # Filtro de Calma: Verifica se o preço lateralizou no topo/fundo
        if len(prices) >= 4:
            # Se o último tick já começou a voltar, a certeza aumenta
            if status == "OVERBOUGHT" and prices[-1] < prices[-2]: score = min(10, score + 1)
            elif status == "OVERSOLD" and prices[-1] > prices[-2]: score = min(10, score + 1)

        if score < 8: status = "NEUTRAL" # Sniper só opera com Score 8+

        return {"status": status, "rsi": rsi, "confianca_score": score}

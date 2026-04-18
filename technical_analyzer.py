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

        if avg_loss == 0: return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def analyze_trend(self, prices):
        """Lógica Sniper: Filtra apenas entradas de altíssima probabilidade."""
        rsi = self.calculate_rsi(prices)
        if rsi is None:
            return {"status": "WAIT", "confianca_score": 0}

        score = 0
        status = "NEUTRAL"

        # FILTRO SNIPER ULTRA: Níveis extremos (88/12) para máxima assertividade
        if rsi >= 88: 
            status = "OVERBOUGHT"
            score = 8 # Score base aumentado para Sniper Ultra
            if rsi >= 92: score += 1 # Exaustão severa
            if rsi >= 96: score += 1 # "Certeza" estatística máxima
            
        elif rsi <= 12:
            status = "OVERSOLD"
            score = 8
            if rsi <= 8: score += 1
            if rsi <= 4: score += 1

        # Validação de micro-tendência (os últimos 5 ticks devem confirmar a exaustão)
        if len(prices) >= 5:
            if status == "OVERBOUGHT" and all(prices[i] > prices[i-1] for i in range(-4, 0)):
                score = min(10, score + 1)
            elif status == "OVERSOLD" and all(prices[i] < prices[i-1] for i in range(-4, 0)):
                score = min(10, score + 1)

        # Se o score for menor que 7, o Sniper não atira
        if score < 7: status = "NEUTRAL"

        return {
            "status": status,
            "rsi": rsi,
            "confianca_score": score,
            "reason": f"Sniper Mode: {status} (Score {score})"
        }

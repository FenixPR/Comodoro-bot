import logging
import statistics  # nativo do Python

class TechnicalAnalyzer:
    def __init__(self, rsi_period=14):
        self.logger = logging.getLogger(__name__)
        self.rsi_period = rsi_period

    def calculate_rsi(self, prices):
        """RSI com método Wilder (smoothing correto) + usa TODOS os ticks disponíveis"""
        if len(prices) < self.rsi_period + 1:
            return None

        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        # Primeiro average (SMA)
        avg_gain = sum(gains[:self.rsi_period]) / self.rsi_period
        avg_loss = sum(losses[:self.rsi_period]) / self.rsi_period

        # Smoothing Wilder para o restante dos ticks
        for i in range(self.rsi_period, len(deltas)):
            avg_gain = (avg_gain * (self.rsi_period - 1) + gains[i]) / self.rsi_period
            avg_loss = (avg_loss * (self.rsi_period - 1) + losses[i]) / self.rsi_period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def analyze_trend(self, prices):
        """Análise Xeque-Mate ULTRA ROBUSTA – só dá sinal com CERTEZA ALTA"""
        rsi = self.calculate_rsi(prices)
        if rsi is None:
            return {"status": "WAIT", "confianca_score": 0}

        score = 0
        status = "NEUTRAL"

        # === NÍVEIS EXTREMOS (mais exigentes) ===
        if rsi >= 88:
            status = "OVERBOUGHT"
            score = 8
            if rsi >= 92: score += 1
            if rsi >= 95: score += 1
        elif rsi <= 12:
            status = "OVERSOLD"
            score = 8
            if rsi <= 8: score += 1
            if rsi <= 5: score += 1

        # === CONFLUÊNCIAS FORTES PARA CERTEZA DE WIN ===
        if len(prices) >= 6:
            # Reversal forte (últimos 3 ticks já voltando)
            if status == "OVERBOUGHT" and prices[-1] < prices[-2] < prices[-3]:
                score += 2
            elif status == "OVERSOLD" and prices[-1] > prices[-2] > prices[-3]:
                score += 2

            # Momentum consistente (sem ruído)
            last_5 = prices[-5:]
            if statistics.stdev(last_5) < 0.5:  # mercado calmo demais = risco
                score -= 1

        # Score máximo = 10 (só opera com 9.5+)
        score = min(10, score)

        if score < 9.5:
            status = "NEUTRAL"  # NADA de trade com dúvida

        return {
            "status": status,
            "rsi": round(rsi, 2),
            "confianca_score": score
        }

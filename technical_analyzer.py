import logging
import statistics
from collections import defaultdict
import time
from datetime import datetime

class TechnicalAnalyzer:
    def __init__(self, rsi_period=14, bb_period=20, macd_fast=12, macd_slow=26, macd_signal=9, stoch_period=14):
        self.logger = logging.getLogger(__name__)
        self.rsi_period = rsi_period
        self.bb_period = bb_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.stoch_period = stoch_period

        # Histórico de dígitos por símbolo
        self.digit_histories: dict = defaultdict(list)

    def get_last_digit(self, quote: float) -> int:
        """Padrão oficial Deriv: último dígito do preço do tick"""
        return int(quote) % 10

    def calculate_rsi(self, prices):
        if len(prices) < self.rsi_period + 1:
            return None
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        avg_gain = sum(gains[:self.rsi_period]) / self.rsi_period
        avg_loss = sum(losses[:self.rsi_period]) / self.rsi_period

        for i in range(self.rsi_period, len(deltas)):
            avg_gain = (avg_gain * (self.rsi_period - 1) + gains[i]) / self.rsi_period
            avg_loss = (avg_loss * (self.rsi_period - 1) + losses[i]) / self.rsi_period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def calculate_bollinger(self, prices):
        if len(prices) < self.bb_period:
            return None
        sma = sum(prices[-self.bb_period:]) / self.bb_period
        std = statistics.stdev(prices[-self.bb_period:])
        return {
            'upper': sma + 2 * std,
            'middle': sma,
            'lower': sma - 2 * std,
            'price': prices[-1]
        }

    def calculate_macd(self, prices):
        if len(prices) < self.macd_slow:
            return None

        def ema(data, period):
            multiplier = 2 / (period + 1)
            ema_val = data[0]
            emas = [ema_val]
            for price in data[1:]:
                ema_val = price * multiplier + ema_val * (1 - multiplier)
                emas.append(ema_val)
            return emas

        fast_ema = ema(prices, self.macd_fast)
        slow_ema = ema(prices, self.macd_slow)
        macd_line = [f - s for f, s in zip(fast_ema, slow_ema)]
        signal_line = ema(macd_line, self.macd_signal)
        histogram = macd_line[-1] - signal_line[-1]
        return {'histogram': histogram, 'trend': 'bear' if histogram < 0 else 'bull' if histogram > 0 else 'flat'}

    def calculate_stochastic(self, prices):
        if len(prices) < self.stoch_period:
            return None
        recent = prices[-self.stoch_period:]
        highest = max(recent)
        lowest = min(recent)
        k = 100 * (prices[-1] - lowest) / (highest - lowest) if highest != lowest else 50
        return {'k': round(k, 2), 'overbought': k > 80, 'oversold': k < 20}

    def analyze_digit_pattern(self, symbol, last_digit):
        self.digit_histories[symbol].append(last_digit)
        if len(self.digit_histories[symbol]) > 60:
            self.digit_histories[symbol] = self.digit_histories[symbol][-60:]

        hist = self.digit_histories[symbol]
        if len(hist) < 30:
            return {"score": 0}

        freq = [hist.count(d) for d in range(10)]
        total = len(hist)
        high_digits = sum(freq[7:]) / total   # 7,8,9
        low_digits = sum(freq[0:3]) / total    # 0,1,2

        # Favorável para DIGITUNDER (barrier 8 → espera dígito baixo)
        under_bias = 1 if high_digits > 0.35 else 0
        # Favorável para DIGITOVER (barrier 1 → espera dígito alto)
        over_bias = 1 if low_digits > 0.35 else 0

        # Dígito frio (apareceu pouco)
        cold_digit_score = 1 if freq[last_digit] < total * 0.07 else 0

        return {
            "under_bias": under_bias,
            "over_bias": over_bias,
            "cold_digit": cold_digit_score,
            "score": under_bias + over_bias + cold_digit_score
        }

    def analyze_trend(self, symbol, prices, quote):
        if len(prices) < 60:
            return {"status": "WAIT", "confianca_score": 0, "confluences": 0}

        rsi = self.calculate_rsi(prices)
        bb = self.calculate_bollinger(prices)
        macd = self.calculate_macd(prices)
        stoch = self.calculate_stochastic(prices)
        digit = self.analyze_digit_pattern(symbol, self.get_last_digit(quote))

        if None in (rsi, bb, macd, stoch):
            return {"status": "WAIT", "confianca_score": 0, "confluences": 0}

        # Filtro de volatilidade (regime de mercado)
        vol = statistics.stdev(prices[-30:])
        if vol > 8.0 or vol < 0.3:  # muito volátil ou muito flat
            return {"status": "WAIT", "confianca_score": 0, "confluences": 0}

        score = 0
        confluences = 0
        status = "NEUTRAL"

        # === OVERBOUGHT (DIGITUNDER) ===
        if rsi >= 88 and stoch['overbought'] and prices[-1] >= bb['upper'] * 0.98 and macd['trend'] == 'bear':
            status = "OVERBOUGHT"
            score += 4
            confluences += 3
            if digit["under_bias"]:
                confluences += 1
                score += 2

        # === OVERSOLD (DIGITOVER) ===
        elif rsi <= 12 and stoch['oversold'] and prices[-1] <= bb['lower'] * 1.02 and macd['trend'] == 'bull':
            status = "OVERSOLD"
            score += 4
            confluences += 3
            if digit["over_bias"]:
                confluences += 1
                score += 2

        # Confluência extra de dígito frio
        if digit["cold_digit"]:
            confluences += 1
            score += 1

        # Requer mínimo 4 confluências + score alto
        if confluences < 4 or score < 9.5:
            status = "NEUTRAL"

        return {
            "status": status,
            "rsi": round(rsi, 2),
            "confianca_score": min(10, score),
            "confluences": confluences,
            "volatility": round(vol, 2)
        }

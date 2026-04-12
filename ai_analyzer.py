import logging
import json
import os
import requests
from typing import List, Optional, Dict

class AIAnalyzer:
    def __init__(self, config_manager):
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self.api_key = self.config_manager.get("ai.openai_api_key")
        base_url_env = self.config_manager.get("ai.openai_base_url", "https://api.openai.com/v1")
        self.base_url = f"{base_url_env.rstrip("/")}/chat/completions"
        self.model = self.config_manager.get("ai.model", "gemini-2.5-flash")

    def analyze_market(self, ticks: List[float], symbol: str) -> Optional[Dict]:
        """
        Análise probabilística profunda para evitar LOSS.
        """
        if not self.api_key:
            self.logger.warning("OPENAI_API_KEY não configurada. IA desativada.")
            return None

        # Extrair os últimos dígitos dos preços
        digits = []
        for t in ticks:
            # Formata para garantir que temos o último dígito decimal
            s = f"{t:.5f}".rstrip("0").rstrip(".")
            if s:
                digits.append(int(s[-1]))
            else:
                digits.append(0)
        
        recent_digits = digits[-50:]
        
        # Prompt focado 100% em EVITAR LOSS e PROBABILIDADE
        prompt = f"""
        ANÁLISE DE RISCO PARA TRADING DE DÍGITOS (ATIVO: {symbol})
        
        DADOS RECENTES (Últimos 50 dígitos): {recent_digits}
        
        Sua missão é atuar como um atuário de seguros: seu objetivo NÃO é apenas ganhar, mas NÃO PERDER.
        
        REGRAS DE OURO:
        1. Identifique o dígito "frio" (que menos apareceu) e o "quente" (que mais apareceu).
        2. Para DIGIT UNDER: A barreira deve ser um número que tenha baixíssima probabilidade de ser atingido nos próximos 1-2 ticks.
        3. Para DIGIT OVER: A barreira deve ser um número que o mercado já superou com frequência nos últimos ticks.
        4. Se houver qualquer incerteza ou padrão de reversão, recomende 'WAIT'.
        
        Responda ESTRITAMENTE em JSON:
        {{
            "recommendation": "UNDER" | "OVER" | "WAIT",
            "barrier": 0-9,
            "confidence": 0.0-1.0,
            "analysis_summary": "Explique por que esta entrada evita o loss baseando-se nos 50 dígitos fornecidos"
        }}
        """

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Você é uma IA de alta precisão para análise probabilística de mercado financeiro."},
                {"role": "user", "content": prompt}
            ]
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            content = data["choices"][0]["message"]["content"]
            # Limpeza básica de Markdown se a IA retornar blocos de código
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            
            # Log detalhado da decisão da IA
            self.logger.info(f"--- ANÁLISE IA [{symbol}] ---")
            self.logger.info(f"Decisão: {result.get("recommendation")} | Confiança: {float(result.get("confidence", 0))*100:.1f}%")
            self.logger.info(f"Motivo: {result.get("analysis_summary", "N/A")}")
            
            return result
        except Exception as e:
            self.logger.error(f"Erro na análise de IA para {symbol}: {e}")
            return None

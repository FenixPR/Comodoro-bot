import unittest
import logging
from unittest.mock import MagicMock

# Mock para ConfigManager
class MockConfigManager:
    def __init__(self, config_data):
        self.config_data = config_data

    def get(self, key_path, default=None):
        keys = key_path.split(".")
        value = self.config_data
        for key in keys:
            value = value.get(key, {})
        if isinstance(value, dict) and not value:
            return default
        return value

# Importar a classe TradingStrategy do arquivo modificado
# Para fins de teste, vamos simular a importação ou copiar o código relevante
# Assumindo que trading_strategy.py está no mesmo diretório ou acessível

# Copie a classe TradingStrategy modificada aqui para garantir que estamos testando a versão correta
class TradingStrategy:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)

        # Carrega os parâmetros da configuração
        self.initial_stake = float(self.config_manager.get('trading.stake_amount', 0.6))
        self.martingale_multiplier = float(self.config_manager.get('trading.martingale_multiplier', 3.5))
        self.martingale_max_consecutive_losses = int(self.config_manager.get('trading.martingale_max_consecutive_losses', 5))

        # Variáveis de estado da estratégia - inicializadas aqui e no reset
        self.current_stake = self.initial_stake
        self.current_prediction = 8
        self.is_recovery_mode = False
        self.consecutive_losses = 0
        self.reset() # Garante que o estado inicial está definido corretamente

    def reset(self):
        """Reseta o estado da estratégia para os valores iniciais."""
        self.logger.info("A redefinir a estratégia para o estado inicial.")
        self.current_stake = self.initial_stake
        self.current_prediction = 8
        self.is_recovery_mode = False
        self.consecutive_losses = 0

    def analyze_tick(self, tick_data: dict) -> dict:
        # Não precisamos testar analyze_tick para esta validação
        pass

    def on_trade_result(self, result: str):
        """Atualiza o estado da estratégia com base no resultado da operação."""
        if result == "WIN":
            self.logger.info("Resultado: WIN. A redefinir para o estado inicial.")
            self.reset() # Chama a função de reset
        else: # LOSS
            self.logger.info("Resultado: LOSS. A ativar o modo de recuperação (Martingale).")
            self.consecutive_losses += 1
            if self.consecutive_losses <= self.martingale_max_consecutive_losses:
                self.current_stake *= self.martingale_multiplier
                self.current_prediction = 2
                self.is_recovery_mode = True
            else:
                self.logger.warning(f"Martingale atingiu o limite de {self.martingale_max_consecutive_losses} perdas consecutivas. A redefinir para o estado inicial.")
                self.reset()
        
        self.logger.info(f"Perdas consecutivas: {self.consecutive_losses}")
        self.logger.info(f"Próxima aposta: ${self.current_stake:.2f}, Próxima previsão: {self.current_prediction}")

    def _create_trade_signal(self, contract_type: str) -> dict:
        # Não precisamos testar _create_trade_signal para esta validação
        pass


class TestMartingaleStrategy(unittest.TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL) # Desabilita logs durante os testes
        self.config_data = {
            "trading": {
                "stake_amount": 1.0,
                "martingale_multiplier": 2.0,
                "martingale_max_consecutive_losses": 3
            }
        }
        self.config_manager = MockConfigManager(self.config_data)
        self.strategy = TradingStrategy(self.config_manager)

    def test_initial_state(self):
        self.assertEqual(self.strategy.current_stake, 1.0)
        self.assertFalse(self.strategy.is_recovery_mode)
        self.assertEqual(self.strategy.consecutive_losses, 0)

    def test_win_resets_state(self):
        self.strategy.on_trade_result("LOSS")
        self.strategy.on_trade_result("WIN")
        self.assertEqual(self.strategy.current_stake, 1.0)
        self.assertFalse(self.strategy.is_recovery_mode)
        self.assertEqual(self.strategy.consecutive_losses, 0)

    def test_single_loss(self):
        self.strategy.on_trade_result("LOSS")
        self.assertEqual(self.strategy.consecutive_losses, 1)
        self.assertEqual(self.strategy.current_stake, 1.0 * 2.0) # initial_stake * martingale_multiplier
        self.assertTrue(self.strategy.is_recovery_mode)

    def test_multiple_losses_within_limit(self):
        self.strategy.on_trade_result("LOSS") # 1st loss
        self.assertEqual(self.strategy.consecutive_losses, 1)
        self.assertEqual(self.strategy.current_stake, 2.0)

        self.strategy.on_trade_result("LOSS") # 2nd loss
        self.assertEqual(self.strategy.consecutive_losses, 2)
        self.assertEqual(self.strategy.current_stake, 2.0 * 2.0)

        self.strategy.on_trade_result("LOSS") # 3rd loss
        self.assertEqual(self.strategy.consecutive_losses, 3)
        self.assertEqual(self.strategy.current_stake, 4.0 * 2.0)
        self.assertTrue(self.strategy.is_recovery_mode)

    def test_losses_exceed_limit(self):
        self.strategy.on_trade_result("LOSS") # 1st loss
        self.strategy.on_trade_result("LOSS") # 2nd loss
        self.strategy.on_trade_result("LOSS") # 3rd loss
        self.assertEqual(self.strategy.consecutive_losses, 3)
        self.assertEqual(self.strategy.current_stake, 8.0)
        self.assertTrue(self.strategy.is_recovery_mode)

        self.strategy.on_trade_result("LOSS") # 4th loss (exceeds limit)
        self.assertEqual(self.strategy.consecutive_losses, 0) # Should reset
        self.assertEqual(self.strategy.current_stake, 1.0) # Should reset to initial stake
        self.assertFalse(self.strategy.is_recovery_mode) # Should reset

    def test_win_after_losses(self):
        self.strategy.on_trade_result("LOSS")
        self.strategy.on_trade_result("LOSS")
        self.strategy.on_trade_result("WIN")
        self.assertEqual(self.strategy.consecutive_losses, 0)
        self.assertEqual(self.strategy.current_stake, 1.0)
        self.assertFalse(self.strategy.is_recovery_mode)

if __name__ == '__main__':
    unittest.main()


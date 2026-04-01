# Guia de Implantação no Render - Comodoro Bot

Para rodar este bot no Render com sucesso, siga estes passos:

## 1. Configuração do Web Service
No painel do Render, crie um novo **Web Service** e conecte seu repositório GitHub.

## 2. Configurações de Build e Start
- **Runtime:** `Python 3`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python main.py` (ou use o `Procfile` que já incluí)

## 3. Variáveis de Ambiente (Environment Variables)
Adicione as seguintes variáveis no painel do Render para que o bot funcione:

| Variável | Descrição |
| :--- | :--- |
| `PORT` | 10000 (O Render geralmente define isso automaticamente) |
| `DERIV_APP_ID` | Seu App ID da Deriv |
| `DERIV_API_TOKEN` | Seu API Token da Deriv |
| `TELEGRAM_BOT_TOKEN` | O Token do seu Bot do Telegram |
| `TELEGRAM_CHAT_ID` | Seu Chat ID do Telegram |

## 4. Alterações Realizadas
- **Correção de Sintaxe:** Corrigido erro no `bot_config.json` e f-strings no `ai_analyzer.py`.
- **Comandos Telegram:** Agora os comandos `/set_profit` e `/set_loss` funcionam e alteram a meta em tempo real.
- **Gerenciamento de Risco:** O bot agora respeita a meta de lucro diária e o stop loss configurado.
- **Compatibilidade Render:** Adicionado `Procfile` e garantido que o servidor Flask use a porta correta.

---
**Nota:** O arquivo `bot_config.json` serve como fallback, mas as Variáveis de Ambiente no Render têm prioridade.

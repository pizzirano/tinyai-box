# TinyAI Box

Caixa de IA local rodando em uma **TV Box ARMv7** (Armbian/Debian, 1–4GB RAM). Fala por voz (Whisper → LLM → Piper), responde prompts pequenos com **TinyLlama** local e delega prompts complexos ao **OpenRouter**. Tudo sobe com um único comando.

```
Scheduler → Docker → Voice → OTA → Network
```

## Início rápido

```bash
git clone <seu-repo> && cd tinyai-box
cp .env.example .env          # preencha OPENROUTER_API_KEY (opcional)
docker compose up -d
```

Baixe o modelo GGUF (uma vez) — instruções em `docs/modulos/ai.md`.

Teste:

```bash
curl http://localhost:8000/saude
curl -X POST http://localhost:8000/prompt \
  -H 'Content-Type: application/json' \
  -d '{"texto": "oi, tudo bem?"}'
```

Resposta inclui a rota escolhida e o motivo:

```json
{"resposta": "...", "rota": "llm_local", "motivo": "prompt pequeno e hardware dentro dos limites"}
```

Voz: `POST /voz` com o campo multipart `audio` (WAV) devolve WAV sintetizado pelo Piper.

## Estrutura

```
scheduler/            # cérebro em Python (FastAPI)
  scheduler/rotas.py       # decisão de rota — funções puras, testáveis
  scheduler/adaptadores.py # Whisper, llama.cpp, Piper, OpenRouter
  scheduler/hardware.py    # RAM/CPU/temperatura via /proc e /sys
  scheduler/api.py         # endpoints /prompt, /voz, /saude
  tests/                   # 13 testes das regras de decisão
docker-compose.yml    # sobe tudo: scheduler, llm, whisper, piper, watchtower (OTA)
systemd/              # units para boot automático + timer de monitoramento
scripts/monitor.sh    # diagnóstico de recursos com thresholds e alertas
docs/                 # MkDocs: arquitetura (Mermaid), módulos, ADRs
.github/workflows/    # CI: testes + build multi-arch linux/arm/v7 → GHCR
```

## Como o Scheduler decide

| Entrada | Rota |
|---|---|
| Áudio | Whisper → LLM → Piper |
| Texto pequeno + hardware saudável (RAM ≥ 500MB, CPU < 90%, temp < 75°C) | TinyLlama local |
| Texto complexo ou hardware pressionado | OpenRouter |
| Falha do modelo local | Fallback automático → OpenRouter |

Cada decisão vira log JSON (rota, motivo, latência, fallback).

## Instalar na TV Box (boot automático)

```bash
sudo cp -r . /opt/tinyai-box
sudo cp systemd/* /etc/systemd/system/   # apenas .service e .timer
sudo systemctl daemon-reload
sudo systemctl enable --now tinyai.service tinyai-monitor.timer
```

## Desenvolvimento

```bash
cd scheduler
pip install -r requirements.txt pytest
python -m pytest tests/ -v        # 13 passed
uvicorn scheduler.api:app --reload
```

Documentação completa: `pip install mkdocs-material && mkdocs serve`

## Decisões de arquitetura

- **ADR-001** — camadas simples com Scheduler central único
- **ADR-002** — roteamento por heurística barata + estado real do hardware
- **ADR-003** — OTA via Watchtower (1x/dia, rollback fixando tag)

Detalhes em `docs/adr/`.

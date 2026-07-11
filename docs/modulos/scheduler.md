# Módulo: Scheduler

Serviço FastAPI (porta 8000) que roteia cada requisição.

- `scheduler/rotas.py` — funções **puras** de decisão (`escolher_rota`), sem I/O.
- `scheduler/adaptadores.py` — chamadas HTTP a Whisper, llama.cpp, Piper e OpenRouter. Credenciais só via variáveis de ambiente.
- `scheduler/hardware.py` — lê RAM/CPU/temperatura de `/proc` e `/sys`.
- `scheduler/api.py` — endpoints `POST /prompt`, `POST /voz`, `GET /saude`.

Testes: `cd scheduler && python -m pytest tests/` (13 casos cobrindo heurística, limites de hardware e fallback).

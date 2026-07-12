# TinyAI Box

Caixa de IA local rodando em uma **TV Box ARMv7** (Armbian/Debian, ~1GB RAM útil). Fala por voz (STT → LLM → TTS), responde prompts pequenos com um modelo local (**Qwen2.5-0.5B** via llama.cpp) e delega prompts complexos ao **OpenRouter**.

```
Scheduler (Docker) → LLM / TTS / STT (nativos, systemd) → OTA → Network
```

> **⚠️ Nota importante sobre esta implantação:** o kernel desta TV box
> específica (`armv7`, vendor Rockchip) **não inclui o módulo `veth`**,
> exigido pela rede *bridge* padrão do Docker — tanto para build
> (`apt-get`, `wget` dentro de `RUN`) quanto para comunicação entre
> containers em runtime. Isso quebra o `docker compose up -d --build`
> multi-container original. A arquitetura foi adaptada (ver seção
> "Por que mudamos" abaixo). Se seu hardware tiver `veth` disponível, o
> compose multi-container original volta a funcionar normalmente.

## Por que mudamos de estratégia

O plano original rodava **todos** os serviços (scheduler, llm, whisper,
piper, watchtower) como containers Docker, orquestrados por
`docker compose up -d --build`. Isso quebrou em cascata:

1. **`rhasspy/wyoming-piper:latest` não publica manifest para `linux/arm/v7`**
   — a imagem simplesmente não existe para ARM 32-bit.
2. Ao tentar contornar isso compilando localmente (`build:` no compose para
   `llm`, `whisper`, `scheduler`), todo `RUN apt-get install` dentro dos
   Dockerfiles falhava com:
   ```
   failed to create endpoint ... failed to add the host (vethXXXX) <=> sandbox
   (vethYYYY) pair interfaces: operation not supported
   ```
   Isso confirmou que o **kernel não tem o módulo `veth`** — sem ele, o
   Docker não consegue criar a rede virtual necessária nem para builds
   (que precisam de acesso à internet) nem para rodar containers em
   bridge normal.
3. `docker compose build` usa BuildKit/bake por padrão, que **não respeita**
   `--network host` do jeito esperado nesse cenário. A saída foi buildar
   manualmente com o builder legado:
   ```bash
   DOCKER_BUILDKIT=0 docker build --network host -t tinyai/scheduler:latest ./scheduler
   ```
   Isso funciona porque `--network host` no build clássico reusa a pilha de
   rede do host diretamente, sem precisar criar par `veth` nenhum.

**Decisão final:** os serviços de IA pesados (TTS, LLM, STT) saíram do
Docker e passaram a rodar **nativos no host via `systemd`**, usando
binários e modelos que já podiam ser compilados/instalados diretamente na
TV box. Só o `scheduler` (API leve em FastAPI) e o `watchtower` continuam
em container — ambos em `network_mode: host`, para conseguirem falar com
os serviços nativos via `localhost` sem depender de rede bridge nenhuma.

## Arquitetura atual

| Serviço | Onde roda | Porta | Engine |
|---|---|---|---|
| Scheduler (API) | Docker, `network_mode: host` | 8000 | FastAPI/uvicorn |
| LLM local | nativo, `systemd` (`tinyai-llm.service`) | 8080 | `llama-server` (llama.cpp compilado nativo) |
| TTS (Piper) | nativo, `systemd` (`tinyai-piper.service`) | 5000 | binário `piper` armv7 + wrapper Flask |
| STT | nativo, `systemd` (`tinyai-stt.service`) | 9000 | `vosk` (Python) + `vosk-model-small-pt-0.3` |
| Watchtower (OTA) | Docker, `network_mode: host` | — | atualização automática de imagens 1x/dia |

O contrato HTTP entre o scheduler e cada serviço nativo é o mesmo que já
existia em `scheduler/scheduler/adaptadores.py` (POST `/completion`, POST
`/api/tts`, POST `/inference`) — só o *transporte* mudou, de
`http://<nome-do-container>:<porta>` para `http://localhost:<porta>`.

## Início rápido (neste hardware)

```bash
git clone <seu-repo> && cd tinyai-box
cp .env.example .env          # preencha OPENROUTER_API_KEY (opcional)
```

### 1. Serviços nativos (LLM, TTS, STT)

Cada um roda em seu próprio venv Python (ou binário direto) como serviço
`systemd`. Unidades de referência ficam em `systemd/tinyai-piper.service`,
`systemd/tinyai-llm.service` e `systemd/tinyai-stt.service`:

```bash
sudo cp systemd/tinyai-piper.service systemd/tinyai-llm.service systemd/tinyai-stt.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tinyai-piper.service tinyai-llm.service tinyai-stt.service
```

Ajuste os caminhos (`ExecStart`, `WorkingDirectory`) em cada `.service` para
onde estiverem o binário do Piper, o modelo de voz, o `llama-server` e o
modelo GGUF no seu ambiente.

O `llama-server` roda com `-np 1` (um único slot, para não dividir os 512
tokens de contexto entre slots que nunca serão usados em paralelo nesse
hardware) e o governor de CPU é fixado em `performance` via
`cpu-performance.service` (ver seção de tuning).

### 2. Scheduler (Docker) + Watchtower

Build manual (**não use `docker compose build`** — falha com erro de
`veth` neste kernel):

```bash
DOCKER_BUILDKIT=0 docker build --network host -t tinyai/scheduler:latest ./scheduler
docker compose up -d
```

`docker-compose.yml` não tem nenhum `build:` — só `image:` com
`pull_policy: never`, então o `docker compose up -d` apenas cria os
containers a partir da imagem já buildada localmente, sem nunca acionar o
BuildKit/bake.

### 3. Testar

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

Voz: `POST /voz` com o campo multipart `audio` (WAV) devolve WAV
sintetizado pelo Piper.

## Estrutura

```
scheduler/                  # cérebro em Python (FastAPI) — único serviço em Docker
  scheduler/rotas.py             # decisão de rota — funções puras, testáveis
  scheduler/adaptadores.py       # HTTP clients: STT, llama.cpp, Piper, OpenRouter
  scheduler/hardware.py          # RAM/CPU/temperatura via /proc e /sys
  scheduler/api.py               # endpoints /prompt, /voz, /saude
  tests/                         # testes das regras de decisão
native/                     # serviços nativos (fora do Docker) — solução p/ ARMv7 sem veth
  piper/server.py                # servidor HTTP fino: POST /api/tts -> WAV (chama binário piper)
  stt/server.py                  # servidor HTTP fino: POST /inference -> texto (usa Vosk)
docker-compose.yml           # sobe scheduler + watchtower, ambos em network_mode: host
systemd/                     # units: serviços nativos + boot automático + monitoramento
scripts/monitor.sh           # diagnóstico de recursos com thresholds e alertas
docs/                         # MkDocs: arquitetura (Mermaid), módulos, ADRs
.github/workflows/            # CI: testes + build multi-arch linux/arm/v7 → GHCR
```

## Como o Scheduler decide

| Entrada | Rota |
|---|---|
| Áudio | STT (Vosk) → LLM → Piper |
| Texto pequeno + hardware saudável (RAM ≥ 500MB, CPU < 90%, temp < 75°C) | LLM local |
| Texto complexo ou hardware pressionado | OpenRouter |
| Falha do modelo local | Fallback automático → OpenRouter |

Cada decisão vira log JSON (rota, motivo, latência, fallback).

### Prompt de sistema e ajustes de geração

O `completar_local` em `adaptadores.py` injeta um prompt de sistema fixo
(identidade + instrução de concisão) antes de cada pergunta, com
`temperature=0.35` e `repeat_penalty=1.15` para reduzir divagação — modelos
de 0.5B tendem a "alucinar" tópicos aleatórios sem essa ancoragem. A
resposta também passa por uma limpeza (`_limpar_resposta`) que remove
rótulos ecoados do prompt (ex: "Resposta:") e apara a última frase
incompleta, evitando respostas cortadas no meio.

## Tuning de performance aplicado

Com um Cortex-A7 de 4 núcleos, a geração roda a **~1.8–2 tokens/segundo**
com Qwen2.5-0.5B-Instruct Q4_K_M — esse é o teto físico do hardware, não
um bug. Os ajustes abaixo otimizam o que dá para otimizar:

- **`max_tokens=56`** no endpoint `/prompt` (em vez do padrão de 256) —
  mantém a latência em ~30s em vez de ~2min.
- **Governor de CPU fixado em `performance`** via serviço systemd
  (`cpu-performance.service`), evitando o atraso de escalonamento de
  frequência do `ondemand`.
- **`llama-server -np 1`** — um único slot de inferência usando o contexto
  completo de 512 tokens, em vez de 4 slots (padrão) dividindo o contexto
  em pedaços de ~128 tokens cada, inúteis nesse hardware sem paralelismo
  real.
- **`TIMEOUT_LOCAL_S=180`** no `.env` — evita `TimeoutException` em
  respostas que se aproximem do limite de tokens.

Alavanca não aplicada, mas testável: quantização `Q4_0` no lugar de
`Q4_K_M` pode ganhar ~10-15% em ARM com NEON — compare com `print_timing`
do `journalctl -u tinyai-llm` antes de trocar definitivamente.

## Solução de problemas conhecidos deste hardware

- **`no matching manifest for linux/arm/v7`**: a imagem Docker não publica
  build para ARMv7 32-bit. Prefira compilar/rodar o binário nativo (como
  fizemos com Piper e llama.cpp) em vez de depender de imagens oficiais.
- **`failed to create endpoint ... operation not supported` / erro de
  `veth`**: o kernel não tem o módulo `veth` (`modprobe veth` retorna
  `Module veth not found`). Builds precisam de
  `DOCKER_BUILDKIT=0 docker build --network host` manual; containers em
  runtime devem usar `network_mode: host`. **Nunca** use
  `docker compose build` ou `docker compose up --build` neste hardware.
- **`cannot enable executable stack as shared object requires`**: alguma
  lib `.so` pré-compilada (ex: `libvosk.so`) pede stack executável,
  bloqueado pelo kernel. Corrige-se limpando o bit executável do segmento
  `PT_GNU_STACK` do binário ELF (o pacote `execstack` não existe mais no
  Debian bookworm — usamos um patch manual em Python; ver histórico do
  projeto).
- **`curl: Failed to connect ... Could not connect to server` logo após
  `docker compose up -d`**: corrida de largada — o container reporta
  "Started" antes do uvicorn terminar de subir. Espere 2-3s antes do
  primeiro curl, ou confirme com `docker compose logs scheduler --tail=20`
  procurando por `Uvicorn running on http://0.0.0.0:8000`.
- **TV box para de responder a ping/SSH completamente** (não é erro de
  serviço, é o dispositivo inteiro travado): suspeita principal é **OOM**
  — rodar `docker build` (que já é pesado em RAM/CPU) com o
  `tinyai-llm.service` ativo ao mesmo tempo pode estourar a memória
  disponível (~970MB total). **Recomendação:** sempre
  `sudo systemctl stop tinyai-llm.service` antes de qualquer
  `docker build`, e subir de novo depois. Sem acesso físico ao
  dispositivo, a única recuperação é desconectar e reconectar a energia.
  Depois de religar, diagnostique com:
  ```bash
  sudo journalctl -k -b -1 --no-pager | tail -100
  sudo dmesg -T | grep -iE "oom|out of memory|killed process"
  ```

## Instalar na TV Box (boot automático)

```bash
sudo cp -r . /opt/tinyai-box
sudo cp systemd/* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now \
  tinyai-piper.service tinyai-llm.service tinyai-stt.service \
  cpu-performance.service \
  tinyai.service tinyai-monitor.timer
```

## Pendências conhecidas

- **Captura de microfone contínua / wake word**: hoje o áudio precisa ser
  enviado manualmente via `curl`/API para `/voz`. Há um front-end de
  captura com wake word ("hey_jarvis" via openWakeWord) em
  `~/apps/box-assistant` que pode ser adaptado para chamar `/voz` no lugar
  do fluxo antigo — pendente de implementação como
  `tinyai-wakeword.service`.
- **Monitoramento (`tinyai-monitor.timer`)**: ainda não instalado nesta
  rodada. Planejado expor um endpoint `/metrics` (RAM/CPU/temperatura em
  JSON) para ser consumido remotamente por um Uptime Kuma rodando em outra
  máquina (monitor tipo "JSON Query" ou simples "HTTP(s)" apontando para
  `/saude`), evitando rodar o próprio Uptime Kuma (Node.js, pesado) nesta
  TV box.

## Desenvolvimento

```bash
cd scheduler
pip install -r requirements.txt pytest
python -m pytest tests/ -v
uvicorn scheduler.api:app --reload
```

Documentação completa: `pip install mkdocs-material && mkdocs serve`

## Decisões de arquitetura

- **ADR-001** — camadas simples com Scheduler central único
- **ADR-002** — roteamento por heurística barata + estado real do hardware
- **ADR-003** — OTA via Watchtower (1x/dia, rollback fixando tag)
- **ADR-004** — serviços de IA (TTS/LLM/STT) nativos via systemd em
  hardware sem suporte a `veth`, com apenas o Scheduler e o Watchtower
  permanecendo em container (`network_mode: host`)

Detalhes em `docs/adr/`.

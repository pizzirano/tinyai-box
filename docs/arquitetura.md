# Arquitetura

O sistema segue camadas simples, com o Scheduler como único cérebro:

```mermaid
flowchart TD
    U[Usuário: texto ou voz] --> S[Scheduler :8000]
    S -->|áudio| W[Whisper STT]
    W --> S
    S -->|prompt pequeno + hardware ok| L[TinyLlama<br/>llama.cpp local]
    S -->|prompt complexo ou hardware pressionado| O[OpenRouter API]
    L --> S
    O --> S
    S -->|resposta de voz| P[Piper TTS]
    P --> U
    S -->|resposta de texto| U

    subgraph Observabilidade
      H["/proc + /sys<br/>RAM, CPU, temperatura"]
    end
    H -.alimenta decisão.-> S
```

## Fluxo de uma requisição de voz

```mermaid
sequenceDiagram
    participant U as Usuário
    participant S as Scheduler
    participant W as Whisper
    participant L as LLM (local ou remoto)
    participant P as Piper
    U->>S: POST /voz (WAV)
    S->>S: lê hardware + decide rota
    S->>W: transcrever
    W-->>S: texto
    S->>L: completar (rota decidida)
    L-->>S: resposta
    S->>P: sintetizar
    P-->>S: WAV
    S-->>U: áudio + headers (transcrição, rota)
```

## Regras de decisão

| Condição | Rota |
|---|---|
| Entrada é áudio | Pipeline de voz |
| ≤ 280 chars, sem palavra-chave complexa, RAM ≥ 500MB, CPU < 90%, temp < 75°C | TinyLlama local |
| Complexo OU hardware pressionado (com OpenRouter configurado) | OpenRouter |
| Falha do local | Fallback → OpenRouter |

Decisões registradas em log JSON estruturado (rota, motivo, latência, fallback).
Histórico de decisões de arquitetura em `docs/adr/`.

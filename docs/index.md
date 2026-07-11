# TinyAI Box

Caixa de IA local rodando em uma TV Box ARMv7 (Armbian/Debian, 1-4GB RAM).
Fala por voz (Whisper → LLM → Piper), responde prompts pequenos com TinyLlama
local e delega prompts complexos ao OpenRouter.

**Subir tudo:**

```bash
cp .env.example .env   # preencher OPENROUTER_API_KEY (opcional)
docker compose up -d
```

Veja [Arquitetura](arquitetura.md) para entender as camadas, e os módulos no
menu lateral para detalhes de cada serviço.

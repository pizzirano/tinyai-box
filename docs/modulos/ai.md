# Módulo: IA local

Modelo padrão: **TinyLlama 1.1B Chat, GGUF Q4_K_M** (~670MB em disco, ~800MB de
RAM em uso com contexto 1024). Cabe com folga em uma box de 2GB deixando espaço
para Whisper tiny e Piper.

Baixar o modelo para o volume:

```bash
docker compose up -d llm-local   # cria o volume "modelos"
docker run --rm -v tinyai-box_modelos:/models alpine \
  wget -O /models/tinyllama-1.1b-chat-q4_k_m.gguf \
  https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf
docker compose restart llm-local
```

Trade-off: modelos maiores (3B Q4) melhoram qualidade mas dobram a RAM e caem
para ~1-2 tokens/s em ARMv7 — estimativas; validar com benchmark real na box.

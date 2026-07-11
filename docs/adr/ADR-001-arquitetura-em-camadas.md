# ADR-001: Arquitetura em camadas com Scheduler central
Data: 2026-07-11
Status: aceito

Contexto:
O TinyAI Box roda em TV Box ARMv7 com 1-4GB de RAM. Precisamos de um único
ponto de decisão que escolha entre voz (Whisper→LLM→Piper), LLM local
(TinyLlama) e IA remota (OpenRouter), respeitando os limites do hardware.

Decisão:
Adotar arquitetura em camadas: Scheduler → Docker → Voice → OTA → Network.
O Scheduler é o único componente com lógica de roteamento; os demais serviços
são "burros" (recebem requisição, respondem). Todos os serviços sobem com um
único `docker compose up -d`.

Consequências:
+ Um só lugar para entender/alterar o fluxo de decisão.
+ Serviços substituíveis (trocar TinyLlama por outro GGUF não toca o Scheduler).
- O Scheduler é ponto único de falha → mitigado com restart: unless-stopped.

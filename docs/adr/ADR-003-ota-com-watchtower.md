# ADR-003: OTA de containers via Watchtower
Data: 2026-07-11
Status: aceito

Contexto:
A caixa fica na casa do usuário; atualizações precisam ser automáticas,
simples e reversíveis.

Decisão:
Usar Watchtower checando o registry 1x/dia. Rollback = fixar a tag anterior
da imagem no docker-compose.yml e `docker compose up -d`. Nada de pipeline
de atualização customizado.

Consequências:
+ Zero código próprio de OTA para manter.
- Atualização automática pode trazer regressão → mitigado publicando tags
  versionadas no CI e podendo fixar versão no compose.

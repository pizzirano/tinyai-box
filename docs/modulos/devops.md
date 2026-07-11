# Módulo: DevOps

- **Compose**: `docker compose up -d` sobe scheduler, llm-local, whisper, piper e watchtower. Limites de memória por serviço protegem a box.
- **Build ARMv7 local**: `docker buildx build --platform linux/arm/v7 -t tinyai/scheduler ./scheduler`
- **CI (GitHub Actions)**: roda os testes; em push na main ou tag `v*`, builda multi-arch (`linux/arm/v7` + amd64) com cache de camadas e publica no GHCR.
- **OTA**: Watchtower checa novas imagens 1x/dia (ADR-003). Rollback = fixar tag anterior no compose.

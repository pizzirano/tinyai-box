# ADR-002: Roteamento por heurística simples + estado do hardware
Data: 2026-07-11
Status: aceito

Contexto:
Classificar a complexidade de um prompt com outro modelo custaria RAM/CPU que
não temos. Precisamos de uma régua barata.

Decisão:
Heurística pura em Python: prompt ≤ 280 chars e sem palavras-chave de
raciocínio → local; caso contrário → OpenRouter. A decisão também consulta o
estado do hardware (RAM livre ≥ 500MB, CPU < 90%, temp < 75°C) antes de
escolher o modelo local. Falha do local cai em fallback para OpenRouter.

Consequências:
+ Decisão em microssegundos, testável sem rede (13 testes unitários).
- Heurística pode errar; os limites são constantes fáceis de ajustar em
  scheduler/rotas.py conforme uso real.

# SoilTest: em desenvolvimento

Nada aqui foi validado por completo no PLAXIS real. Para trabalho, use `../plaxis_soiltest_auto.py`.

| Arquivo | O que é | Situação |
|---|---|---|
| `plaxis_soiltest_auto_dev.py` | O mesmo script da versão estável com `SOMENTE_VALIDADO = False`: libera **cíclicos não drenados** e **controle por tensão** no CDSS e no triaxial cíclico | Atributos existem na API; ainda não calculados no PLAXIS real |
| `soiltest_triaxial.py` | Triaxial com comparação contra um CSV de laboratório (RMSE e R² de q × ε_a, ε_v e Δu) | Triaxial validado; comparação com laboratório testada só com dados fictícios (mock). É a base da calibração |
| `soiltest_ensaios.py` | Edômetro, CRS e DSS com comparação contra laboratório | Superado pelo script automático para rodar os ensaios; mantido pela parte de comparação |

## Próximos passos

1. Rodar o `_dev` com MC ou HS e comportamento U no CDSS e no triaxial cíclico (Δu deve crescer a cada ciclo).
2. Rodar o `_dev` com controle por tensão (amplitude de 20 a 30 % da resistência).
3. Calibração: ajustar parâmetros (por exemplo φ', E50ref, m) minimizando o erro contra o ensaio de laboratório,
   usando o script automático para simular e `soiltest_triaxial.py` para medir o erro.

Quando um item for validado, ele passa para o script estável. Basta mudar a condição em `SOMENTE_VALIDADO` e
acrescentar o caso em `tests/regressao.sh`.

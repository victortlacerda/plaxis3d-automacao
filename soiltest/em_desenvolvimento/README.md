# SoilTest: em desenvolvimento

Para trabalho, use `../plaxis_soiltest_auto.py`. Os cíclicos não drenados e o controle por tensão foram validados no PLAXIS real em 08/11/2026 e já estão na versão estável.

| Arquivo | O que é | Situação |
|---|---|---|
| `plaxis_soiltest_auto_dev.py` | Cópia de trabalho do script, usada pela bateria; é onde entram os próximos recursos antes de irem para a versão estável | Hoje igual à estável |
| `soiltest_bateria.py` | Roda sem perguntas, numa única execução, as rodadas pendentes: cíclicos não drenados, controle por tensão, K0 no DSS/CDSS/cíclico e HS sem pré-adensamento × OCR = 2. Grava `soiltest_saida/bateria_<data>.txt` | Rodada no PLAXIS real em 08/11/2026 (5 casos, sem erro); saídas em `../exemplos/bateria_20261108/` |
| `soiltest_triaxial.py` | Triaxial com comparação contra um CSV de laboratório (RMSE e R² de q × ε_a, ε_v e Δu) | Triaxial validado; comparação com laboratório testada só com dados fictícios (mock). É a base da calibração |
| `soiltest_ensaios.py` | Edômetro, CRS e DSS com comparação contra laboratório | Superado pelo script automático para rodar os ensaios; mantido pela parte de comparação |

## Próximos passos

1. Acúmulo de poropressão em ciclos: repetir a bateria com HS small, MCC e Soft Soil (modelos com contração plástica). O MC com ψ = 0 não acumula.
2. Efeito do OCR no HS e no MCC pelo edômetro e pelo CRS (modo σ'p), onde o pré-adensamento aparece de fato.
3. Calibração: ajustar parâmetros (por exemplo φ', E50ref, m) minimizando o erro contra o ensaio de laboratório, usando o script automático para simular e `soiltest_triaxial.py` para medir o erro.

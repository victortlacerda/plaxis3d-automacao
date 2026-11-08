# SoilTest: em desenvolvimento

Para trabalho, use `../plaxis_soiltest_auto.py`. Os cíclicos não drenados e o controle por tensão foram validados no PLAXIS real em 08/11/2026 e já estão na versão estável.

| Arquivo | O que é | Situação |
|---|---|---|
| `plaxis_soiltest_auto_dev.py` | Cópia de trabalho do script, usada pela bateria; é onde entram os próximos recursos antes de irem para a versão estável | Hoje igual à estável |
| `soiltest_bateria.py` | Roda sem perguntas, numa única execução, as rodadas pendentes: cíclicos não drenados, controle por tensão, K0 no DSS/CDSS/cíclico e HS sem pré-adensamento × OCR = 2. Grava `soiltest_saida/bateria_<data>.txt` | Rodada no PLAXIS real em 08/11/2026 (5 casos, sem erro); saídas em `../exemplos/bateria_20261108/` |
| `soiltest_triaxial.py` | Triaxial com comparação contra um CSV de laboratório (RMSE e R² de q × ε_a, ε_v e Δu) | Triaxial validado; comparação com laboratório testada só com dados fictícios (mock). É a base da calibração |
| `soiltest_ensaios.py` | Edômetro, CRS e DSS com comparação contra laboratório | Superado pelo script automático para rodar os ensaios; mantido pela parte de comparação |

## Próximos passos

1. Calibração: ajustar parâmetros (por exemplo φ', E50ref, m) minimizando o erro contra o ensaio de laboratório, usando o script automático para simular e `soiltest_triaxial.py` para medir o erro.
2. (Adiado) Modelos cíclicos do PLAXIS (UBC3D-PLM, PM4Sand) para acúmulo de poropressão: os 6 modelos atuais não acumulam Δu de forma progressiva (bateria 2).

A bateria (`soiltest_bateria.py`) tem duas listas de casos: `RODAR = "1"` (MC, LE e HS: cíclicos, tensão, K0, OCR no triaxial) e `RODAR = "2"` (HS small, MCC e Soft Soil cíclicos; OCR no edômetro e no CRS) e `RODAR = "3"` (σ'p padrão no MCC e no Soft Soil).

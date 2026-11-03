# SoilTest: exemplos (rodadas reais)

Saídas originais do `plaxis_soiltest_auto.py` no PLAXIS 3D 2024.2, copiadas sem edição. As colunas dos CSV estão
explicadas no [glossário](../glossario.md). Os gráficos destas rodadas estão em [`../imagens/`](../imagens/).

| Pasta | Rodada |
|---|---|
| `LE_drenado_todos_ensaios/` | Linear Elastic drenado (E' = 30000 kPa, ν' = 0,3): triaxial, edômetro, CRS, DSS, CDSS e triaxial cíclico. Todos conferem com a teoria |
| `HS_K0_OCR2/` | Hardening Soil drenado com corte de dilatância, consolidação K0 = 0,5 e OCR = 2; triaxial em σ3 = 50, 100 e 200 kPa |

O `log.txt` do Linear Elastic foi gerado por uma versão anterior e mostra o aviso "261 pontos lidos; esperava 241".
O aviso estava errado; o certo é (4 × ciclos + 1) × passos + 1 = 261, e a versão atual já usa essa conta.

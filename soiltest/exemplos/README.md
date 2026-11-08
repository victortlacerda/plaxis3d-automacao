# SoilTest: exemplos (rodadas reais)

Saídas originais do `plaxis_soiltest_auto.py` no PLAXIS 3D 2024.2, copiadas sem edição. As colunas dos CSV estão
explicadas no [glossário](../glossario.md). Os gráficos destas rodadas estão em [`../imagens/`](../imagens/).

| Pasta | Rodada |
|---|---|
| `LE_drenado_todos_ensaios/` | Linear Elastic drenado (E' = 30000 kPa, ν' = 0,3): triaxial, edômetro, CRS, DSS, CDSS e triaxial cíclico. Todos conferem com a teoria |
| `ferramentas_20261108/` | Rodadas reais das ferramentas: auditoria dos 11 materiais do projeto, biblioteca (3 materiais da planilha modelo), paramétrico de φ' e curvas G/G0 do HS small. Cada pasta tem `relatorio.html` e `log.txt` |
| `bateria_20261108_3/` | Bateria 3: σ'p padrão de 100 kPa no edômetro e no CRS do MCC e do Soft Soil, sem informar pré-adensamento |
| `bateria_20261108_2/` | Bateria 2: cíclicos não drenados com HS small, MCC e Soft Soil; edômetro e CRS do HS e do MCC sem pré-adensamento × σ'p = 100 kPa |
| `bateria_20261108/` | Bateria de 08/11/2026: cíclicos não drenados e controle por tensão (MC), K0 no DSS/CDSS/triaxial cíclico (LE), HS normalmente adensado × OCR = 2. Resumo em `resumo_bateria.txt` |
| `HS_K0_OCR2/` | Hardening Soil drenado com corte de dilatância, consolidação K0 = 0,5 e OCR = 2; triaxial em σ3 = 50, 100 e 200 kPa |

O `log.txt` do Linear Elastic foi gerado por uma versão anterior e mostra o aviso "261 pontos lidos; esperava 241".
O aviso estava errado; o certo é (4 × ciclos + 1) × passos + 1 = 261, e a versão atual já usa essa conta.

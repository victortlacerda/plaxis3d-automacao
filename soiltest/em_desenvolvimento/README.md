# SoilTest: em desenvolvimento

Para trabalho, use `../plaxis_soiltest_auto.py`. Os cíclicos não drenados e o controle por tensão foram validados no PLAXIS real em 08/11/2026 e já estão na versão estável.

| Arquivo | O que é | Situação |
|---|---|---|
| `plaxis_soiltest_auto_dev.py` | Cópia de trabalho do script, usada pela bateria; é onde entram os próximos recursos antes de irem para a versão estável | Hoje igual à estável |
| `soiltest_bateria.py` | Roda sem perguntas, numa única execução, as rodadas pendentes: cíclicos não drenados, controle por tensão, K0 no DSS/CDSS/cíclico e HS sem pré-adensamento × OCR = 2. Grava `soiltest_saida/bateria_<data>.txt` | Rodada no PLAXIS real em 08/11/2026 (5 casos, sem erro); saídas em `../exemplos/bateria_20261108/` |
| `soiltest_triaxial.py` | Triaxial com comparação contra um CSV de laboratório (RMSE e R² de q × ε_a, ε_v e Δu) | Triaxial validado; comparação com laboratório testada só com dados fictícios (mock). É a base da calibração |
| `soiltest_calibracao.py` | **Calibração automática** contra triaxiais de laboratório (CSV): roda os mesmos ensaios no SoilTest, mede o erro em q × ε_a e Δu (ou ε_v) e ajusta os parâmetros livres (amostragem + Nelder-Mead, sem scipy). Avisa antes da busca quando os dados têm amolecimento pós-pico ou q máximo que não cresce com σ3. Saída: `historico.csv`, `melhor.json`, gráficos lab × simulação e `relatorio.html`; o material calibrado fica no Input | Rodado no PLAXIS real em 10 e 11/11/2026 contra 4 CIU de um solo residual: resistência livre (280 avaliações, erro 0,183) e φ' e c' do laudo fixos (201 avaliações em 23 min, erro 0,165). Formato do CSV em [`../dados_laboratorio_exemplo/`](../dados_laboratorio_exemplo/) |
| `soiltest_ensaios.py` | Edômetro, CRS e DSS com comparação contra laboratório | Superado pelo script automático para rodar os ensaios; mantido pela parte de comparação |

## Próximos passos

1. Calibração: conferir a sensibilidade a m (fixo em 0,3 e 0,5); depois, edômetro e ensaios drenados no mesmo calibrador. Passa para a versão estável quando tiver ao menos dois ensaios reais ajustados.
2. (Adiado) Modelos cíclicos do PLAXIS (UBC3D-PLM, PM4Sand) para acúmulo de poropressão: os 6 modelos atuais não acumulam Δu de forma progressiva (bateria 2).

A bateria (`soiltest_bateria.py`) tem duas listas de casos: `RODAR = "1"` (MC, LE e HS: cíclicos, tensão, K0, OCR no triaxial) e `RODAR = "2"` (HS small, MCC e Soft Soil cíclicos; OCR no edômetro e no CRS) e `RODAR = "3"` (σ'p padrão no MCC e no Soft Soil).

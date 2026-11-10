# Dados de laboratório: formato e exemplo

`lab_sintetico.csv` é um ensaio **sintético** (curvas inventadas), só para mostrar o formato e testar o calibrador.
Não é dado de ensaio real. Ensaios reais de clientes não ficam neste repositório: a pasta `dados_laboratorio/` está no
`.gitignore`.

Formato do CSV (separador `;`, vírgula ou ponto decimal), uma linha por ponto:

| Coluna | Significado |
|---|---|
| `ensaio` | nome do corpo de prova (ex.: `CIU_50kPa`) |
| `drenagem` | `U` = não drenado (CIU), `D` = drenado (CID) |
| `sigma3_kPa` | pressão confinante efetiva de adensamento |
| `eps_a_pct` | deformação axial (%) |
| `q_kPa` | tensão desviadora σ1 − σ3 |
| `du_kPa` | excesso de poropressão (ensaio `U`) |
| `ev_pct` | deformação volumétrica, contração positiva (ensaio `D`) |

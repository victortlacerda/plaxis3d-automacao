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

### Colunas opcionais (interpretação de ensaios, `../em_desenvolvimento/interpretacao/`)

Um CSV sem estas colunas continua valendo igual. Elas servem para outros tipos de ensaio e para agrupar CPs:

| Coluna | Significado |
|---|---|
| `tipo` | `UU`, `CIU`, `CAU`, `CID` ou `CAD`. Sem ela: `U` → CIU (UU se não houver `du_kPa`), `D` → CID; vira CAU/CAD quando há ponto em ε_a = 0 com q > 0 |
| `serie` | CPs que formam uma mesma envoltória (ex.: `SP01_5m`). Sem ela, a série é o tipo |
| `sigma1_kPa` | alternativa a `q_kPa`: com `q_kPa` vazio, q = σ1 − σ3 |
| `u0_kPa` | contrapressão; só informativa (as tensões totais são relativas a ela) |

`sigma3_kPa` é a tensão efetiva lateral de adensamento σ'3c nos ensaios adensados (no CAU/CAD, σ'3c = K·σ'1c e o
primeiro ponto tem q = q0) e a **pressão de câmara total** no UU (sem `du_kPa` e sem `ev_pct`).

Exemplo:

```
ensaio;tipo;serie;drenagem;sigma3_kPa;eps_a_pct;q_kPa;du_kPa;ev_pct;u0_kPa
CP1;CIU;SP01_5m;U;100;2,0;85,3;31,2;;300
CP4;UU;SP01_5m;U;150;3,0;62,0;;;
```

Modelo para preencher: `../em_desenvolvimento/interpretacao/modelo_entrada_laboratorio.csv`.

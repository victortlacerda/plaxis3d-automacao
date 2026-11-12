# Interpretação de ensaios triaxiais (laboratório e PLAXIS SoilTest)

Ferramenta independente para **extrair e interpretar** ensaios triaxiais reais (laudo) e simulados (PLAXIS SoilTest),
com gráficos, parâmetros por critério de ruptura e relatório. Não depende do calibrador.

| Arquivo | Para quê |
|---|---|
| `soiltest_extrair.py` | Puxa os triaxiais **do PLAXIS SoilTest** (roda os ensaios de um material do projeto, ou lê a janela já aberta), grava os CSV e faz o relatório |
| `soiltest_interpretacao.py` | Interpreta **CSV** de laboratório e/ou pastas de ensaios simulados e faz o relatório. Não precisa do PLAXIS |
| `modelo_entrada_laboratorio.csv` | **CSV-modelo** para digitar o laudo (UU, CIU e CID de exemplo, dados fictícios) |

Os dois scripts precisam do `plaxis_soiltest_auto.py` (em `soiltest/`), só pelo relatório e pela conexão com o PLAXIS.

## 1. Ensaio de laboratório: o CSV padrão

Copie `modelo_entrada_laboratorio.csv`, apague as linhas de exemplo e preencha uma linha por ponto da curva.
Separador `;`; vírgula ou ponto decimal (abre e salva direto no Excel em português como "CSV (separado por vírgulas)",
que no Brasil usa `;`). Guarde laudos reais em `dados_laboratorio/` (fora do git).

| Coluna | Obrigatória | Significado |
|---|---|---|
| `ensaio` | sim | nome do corpo de prova (CP); todas as linhas do mesmo CP têm o mesmo nome |
| `tipo` | recomendada | `UU`, `CIU`, `CAU`, `CID` ou `CAD` |
| `serie` | recomendada | CPs que formam uma envoltória (ex.: `SP01_5m`); sem ela, a série é o tipo |
| `drenagem` | se não houver `tipo` | `U` (não drenado) ou `D` (drenado) |
| `sigma3_kPa` | sim | CIU/CID/CAU/CAD: tensão efetiva de adensamento σ'3c (lateral). UU: pressão de câmara total |
| `eps_a_pct` | sim | deformação axial (%) |
| `q_kPa` | sim (ou `sigma1_kPa`) | tensão desviadora σ1 − σ3 |
| `sigma1_kPa` | não | alternativa a `q_kPa` (q = σ1 − σ3) |
| `du_kPa` | CIU/CAU | excesso de poropressão (acréscimo +) |
| `ev_pct` | CID/CAD | deformação volumétrica (contração +) |
| `u0_kPa` | não | contrapressão; só informativa |

Convenção de laboratório: compressão positiva. Coloque o ponto inicial (ε_a = 0): no CAU/CAD ele dá o q0 do
adensamento anisotrópico. Se a coluna `tipo` faltar, `U` vira CIU (UU sem `du_kPa`), `D` vira CID, e CAU/CAD quando o
ponto ε_a = 0 tem q > 0.

Rodar: edite `CONFIG["lab_csv"]` no `soiltest_interpretacao.py` e rode pelo `Executar_script_PLAXIS.bat`, ou no terminal:

```
python soiltest_interpretacao.py C:\...\dados_laboratorio\SP01.csv
```

## 2. Ensaio simulado: puxar do PLAXIS SoilTest (`soiltest_extrair.py`)

Edite o `CONFIG` no topo e rode pelo `Executar_script_PLAXIS.bat` (senha em `PLAXIS_PASSWORD`).

**Modo `"material"` (recomendado).** PLAXIS 3D Input aberto com o projeto. Em `"material"` o nome do material
(vazio = o script lista os materiais e pergunta). O script abre o SoilTest com ele, roda os triaxiais e interpreta.

```python
"modo": "material", "material": "Argila_SP01",
"pressoes_kPa": [50, 100, 200],                 # σ'3c de cada CP
"comportamentos": ["Undrained", "Drained"],     # Undrained -> CIU, Drained -> CID
"consolidacao": "Isotropic",                    # "K0" -> CAU/CAD (K0 = None usa 1 − sen φ')
"MaximumStrain": 20, "Steps": 100,
```

**Modo `"aberto"`.** O SoilTest já está aberto com o servidor de scripts ativo (porta em `"porta_soiltest"`, ou
`None` para procurar entre 10000 e 10030).
- `"rodar_ensaios": True`: roda os triaxiais do CONFIG no material que estiver na janela.
- `"rodar_ensaios": False`: **só lê** o triaxial que você calculou na janela (o SoilTest guarda uma curva por vez).
  Com `"pasta_ensaios"` fixa, cada execução acrescenta a curva e refaz o relatório com todas: calcule 50 kPa e rode;
  calcule 100 kPa e rode; e assim por diante.

Material Undrained C (tensões totais) vira UU; Non-porous só drenado; Undrained B e C só não drenado.
Para comparar com o laudo no mesmo relatório, preencha `"lab_csv"`.

Também dá para interpretar uma pasta do `plaxis_soiltest_auto.py` sem o PLAXIS:
`python soiltest_interpretacao.py lab.csv C:\...\soiltest_saida\auto_HS_D_...`

## 3. O que sai

Em `soiltest_saida/extracao_<material>_<data>/` (extrator) ou `soiltest_saida/interpretacao_<data>/`:

- `ensaios/*.csv` (só o extrator): as curvas puxadas do SoilTest, no formato do `plaxis_soiltest_auto.py`;
- `graficos/*.png`, um por gráfico e por série: q × ε_a (com os pontos de ruptura de cada critério), Δu × ε_a,
  A × ε_a, σ'1/σ'3 × ε_a, ε_v × ε_a, trajetórias p'–q (Cambridge), s'–t (MIT) e p–q total, círculos de Mohr total e efetivo;
- `parametros.csv`: c, φ, R² e M por série, tensão (total/efetiva) e critério;
- `interpretacao.json`: tudo (pontos de ruptura de cada CP, A_f, Su, ψ, envoltórias, alertas);
- `relatorio.html`: entradas, material, parâmetros, ruptura de cada CP, dilatância, alertas e gráficos (imprime em PDF);
- `log.txt`.

## 4. Como cada ensaio é interpretado

| Tipo | Tensão | Resultado |
|---|---|---|
| UU | total | Su = q_f/2 por CP e médio; círculos de Mohr; φ_u (≈ 0) e c_u da envoltória |
| CIU / CAU | total e efetiva | (c, φ) e (c', φ') por critério; A_f = Δu_f / (q_f − q0); trajetórias; Δu × ε_a |
| CID / CAD | efetiva | c', φ'; ε_v × ε_a; ψ de pico e médio: sen ψ = −(dε_v/dε_a)/(2 − dε_v/dε_a) |

- **Critérios de ruptura:** q máximo, σ'1/σ'3 máxima, ε_a limite (padrão 15 %) e fim do ensaio.
- **Envoltória:** regressão em (s, t), t = m + s·tan α, com sen φ = tan α e c = m / cos φ; M = 6 sen φ'/(3 − sen φ').
  Quando c < 0, mostra também φ com c = 0.
- **Alertas:** amolecimento pós-pico (> 10 %), q máximo que não cresce com σ'3c, R² < 0,95, c negativo, CP que
  não chega a ε_a limite, CIU sem Δu, Su muito variável no UU.

## 5. Situação

- Testado offline: CPs sintéticos com resposta conhecida (70 conferências) e a simulação `../../exemplos/HS_K0_OCR2`
  (devolve c' = 1 kPa, φ' = 35° e ψ = 5° do material). Extrator testado no mock do PLAXIS nos modos material,
  K0, aberto e só leitura.
- **Falta rodar no PLAXIS real** (`soiltest_extrair.py`) e com um laudo real.
- Próximos: laboratório × simulação no mesmo gráfico; edômetro (Cc, Cr, σ'p por Casagrande e Pacheco Silva, cv) e DSS;
  entrada em .xlsx.

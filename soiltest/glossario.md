# Glossário do plaxis_soiltest_auto.py

Este arquivo explica as siglas, os símbolos e as colunas dos CSV. Ele é gravado em cada pasta de saída.

## 1. Convenção de sinais (importante)

O PLAXIS usa **compressão negativa**. Nos CSV e nos gráficos deste script vale a convenção usual de laboratório, **compressão positiva**:

- tensões efetivas σ' > 0 em compressão;
- ε_a > 0 quando o corpo de prova encurta; ε_v > 0 quando o volume diminui (contração); ε_v < 0 é dilatação;
- Δu > 0 é acréscimo de poropressão (no PLAXIS, Δu = −PExcess).

## 2. Ensaios

| Nome no script | Ensaio | O que é |
|---|---|---|
| Triaxial | triaxial de compressão | corpo de prova cilíndrico; pressão confinante constante e carga axial crescente até a deformação máxima |
| Oedometer | edômetro | adensamento unidimensional: só deforma na vertical, sem deformação lateral; fases de carga e descarga |
| CRS | adensamento a taxa de deformação constante (Constant Rate of Strain) | como o edômetro, mas conduzido por deformação imposta |
| DSS | cisalhamento simples direto (Direct Simple Shear) | tensão vertical constante e distorção γ crescente |
| CDSS | DSS cíclico | distorção (ou tensão cisalhante) alternada, para módulo secante, amortecimento e geração de poropressão |
| CycTriaxial | triaxial cíclico | carga axial alternada em compressão e extensão |

Nos ensaios cíclicos os primeiros "passos por quarto" pontos são uma fase inicial, sem carga (deformação e tempo zero); depois vêm os ciclos completos, que começam e terminam em zero. Pontos = (4 × ciclos + 1) × passos por quarto + 1. No triaxial cíclico com controle por tensão, o primeiro meio ciclo é de extensão (q < 0).

## 3. Nome das curvas e dos arquivos (CD_50kPa, CU_100kPa)

- **CD** = Consolidated Drained: consolidação inicial e cisalhamento **drenado** (sem excesso de poropressão).
- **CU** = Consolidated Undrained: consolidação inicial e cisalhamento **não drenado** (volume constante, a poropressão varia).
- O **número** é a pressão de partida: no Triaxial e no Triaxial cíclico, a **pressão confinante σ'3** (kPa); no DSS e no CDSS, a **tensão vertical efetiva inicial σ'v0** (kPa).
- Exemplo: `triaxial_CD_50kPa.csv` = triaxial drenado com σ'3 = 50 kPa.

## 4. Grandezas dos gráficos e colunas dos CSV

Eixos: **a** = axial (direção vertical, y no PLAXIS) e **r** = radial/lateral (x no PLAXIS).

| Coluna do CSV | Símbolo | Significado |
|---|---|---|
| passo | – | número do passo de cálculo (0 = estado inicial, já consolidado) |
| tempo | t | tempo do ensaio, na unidade do SoilTest (dia nos ensaios por fases). Fica zero no Triaxial e no DSS monotônicos |
| eps_a_pct | ε_a | **deformação axial** (%) = encurtamento / altura inicial × 100. Positiva na compressão |
| ev_pct | ε_v | **deformação volumétrica** (%) = variação de volume / volume inicial × 100. Contração +, dilatação − |
| q_kPa | q | **tensão desviadora** q = σ'a − σ'r (= σ'1 − σ'3 na compressão). É a tensão que o corpo de prova suporta **além da pressão confinante**; é o dobro do raio do círculo de Mohr (τ_máx = q/2). A resistência é o pico q_f. No triaxial cíclico q tem sinal: q > 0 compressão, q < 0 extensão |
| p_kPa | p' | **tensão efetiva média** p' = (σ'a + 2σ'r)/3. O gráfico p'–q é a trajetória de tensões |
| sig_a_kPa | σ'a | tensão efetiva axial |
| sig_r_kPa | σ'r | tensão efetiva lateral. No triaxial é σ'3, a pressão confinante efetiva |
| sig_v_kPa | σ'v | tensão efetiva vertical (edômetro, CRS, DSS, CDSS) |
| sig_h_kPa | σ'h | tensão efetiva horizontal. K = σ'h/σ'v; no edômetro elástico K0 = ν/(1 − ν) |
| gamma_pct | γ_xy | **distorção** (%), deformação cisalhante de engenharia. No regime elástico τ = G·γ |
| tau_kPa | τ_xy | **tensão cisalhante** no plano horizontal (DSS e CDSS) |
| du_kPa | Δu | **excesso de poropressão** (kPa). Acréscimo +. Fica zero em ensaio drenado e em material non-porous |

## 5. Siglas dos modelos e da drenagem do material

| Sigla | Modelo |
|---|---|
| MC | Mohr-Coulomb |
| LE | Linear Elastic (elástico linear) |
| HS | Hardening Soil |
| HSsmall | Hardening Soil com rigidez a pequenas deformações |
| MCC | Modified Cam-Clay |
| SS | Soft Soil |

| Sigla | Drenagem do material (DrainageType) |
|---|---|
| D | Drained: parâmetros efetivos, sem poropressão gerada |
| UA | Undrained A: parâmetros efetivos; a poropressão é calculada (mesmo resultado do drenado no SoilTest) |
| UB | Undrained B: parâmetros efetivos de rigidez e resistência não drenada su |
| UC | Undrained C: parâmetros totais (su e ν_u) |
| NP | Non-porous: sem poropressão; só aceita ensaio drenado |

O comportamento do ensaio (CD ou CU) é escolhido à parte. Ele não depende da drenagem do material, exceto em UB, UC e NP.

## 6. Parâmetros do material

- **E'** módulo de Young efetivo; **ν'** coeficiente de Poisson efetivo; **ν_u** Poisson não drenado (≈ 0,495).
- **c'** coesão efetiva; **φ'** ângulo de atrito efetivo; **ψ** ângulo de dilatância; **su** resistência não drenada.
- **E50ref** módulo secante a 50 % de q_f na tensão de referência; **Eoedref** módulo edométrico tangente; **Eurref** módulo de descarga-recarga; **m** expoente de dependência da rigidez com a tensão; **ν_ur** Poisson de descarga-recarga; **pref** tensão de referência (100 kPa); **Rf** razão de ruptura (q_f / q_a, padrão 0,9).
- **G0ref** módulo de cisalhamento a pequenas deformações; **γ0,7** distorção em que G cai a 70 % de G0.
- **λ e κ** (MCC): inclinações da reta de compressão e de descarga em e × ln p'. **λ\* e κ\*** (Soft Soil): as mesmas inclinações em ε_v × ln p'. **M**: inclinação da linha de estado crítico no plano p'–q. **e_init**: índice de vazios inicial. **PhiInter**: ângulo de atrito da interface (o SoilTest recusa o MCC se PhiInter e CInter forem ambos zero).
- **Corte de dilatância** (HS e HSsmall): limita a dilatação quando o índice de vazios chega a **e_max**.

## 7. Consolidação e pré-adensamento

- **Consolidação isotrópica**: σ'x = σ'y antes do cisalhamento. **Consolidação K0**: σ'x = K0 · σ'y, com K0 = σ'h/σ'v. O K0 sugerido vem do K0nc do material, de 1 − sen φ' (Jaky), de M (MCC) ou de ν/(1 − ν).
- **σ'v0**: tensão vertical efetiva no início do cisalhamento. **σ'p**: pressão de pré-adensamento (maior tensão vertical efetiva já suportada).
- **OCR** = σ'p / σ'v0 (razão de pré-adensamento). **POP** = σ'p − σ'v0 (pressão de pré-sobrecarga). O script entrega ao SoilTest a pressão σ'p; com a opção OCR, σ'p = OCR × σ'v0 de cada ensaio.
- Só HS, HSsmall, MCC e Soft Soil aceitam editar σ'p; no MC e no LE é somente leitura.
- No MCC e no Soft Soil, o edômetro e o CRS usam σ'p = 100 kPa por padrão (ajustável), porque sem σ'p esses ensaios partem de tensão zero e a deformação não tem sentido.

## 8. Valores que o script calcula

- **q_f teórico (Mohr-Coulomb, drenado)** = 2 sen φ' / (1 − sen φ') · (σ'3 + c' / tg φ'). Para su: q_f = 2 su.
- **E50** simulado: q_f/2 dividido pela deformação axial em que q atinge q_f/2.
- **E_oed** = E'(1 − ν') / ((1 + ν')(1 − 2ν')): módulo edométrico elástico; ε_v = σ'v / E_oed.
- **G_sec** (CDSS) = amplitude de τ / amplitude de γ no último ciclo. **E_sec** (triaxial cíclico) = amplitude de q / amplitude de ε_a. Elástico: G = E'/(2(1 + ν')).
- **D** (amortecimento, %) = área do laço / (4π · W_s), com W_s = ½ · τ_a · γ_a (ou ½ · q_a · ε_a). Zero em material elástico.

## 9. Arquivos da pasta de saída

- um CSV por ensaio (`triaxial_CD_50kPa.csv`, `oedometer.csv`, `dss_CD_100kPa.csv`, ...);
- `graficos/`: um PNG por gráfico;
- `resumo.json`: parâmetros, consolidação, pré-adensamento e resultados das checagens;
- `log.txt`: tudo o que o script fez, com os avisos;
- `glossario.md`: este arquivo.

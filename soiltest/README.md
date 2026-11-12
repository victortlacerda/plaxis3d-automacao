# SoilTest automático

![Ensaios de laboratório virtuais, automáticos](imagens/capa.png)

Ensaios de laboratório **virtuais** no **PLAXIS SoilTest**, sem clicar em nada. Você escolhe o modelo constitutivo
e os parâmetros. O script cria o material no PLAXIS 3D Input, abre o SoilTest com ele, roda os ensaios, grava CSV
e gráficos e **confere os resultados com a solução teórica** quando ela existe.

É um único arquivo Python (`plaxis_soiltest_auto.py`), rodado pelo mesmo executor externo dos outros módulos.

## O que ele faz

| | |
|---|---|
| **Modelos** | Mohr-Coulomb, Linear Elastic, Hardening Soil, HS small, Modified Cam-Clay e Soft Soil, com todos os tipos de drenagem que o PLAXIS oferece para cada um (Drained, Undrained A/B/C, Non-porous) |
| **Ensaios** | Triaxial, edômetro, CRS, DSS, CDSS (cisalhamento simples cíclico) e triaxial cíclico |
| **Estado inicial** | Consolidação isotrópica ou **K0** (com K0 sugerido por Jaky, K0nc, M do MCC ou ν) e **pré-adensamento** por σ'p ou **OCR** |
| **Saída** | Um CSV por ensaio, **um PNG por gráfico** com eixos autoexplicativos, **relatório técnico HTML** (imprimível em PDF), `resumo.json`, `log.txt` e o [glossário](glossario.md) |
| **Conferência** | q_f de Mohr-Coulomb, 2·su, E·ε no elástico, E_oed no edômetro e no CRS, τ = G·γ no DSS, G_sec e E_sec nos cíclicos, E50 do HS, estado crítico do MCC |

## Galeria

Tudo abaixo vem de rodadas **reais** no PLAXIS 3D 2024.2 (as saídas completas estão em [`exemplos/`](exemplos/)).

**Entrada de dados no console:** menus numerados, Enter aceita o padrão, vírgula decimal aceita, resposta inválida
repete a pergunta.

![Perguntas](imagens/term_perguntas.png)

**Hardening Soil com consolidação K0 = 0,5 e OCR = 2:** o script lê as tensões iniciais que o SoilTest aplicou,
converte o OCR em σ'p para cada ensaio e confere a resistência (diferença menor que 0,04 kPa).

![Rodada HS](imagens/term_hs_k0_ocr.png)

| Tensão desviadora × deformação axial | Deformação volumétrica (corte de dilatância em 1,33 %) |
|---|---|
| ![q x eps_a](imagens/hs_k0_ocr_q_x_eps_a.png) | ![eps_v x eps_a](imagens/hs_k0_ocr_ev_x_eps_a.png) |

| Trajetória p'–q (início em q0 = σ'y − σ'x pela consolidação K0) | Edômetro (carga até 400 kPa e descarga) |
|---|---|
| ![p'-q](imagens/hs_k0_ocr_trajetoria_p_q.png) | ![edômetro](imagens/le_oedometer_sigv_x_epsv.png) |

**Linear Elastic com todos os ensaios:** o material elástico tem resposta exata conhecida, então serve de teste
de ponta a ponta. Todos os valores batem com a teoria.

![Rodada LE](imagens/term_le_todos_ensaios.png)

| DSS: τ × γ | CDSS: laço τ × γ (3 ciclos) |
|---|---|
| ![DSS](imagens/le_dss_tau_x_gamma.png) | ![CDSS](imagens/le_cdss_tau_x_gamma.png) |

| CRS: σ'v × ε_v | Triaxial cíclico: q × ε_a |
|---|---|
| ![CRS](imagens/le_crs_sigv_x_epsv.png) | ![Triaxial cíclico](imagens/le_cyctriaxial_q_x_eps_a.png) |

## Ferramentas

Scripts curtos que reaproveitam o `plaxis_soiltest_auto.py` (precisa estar na mesma pasta). Todos validados no PLAXIS real
em 08/11/2026, com saídas em [`exemplos/ferramentas_20261108/`](exemplos/ferramentas_20261108/).

| Ferramenta | O que faz |
|---|---|
| `soiltest_auditoria.py` | Lê **todos os materiais do projeto aberto**, confere a coerência dos parâmetros (faixas usuais e regras de cada modelo: Eoed/E50, Eur/E50, G0 ≥ Gur, λ > κ, regra de Bolton para ψ...), roda triaxial e edômetro de cada um e entrega um relatório com ERRO / ALERTA / INFO. Pega erro de entrada antes de calcular o 3D. |
| `soiltest_biblioteca.py` | Lê uma planilha CSV ([`materiais_modelo.csv`](materiais_modelo.csv)) e **cria ou atualiza os materiais no Input**, inclusive pesos específicos e qualquer atributo pelo nome. Opcionalmente confere cada material no SoilTest. |
| `soiltest_parametrico.py` | **Estudo paramétrico**: varia um parâmetro numa faixa (ex.: φ' de 28 a 36°), roda os mesmos ensaios e sobrepõe as curvas, com tabela-resumo. |
| `soiltest_gg0.py` | **Curvas G/G0 e amortecimento × γ** pelo CDSS em várias amplitudes, comparadas com o backbone do HS small e com Darendeli (2001). Para análise dinâmica. |

| Auditoria de materiais (resumo do relatório) | Relatório técnico de um material |
|---|---|
| ![Auditoria](imagens/ferr_auditoria.png) | ![Relatório](imagens/ferr_relatorio.png) |

| G/G0 × γ: SoilTest, HS small teórico e Darendeli | Amortecimento × γ |
|---|---|
| ![G/G0](imagens/ferr_gg0_x_gamma.png) | ![D](imagens/ferr_D_x_gamma.png) |

| Estudo paramétrico: φ' de 28 a 36° (MC, σ3 = 100 kPa) |
|---|
| ![Paramétrico](imagens/ferr_parametrico_phi.png) |

## Validação no PLAXIS real

| Rodada | Simulado | Teoria |
|---|---|---|
| MC drenado, σ3 = 50/100/200 kPa | q_max 134,647 / 234,652 / 434,658 kPa | q_f 134,641 / 234,641 / 434,641 |
| HS drenado, K0 = 0,5, OCR = 2 | q_max 138,359 / 272,877 / 541,913 kPa | q_f 138,351 / 272,859 / 541,876 |
| HS, corte de dilatância (eInit 0,5, eMax 0,52) | dilatação máx. 1,334 a 1,357 % | (eMax − eInit)/(1 + eInit) = 1,333 % |
| LE triaxial, 15 % | q 4500 kPa | E·ε = 4500 |
| LE edômetro, 400 kPa | ε_v 0,9905 % | σ/E_oed = 0,9905 % |
| LE CRS, 5 % | σ'v 2019,23 kPa | E_oed·ε = 2019,23 |
| LE DSS, γ = 10 % | τ 1153,846 kPa | G·γ = 1153,846 |
| LE CDSS, ±0,5 % | G_sec 11538,5 kPa, amortecimento 0 | G = 11538,46 |
| LE triaxial cíclico, ±0,5 % | E_sec 30000 kPa, amortecimento 0 | E = 30000 |
| HS small, CDSS em 8 amplitudes (G/G0) | G0 = 119 830 kPa; G/G0 = 0,8357 em γ = 0,01 % | G0ref = 120 000; backbone 0,8386 |
| Paramétrico MC, φ' de 28 a 36° | q_max 193,635 a 304,825 kPa | q_f de Mohr-Coulomb (diferença ≤ 0,015 kPa) |
| LE com K0 = 0,5: DSS, CDSS, triaxial cíclico | σ'x/σ'y = 0,5; τ, G e E iguais aos do isotrópico | K0 aplicado sem mudar a rigidez elástica |
| MC, controle por tensão (τ = 20 kPa, q = 50 kPa) | amplitudes exatas; não drenado E_u = 34500 kPa, Δu = ±16,3 kPa | 2G(1 + ν_u) = 34500; Δp = q/3 = 16,7 |
| MC, cíclico não drenado por deformação | Δu oscila sem acumular; CDSS sem Δu | MC com ψ = 0 não tem tendência volumétrica no cisalhamento |
| MCC edômetro com σ'p = 100 kPa | inclinação 0,0108 antes e 0,054 depois de σ'p | κ/(1 + e0) = 0,010 e λ/(1 + e0) = 0,050 |
| Soft Soil edômetro com σ'p padrão (100 kPa) | inclinação 0,0195 antes e 0,1000 depois de σ'p | κ* = 0,02 e λ* = 0,10 |
| HS edômetro com σ'p = 100 kPa | metade da deformação antes de σ'p; mesma inclinação depois | recompressão mais rígida, curva virgem igual |

O histórico completo das descobertas (nomes de atributos, sinais, armadilhas de cada modelo) está em
[`docs/referencia-soiltest.md`](docs/referencia-soiltest.md).

## Como rodar

1. Abra o **PLAXIS 3D Input** com um projeto e o servidor de scripts ativo (porta 10000).
2. Rode `plaxis_soiltest_auto.py` pelo executor externo (`Executar_script_PLAXIS.bat`).
3. Responda às perguntas (Enter mantém o valor entre colchetes). A senha do SoilTest é pedida na hora, ou lida da
   variável de ambiente `PLAXIS_PASSWORD`; nunca fica gravada em arquivo.
4. A saída vai para `soiltest_saida/auto_<modelo>_<drenagem>_<data>/` ao lado do script.

Sem perguntas: ponha `"interativo": False` no bloco `CONFIG` do topo do arquivo e edite os valores lá.

As ferramentas rodam do mesmo jeito: escolha o arquivo no executor; cada uma tem um bloco de configuração no topo
(`ESTUDO`, `PLANILHA`, `RODAR_SOILTEST`). Elas fecham cada janela do SoilTest ao terminar.

## Estável × em desenvolvimento

| Pasta / arquivo | Status |
|---|---|
| `plaxis_soiltest_auto.py` | **Estável.** Tudo o que já rodou no PLAXIS real, inclusive cíclicos não drenados e controle por tensão (validados em 08/11/2026). |
| `soiltest_auditoria.py`, `soiltest_biblioteca.py`, `soiltest_parametrico.py`, `soiltest_gg0.py` | **Estáveis.** Ferramentas validadas no PLAXIS real em 08/11/2026. |
| [`em_desenvolvimento/`](em_desenvolvimento/) | **Calibração automática** contra triaxiais de laboratório (`soiltest_calibracao.py`, já rodada contra ensaios reais), **interpretação de triaxiais** UU/CIU/CAU/CID/CAD como em laudo (`soiltest_interpretacao.py`, laboratório e simulação) e bateria de testes sem perguntas (`soiltest_bateria.py`) |
| [`descoberta/`](descoberta/) | Scripts usados para mapear a API do SoilTest (atributos, modelos, drenagens). Somente referência. |
| [`exemplos/`](exemplos/) | Saídas reais (CSV, log, resumo) das rodadas da galeria |

Quando um item em desenvolvimento for validado no PLAXIS real, ele passa para o script estável e a regressão
(`tests/regressao.sh`) ganha o caso correspondente.

## Pendências

- [x] Cíclicos não drenados (CDSS e triaxial cíclico) no PLAXIS real
- [x] Controle por tensão (`ShearStressAmplitude`, `AxialStressAmplitude`) no PLAXIS real
- [x] Consolidação K0 no DSS, CDSS e triaxial cíclico
- [x] Efeito do OCR no triaxial do HS (pequeno: +3 % de rigidez inicial; o OCR do HS age no cap)
- [x] Unidade do tempo nos cíclicos: a do projeto (dia)
- [x] Cíclicos não drenados com HS small, MCC e Soft Soil (nenhum acumula Δu de forma progressiva: HS small dilata, MCC e Soft Soil ficam elásticos após o 1º ciclo)
- [x] Efeito do OCR no edômetro e no CRS do HS e do MCC (confere com κ e λ no MCC)
- [x] No MCC e no Soft Soil, σ'p = 100 kPa por padrão no edômetro e no CRS (ajustável; validado no PLAXIS real)
- [ ] Mapear modelos cíclicos (UBC3D-PLM, PM4Sand): adiado, por decisão do projeto
- [x] Relatório técnico HTML em toda rodada
- [x] Ferramentas: auditoria, biblioteca de materiais, estudo paramétrico, curvas G/G0
- [ ] Interpretação de triaxiais (UU, CIU/CAU, CID/CAD) como em laudo: em desenvolvimento, testada offline com ensaios sintéticos
- [ ] Calibração automática contra ensaio de laboratório: em desenvolvimento, 1ª rodada real em 10/11/2026 (4 CIU)
- [ ] MCP: por último, se for feito

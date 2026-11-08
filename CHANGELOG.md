# Histórico de versões

## Não lançado
- `soiltest/`: no MCC e no Soft Soil, edômetro e CRS usam σ'p padrão (100 kPa, ajustável em `sigma_p_padrao_fases_kPa`
  ou na pergunta do modo interativo) quando o pré-adensamento não é informado; edômetro volta a vir ligado nesses modelos.
- `soiltest/`: Δu e tensão efetiva ao fim de cada ciclo no log dos ensaios cíclicos; bateria 2 (modelos contráteis em
  ciclos e OCR no edômetro/CRS) rodada no PLAXIS real. O MCC com σ'p confere com κ e λ; nenhum dos 6 modelos acumula Δu
  ciclo a ciclo.
- `soiltest/`: cíclicos não drenados, controle por tensão e K0 no DSS/CDSS/triaxial cíclico validados no PLAXIS real
  (bateria de 08/11/2026) e liberados na versão estável. Corrigida a descrição da ordem dos pontos nos cíclicos
  (fase inicial sem carga, depois ciclos de zero a zero) e anotado que o triaxial cíclico por tensão começa em extensão.
- `soiltest/`: SoilTest automático. `plaxis_soiltest_auto.py` (estável) cria o material no Input, abre o SoilTest
  e roda triaxial, edômetro, CRS, DSS, CDSS e triaxial cíclico para MC, LE, HS, HS small, MCC e Soft Soil, com
  consolidação K0, pré-adensamento (σ'p ou OCR), corte de dilatância, um PNG por gráfico, glossário e conferência
  teórica. Validado no PLAXIS real (MC drenado; HS com K0 e OCR; LE em todos os ensaios).
  `em_desenvolvimento/`: cíclicos não drenados, controle por tensão e comparação com laboratório (base da calibração).
- README com galeria: telas do script e gráficos de rodadas reais.
- `sapata/`: textos do menu e das etapas indicam que a sapata em volume e o módulo sem ação foram validados no Caso A.
- `subsolo/`: Caso B do manual (radier, paredes, coluna e vigas, três fases de construção). Em desenvolvimento.

## sapata-v1.0.0
- `sapata/plaxis_sapata_interativo.py`: quatro módulos de ação (só carga, só deslocamento prescrito, combinado,
  sem ação), sapata como placa ou como volume linear elástico não poroso, segunda carga (surface + point load),
  Title/Company opcionais, nome do material da sapata, porta perguntada só sem o executor externo.
- `sapata/plaxis_sapata_resultados.py`: curva carga × recalque, tangentes, 10% de B e 25 mm (Terzaghi e Peck, 1948),
  CSV para Excel pt-BR, quatro gráficos; resultados do módulo sem ação.
- Validado no PLAXIS real: Exemplo 1 (carga), Exemplo 2 (deslocamento prescrito: 3162,8 kN contra 3173 kN do PDF)
  e Caso A do manual da Bentley (volume não poroso, só peso próprio: Uz = -102,6 mm).
- `tests/`: regressão por mock.

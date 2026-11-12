# Histórico de versões

## Não lançado
- `soiltest/soiltest_campanha.py` (estável, validada no PLAXIS real em 12/11/2026): campanha de ensaios virtuais definida numa planilha CSV
  (material × ensaio × tensões × drenagem × K0 × pré-adensamento × ciclos), com materiais do projeto aberto ou
  criados pela planilha de materiais; relatório e `campanha_resumo.csv` com uma linha por curva; alerta de
  triaxial não drenado sem pico. Diferença com a teoria abaixo de 0,005 % aparece como 0,00 % (antes em notação científica).
- `plaxis_soiltest_auto_dev.py`: opção de usar um material que já está no projeto (menu ou `material_existente`).
- `soiltest/em_desenvolvimento/interpretacao/`: ferramenta própria para extrair e interpretar triaxiais reais e
  simulados, separada do calibrador. `soiltest_extrair.py` puxa os ensaios do PLAXIS SoilTest (material do projeto ou
  janela aberta, inclusive só lendo a curva já calculada) e faz o relatório; `soiltest_interpretacao.py` interpreta
  UU, CIU/CAU e CID/CAD em tensão total e efetiva (quatro critérios de ruptura, A de Skempton, dilatância, trajetórias,
  círculos de Mohr, alertas). CSV-modelo de entrada `modelo_entrada_laboratorio.csv` (colunas novas opcionais `tipo`,
  `serie`, `sigma1_kPa`, `u0_kPa`; o formato antigo continua válido). Testes offline com CPs sintéticos de resposta
  conhecida e com o mock do PLAXIS.
- `soiltest/em_desenvolvimento/soiltest_calibracao.py`: calibração automática de parâmetros (HS, MC) contra triaxiais
  de laboratório em CSV, trocando parâmetros direto no SoilTest. Primeira rodada real (4 CIU, 280 avaliações em 37 min).
  Aviso prévio de amolecimento pós-pico e de q máximo que não cresce com σ3; faixas padrão de m e Eur/E50 alargadas.
- `estudos/`: lote de sapatas por planilha, sensibilidade de malha/domínio, métodos analíticos (Terzaghi, Meyerhof, Vesić, recalque elástico) e memorial em .docx/.html.
- `ferramentas/resumo_projeto.py`: além do .txt, gera o painel `resumo_projeto.html`.
- `sapata/plaxis_sapata_interativo.py`: o JSON passa a guardar todas as respostas (`entrada`); nenhum comando ao PLAXIS mudou.
- `soiltest/`: relatório técnico HTML (`relatorio.html`, imprimível em PDF) em toda rodada do script principal.
- `soiltest/`: ferramentas `soiltest_auditoria.py` (auditoria dos materiais do projeto), `soiltest_biblioteca.py`
  (materiais a partir de planilha CSV), `soiltest_parametrico.py` (estudo paramétrico) e `soiltest_gg0.py`
  (curvas G/G0 e amortecimento, com HS small teórico e Darendeli), validadas no PLAXIS real.
- `soiltest/plaxis_soiltest_auto.py`: funções reutilizáveis `obter_input`, `abrir_soiltest`, `executar_ensaios` e
  `fechar_soiltest` (fecha a janela do SoilTest pela API).
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

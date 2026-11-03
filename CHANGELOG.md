# Histórico de versões

## Não lançado
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

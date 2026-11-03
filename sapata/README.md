# Sapata isolada (estável)

## Scripts
- `plaxis_sapata_interativo.py`: cria o modelo, salva e (opcional) calcula.
- `plaxis_sapata_resultados.py`: lê o Output e gera curva, critérios, CSV e gráficos.
- `exemplos/`: versões **não interativas** dos Exemplos 1 e 2 (parâmetros no topo do arquivo). São as
  referências validadas; não alterar.

## Módulos de ação (escolhidos na pergunta 5)
1. **Só carga** (surface load ou point load): Exemplo 1. Validado.
2. **Só deslocamento prescrito**: Exemplo 2. Validado (3162,8 kN contra 3173 kN do PDF, domínio 20 × 20).
3. **Combinado** (carga + deslocamento, em sequência ou na mesma fase): *não testado*.
4. **Sem ação** (só peso próprio): validado no Caso A do manual da Bentley (sapata em volume, Uz = -102,6 mm).

Opções extras: Title/Company, nome do material da sapata, sapata como **placa** ou **volume linear elástico
não poroso**, segunda carga (surface + point load; *não testado*).

## Critérios de capacidade de carga (resultados)
Interseção das tangentes, recalque = 10% de B e recalque de 25 mm (Terzaghi e Peck, 1948); qa = qu / 3.
Os dois últimos só valem para carga vertical para baixo.

## Ainda não validado no PLAXIS real
Várias camadas, sapata embutida, tração, carga horizontal, momento, deslocamento prescrito horizontal ou para
cima, módulo combinado, segunda carga, refino de malha com a sapata em volume.

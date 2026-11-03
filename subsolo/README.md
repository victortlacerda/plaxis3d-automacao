# Subsolo com radier (em desenvolvimento)

Reproduz o **Caso B** do Tutorial 1 do manual da Bentley (PLAXIS 3D): prédio com subsolo, um quarto do modelo.

## Scripts
- `plaxis_subsolo_interativo.py`: cria o modelo e as fases Excavation, Construction e Loading.
- `plaxis_subsolo_resultados.py`: Uz dos pontos por fase, M11/M22 e Uz do piso, perfil de Uz do solo, CSV e gráficos.

## Status: NADA aqui foi validado no PLAXIS real
Foi escrito a partir do manual. O script não aborta na primeira falha: registra o item, imprime o `echo()` do objeto
(para descobrir os nomes reais das propriedades), segue com o resto e só calcula se nada falhou.

Pontos de maior risco (pendências):
- [ ] `beammat` / `beam` (propriedades A, I2, I3, tipo de seção)
- [ ] `lineload` (propriedade `qz_start`)
- [ ] plates em superfícies coincidentes com o volume extrudado (podem duplicar)
- [ ] `deactivate` do solo do subsolo na fase Excavation
- [ ] E'inc e zref (rigidez crescente com a profundidade)
- [ ] leitura de resultados de plate por `getresults`
- [ ] refino de malha no volume (hoje só o preset de malha)

Como fechar essas pendências: refazer o Caso B pela interface do PLAXIS e enviar o **histórico de comandos**
(command line history); com os nomes reais, o script é ajustado e este arquivo atualizado.

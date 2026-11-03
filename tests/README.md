# Testes por mock (sem PLAXIS)

- `mock/rodar_interativo.py`: finge o PLAXIS Input; registra cada `CALL`/`SET` enviado a `g_i`.
- `mock/rodar_resultados.py`: finge o Output (curvas e resultados sintéticos).
- `entradas/`: respostas (uma por linha; linha vazia = Enter) para cada cenário.
- `dados/`: JSONs de modelo para os scripts de resultados.
- `baselines/`: saída esperada de cada cenário. `regressao.sh` compara; `--gravar` atualiza.

O mock confere **ordem de comandos e lógica**, não os nomes reais das propriedades: só o PLAXIS valida isso.

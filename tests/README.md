# Testes por mock (sem PLAXIS)

- `mock/rodar_interativo.py`: finge o PLAXIS Input; registra cada `CALL`/`SET` enviado a `g_i`.
- `mock/rodar_resultados.py`: finge o Output (curvas e resultados sintéticos).
- `mock/rodar_soiltest.py`: finge o Input e o SoilTest para `soiltest/` (resultados aproximados; confere o fluxo,
  as mensagens e as checagens, não a mecânica).
- `entradas/`: respostas (uma por linha; linha vazia = Enter) para cada cenário.
- `dados/`: JSONs de modelo para os scripts de resultados.
- `baselines/`: saída esperada de cada cenário. `regressao.sh` compara; `--gravar` atualiza.

O mock confere **ordem de comandos e lógica**, não os nomes reais das propriedades: só o PLAXIS valida isso.

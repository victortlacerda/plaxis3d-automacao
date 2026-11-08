# Estudos de sapata (lote, sensibilidade, analítico e memorial)

Ferramentas que **reusam sem alterar** os scripts validados de `sapata/`: o `construir()` do
`plaxis_sapata_interativo.py` é chamado com os dados montados aqui, e o `plaxis_sapata_resultados.py` roda inteiro
na pasta de cada caso. Os comandos enviados ao PLAXIS são os mesmos já validados.

| Script | O que faz |
|---|---|
| `sapata_lote.py` | Lê `sapatas_lote.xlsx` (uma sapata por linha), roda todas e gera resumo (xlsx/csv), painel HTML, gráfico comparativo e um memorial por caso |
| `sapata_sensibilidade.py` | Roda o mesmo caso variando malha, largura e profundidade do domínio e diz a partir de onde o resultado estabiliza |
| `sapata_relatorio.py` | Use no lugar do `plaxis_sapata_resultados.py`: resultados + Terzaghi/Meyerhof/Vesić + memorial (.docx e .html) |
| `sapata_analitico.py` | Capacidade de carga (Terzaghi 1943, Meyerhof 1963, Vesić 1975) e recalque elástico. `python sapata_analitico.py` confere os fatores com valores de livro |
| `sapata_memorial.py` | Gera Word (.docx) e HTML sem dependências externas |
| `sapata_motor.py` | Execução dos casos, leitura/escrita de xlsx e gráfico PLAXIS x analítico |

## Como usar
1. Copie para a mesma pasta: estes arquivos, `plaxis_sapata_interativo.py`, `plaxis_sapata_resultados.py` e a planilha.
2. Preencha a aba **Sapatas** de `sapatas_lote.xlsx` (a aba **Instruções** explica cada coluna).
3. Rode `sapata_lote.py` pelo executor externo. A saída fica em `lote_<data>/` e o painel abre no navegador.

## Rodar sem digitar nada (pelo menu do PLAXIS)
1. Em `ferramentas/auto_config.json`, indique o script e as respostas (uma por pergunta; "" = Enter).
2. No PLAXIS 3D Input: **Expert > Run Python script > Open...** e escolha `ferramentas/executar_auto.py`.
   (É preciso o PLAXIS ter um Python configurado em Expert > Python > Configure Python interpreter.)
3. Tudo o que for impresso vai para o log indicado no `auto_config.json`.
Pelo executor externo tudo continua funcionando como antes.

## Status (08/11/2026)
Rodados no **PLAXIS 3D 2024.2 real**:
- `sapata_lote.py` com 2 casos (malha coarse): Exemplo 1 com carga (qu tangentes 905 kN/m², 3485 elementos) e
  Exemplo 2 com 25 mm prescritos (2982 kN, 4111 elementos). Repetido: mesmo resultado.
- `sapata_relatorio.py` (memorial do Exemplo 2) e `ferramentas/resumo_projeto.py` (painel HTML).
- `sapata_sensibilidade.py`: malha very coarse (3056 kN) e coarse (2982 kN) concluídas; as rodadas medium e de
  largura foram canceladas por **disco cheio** no C: e agora são descartadas automaticamente (LogInfo 254).
Fatores analíticos conferidos com tabelas de livro (Nc, Nq, Nγ para φ' = 20° e 30°).

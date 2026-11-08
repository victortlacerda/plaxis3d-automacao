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

## Status
Testados com o mock (`tests/regressao.sh`); **ainda sem rodada no PLAXIS real**. Os fatores analíticos foram
conferidos com tabelas de livro (Nc, Nq, Nγ para φ' = 20° e 30°).

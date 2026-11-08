# Exemplos do Manual Bentley (PLAXIS 3D Tutorial Manual)

| Script | Exemplo | Resultado |
|---|---|---|
| `bentley_caso_a.py` | Tutorial 1 - Case A: Rigid foundation (prédio como volume Linear Elástico não poroso, só peso próprio) | Uz = -102,6 mm no centro da sapata (manual: ~110 mm no centro do prédio) |

Não pergunta nada além da senha: os dados estão no topo do arquivo. Usa o `construir()` validado do
`../../plaxis_sapata_interativo.py` e roda o `../../plaxis_sapata_resultados.py` em seguida.
Saídas na própria pasta: `Bentley_Caso_A.p3d`, `ultimo_modelo.json`, `sapata_peso_proprio.csv`.

Próximo: Case B (radier com subsolo) está em `subsolo/` (em desenvolvimento).

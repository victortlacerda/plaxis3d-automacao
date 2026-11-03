# SoilTest: scripts de descoberta

Scripts usados para mapear a API de scripting do SoilTest antes do script automático. Ficam como referência de
como cada nome de atributo foi descoberto; o resultado está em [`../docs/referencia-soiltest.md`](../docs/referencia-soiltest.md).

| Arquivo | O que descobre |
|---|---|
| `soiltest_descoberta.py` | Objetos e comandos expostos pelo servidor do SoilTest |
| `soiltest_passo2.py`, `soiltest_passo3.py` | Atributos e resultados de cada ensaio (Triaxial, Oedometer, CRS, DSS, CDSS, CycTriaxial, General) |
| `soiltest_material.py` | Atributos do material visto pelo SoilTest, por modelo |
| `plaxis_criar_material_soiltest.py` | Primeira versão do fluxo "criar material no Input e abrir o SoilTest" (HS e HS small) |
| `plaxis_soiltest_modelos.py` | Todas as combinações modelo × drenagem: número do SoilModel, atributos, triaxial, edômetro e pré-adensamento |

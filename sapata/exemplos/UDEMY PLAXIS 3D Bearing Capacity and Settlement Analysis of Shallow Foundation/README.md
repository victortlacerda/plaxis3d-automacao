# UDEMY - PLAXIS 3D Bearing Capacity and Settlement Analysis of Shallow Foundation (Nichirvan Taher)

Scripts não interativos dos exemplos do curso (parâmetros no topo de cada arquivo). Validados no PLAXIS 3D 2024.2.

| Script | Exemplo do curso | Resultado |
|---|---|---|
| `nichirvan_taher_exemplo1_modelo.py` + `_resultados.py` | Itens 2 a 5: capacidade de carga última (qu). Sapata 1,0 x 1,0 x 0,5 m, carga de 1000 kN/m², malha fine com coarseness 0,1 na sapata | qu = 792 kN/m² (tangentes) |
| `nichirvan_taher_exemplo2_modelo.py` + `_resultados.py` | Item 6: tensão admissível por recalque. Sapata 3,0 x 3,0 m, deslocamento prescrito de 2,5 cm | 3162,8 kN / 351,4 kN/m² com domínio 20 x 20 m (curso: 3173 kN / 352,5 kN/m²) |

Observações: a espessura de 0,8 m do Exemplo 2 não aparece no texto das anotações; com domínio 10 x 10 m a força
sai ~10% menor (ajuste `XMIN ... YMAX` para -10 ... 10 para reproduzir o curso).

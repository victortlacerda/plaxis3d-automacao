---
name: plaxis3d-automacao-python
description: Automatizar o PLAXIS 3D 2024.2 por Python (executor externo): sapatas, radier e subsolo, com scripts interativos, testes por mock e script de resultados. Usar em projetos PLAXIS 3D com g_i/s_i.
---

# Automação do PLAXIS 3D por Python (sapatas, radier, subsolo)

Instruções acumuladas de um trabalho real com um engenheiro geotécnico brasileiro (português, UTC-3).
Cópia da skill do Claude; os scripts de referência estão neste repositório.

## Ambiente
- Os scripts rodam por um **executor externo** (`plaxis_script_runner.py` + .bat) que conecta no PLAXIS Input em
  `localhost:10000` e faz `exec` do `.py` com `s_i` e `g_i` definidos. **Não perguntar a porta do Input** nesse caso;
  só se `g_i` não existir.
- A senha do servidor é pedida a cada execução (`PLAXIS_PASSWORD` global/ambiente, senão `getpass`).
- A porta do Output vem do PLAXIS: `g_i.selectmeshpoints()` (modelo) ou `g_i.view(fase)` (resultados);
  conectar com `new_server("localhost", porta, password=senha)`.
- Os scripts gravam `ultimo_modelo*.json` na própria pasta para o script de resultados.

## Regras de ouro
1. **Nunca alterar o que já foi validado no PLAXIS real**: funções novas entram como módulos/opções com padrão
   equivalente ao anterior (Enter em tudo = mesmo comportamento).
2. **Provar a não regressão** com o mock: `tests/regressao.sh` compara os logs de comandos com as linhas de base.
3. Marcar tudo que não foi validado como **"[não testado]"**, no script e na resposta.
4. Nomes desconhecidos de comandos/propriedades: pedir o **histórico de comandos** do PLAXIS depois de o usuário
   fazer o passo na interface (fonte mais confiável) e/ou o `echo()` do objeto.
5. Scripts interativos: Enter aceita o padrão; aceitar vírgula ou ponto; validar entradas; avisar sobre bordas
   muito próximas (< 2 × maior lado).
6. Em modelos grandes, não abortar na primeira falha: registrar, imprimir `echo()`, continuar e listar o que faltou.

## Funções auxiliares
`perguntar_*`, `primeiro(res)`, `tentar(descricao, *alternativas)`,
`definir_props(obj, descricao, [(nomes, valores), ...])` (uma propriedade por vez; `echo()` na falha),
`setar_attr`, `nome_obj`, `ativar` por nome, `verificar_conexao()` (leitura inofensiva no início).

## Receitas VALIDADAS no PLAXIS real (2024.2)
```python
s_i.new()
g_i.setproperties("Title", t, "UnitForce","kN","UnitLength","m","UnitTime","day","WaterWeight",10.0)
g_i.SoilContour.initializerectangular(xmin, ymin, xmax, ymax)
bh = g_i.borehole(xmin, ymin); bh.Head = cota_NA
g_i.soillayer(espessura)                              # uma por camada, de cima para baixo
mat = g_i.soilmat()   # Identification, SoilModel 2, DrainageType "Drained", gammaUnsat, gammaSat, Eref, nu, cref, phi, psi
g_i.Soillayers[i].Soil.Material = mat
pm = g_i.platemat()   # Identification, MaterialType "Elastic", Isotropic True, gamma, d, E1, StructNu12
g_i.gotostructures()
poly = primeiro(g_i.surface((x,y,z),(x,y,z),(x,y,z),(x,y,z)))
placa = g_i.plate(poly); placa.Material = pm
carga = g_i.surfload(poly); carga.sigz = -q
desl = g_i.surfdispl(poly)  # Displacement_x/y "Free", Displacement_z "Prescribed"; desl.uz = -0.025
res = g_i.extrude(poly, 0, 0, -d)    # devolve [Volume_1, Soil_2]; depois g_i.delete(poly)
g_i.gotomesh()                       # refino: set Polygon_1_1.CoarsenessFactor (confirmar lendo de volta)
g_i.mesh(fator)   # very coarse 0.1, coarse 0.075, medium 0.05, fine 0.035, very fine 0.025
porta = g_i.selectmeshpoints(); s_o, g_o = new_server("localhost", porta, password=senha)
g_o.addcurvepoint("node", x, y, z); g_o.update()
g_i.gotostages(); g_i.InitialPhase.DeformCalcType = "K0 procedure"
fase = g_i.phase(anterior); fase.Identification = "Footing"; fase.Deform.ResetDisplacementsToZero = True
g_i.activate(g_i.Plate_1, fase)                    # objeto buscado pelo nome
g_i.setmaterial(Volume_1, fase, material)          # material do volume numa fase
fase.Deform.setproperties("UseDefaultIterationParams", False)
fase.Deform.setproperties("MaxLoadFractionPerStep", 1.0/n)    # mais pontos na curva
g_i.calculate(); fase.LogInfo.value                # 0 = sucesso
g_i.save(caminho)
```
Output: `g_i.view(g_i.Phases[-1])` → porta; `g_o.Phases[-1].Steps.value`; `g_o.getcurveresults(no, passo, g_o.ResultTypes.Soil.Uz)`;
`passo.Reached.SumMstage`; `passo.Reached.ForceZ` (por passo, deslocamento prescrito; conferir com
`ResultTypes.PrescribedDisplacement.ReactionForceZ` no último passo; `getresults` só em passos guardados).

## Erros conhecidos
- `MaterialName` não existe: usar `Identification`; Poisson da placa é `StructNu12`; `Distribution_z` não existe.
- Coarseness em `Polygon_1_1` (modo Mesh) e **ler de volta**: um `setattr` sem erro pode ser falso positivo.
- `getresults` em passo não guardado: "Phase has not been previewed or calculated yet" → usar `Reached.Force*`.
- `extrude` devolve dois objetos (Volume_1, Soil_2): atribuir no primeiro que aceitar.
- `WinError 10061` em `s_i.new()`: o servidor do PLAXIS Input parou; conferir e reiniciar o executor.
- Domínio pequeno subestima a força (10 × 10 deu ~10% menos que 20 × 20).
- Critérios de 10% de B e 25 mm só para carga vertical para baixo.

## Validações conseguidas
Exemplo 1 (1 × 1 × 0,5 m, 1000 kN/m²); Exemplo 2 (3 × 3 × 0,8 m, 2,5 cm: 3162,8 kN contra 3173 kN do PDF);
Caso A do manual Bentley (volume linear elástico não poroso, γ 50, E 3·10⁷, ν 0,15, só peso próprio):
Uz = -102,6 mm no centro da sapata (~110 mm máximo no manual).

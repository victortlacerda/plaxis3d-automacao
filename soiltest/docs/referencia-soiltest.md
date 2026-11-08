# PLAXIS SoilTest – referência resumida de comandos e objetos

Fonte: Commands Reference do PLAXIS 3D (seção "SoilTest tool"), extraído das páginas HTML locais do usuário.
Isto cobre comandos e objetos. O manual não diz como abrir o servidor de scripting do SoilTest nem qual porta ele usa.

## Ensaios (objetos)
Triaxial, CycTriaxial, Oedometer, CRS, DSS, CDSS, PMT (só Hardening Soil drenado), General.

| Ensaio | Propriedades principais |
|---|---|
| Triaxial | Behaviour (Drained/Undrained), Direction (compressão/extensão), Consolidation (Isotropic/K0), K0, CellPressure, MaximumStrain (%), Steps, PreconsolidationPressure, ApplyMobilisedShearStrength, MobilisedShearStrength |
| CycTriaxial | Behaviour, Consolidation, K0, CellPressure, InitialAxialStressinc, NumberOfCycles, NumberOfStepsPerQuarterCycle, DurationPerCycle, TestControlType (stress/strain), AxialStrainAmplitude |
| Oedometer | PreconsolidationPressure, PhaseTable[n].Duration (dia) / .Siginc / .Steps |
| CRS | PreconsolidationPressure, PhaseTable[n].Duration / .Epsinc / .Steps |
| DSS | Behaviour, Consolidation, K0, PreconsolidationPressure, AbsSigyyEinit, MaximumShearStrain (%), Steps |
| CDSS | Behaviour, Consolidation, K0, AbsSigyyinit, InitialStaticShear, NumberOfCycles, NumberOfStepsPerQuarterCycle, DurationPerCycle, TestControlType, ShearStrainAmplitude / ShearStressAmplitude |
| General | Behaviour, Sigxxinit/Sigyyinit/Sigzzinit + tensões de cisalhamento iniciais, PhaseTable[n].Duration / .Steps, CyclicPhases |

Somente leitura: Error=0.01, Relax=1.0, Iteration=50, ArcLength=False.

## Resultados (`<Ensaio>.Results.<campo>`, lista por passo)
Time, Epsxx/Epsyy/Epszz, Gamxy/Gamyz/Gamzx, SigxxE/SigyyE/SigzzE (efetivas), Sigxy/Sigyz/Sigzx, SigxxT/SigyyT/SigzzT (totais), PTotal/PExcess/PActive, Eps1/Eps2/Eps3, TotalVolumetricStrain, SigmaEffective1/2/3, MeanEffStress (p'), DeviatoricStress (q), DeviatoricStressT (|σ'1−σ'3|), DeviatoricStrain, MobilizedShearStrength, MeanTotStress.

## Comandos (escopo SoilTest)
- Ensaio: `calculate <Ensaio>`, `addphase`, `insertphase`, `deletephase <linha>`, `markphasescyclic`, `deletecyclicphases`
- Propriedades: `set <Obj.Prop> <valor>`, `setproperties <Obj> "Prop" valor ...`, `multiply`, `apply <lista> "setproperties" "Prop" valor`
- Leitura: `echo [Obj]`, `echo Triaxial.Results.Eps1`, `index <Obj.Results.Campo> <i>`, `info`, `commands`, `filter`
- Material: `validate <Material> ["errors"|"warnings"|"all"]`, `rename`
- Arquivo/sessão: `save <Ensaio> "<caminho>.stt.plxml"`, `close`, `undo`, `redo`
- No Input: `soiltest <Material>` abre o SoilTest para o material.

## Em aberto
- Porta/senha do servidor de scripting do SoilTest e como ativá-lo.
- Como o plxscripting devolve `echo` e os campos de `Results` (lista, string?). O script `soiltest_descoberta.py` investiga isso.

## Confirmado na prática (relatório do passo 1, SoilTest na porta 10000)
- O servidor do SoilTest responde ao `plxscripting` na porta 10000. `new_server` devolve `Server` e `PlxProxyGlobalObject` (`g`).
- `g` expõe `Triaxial`, `CycTriaxial`, `Oedometer`, `CRS`, `DSS`, `CDSS`, `General`, `Material` e `Tests`. `PMT` e `index` não aparecem.
- Comandos globais disponíveis como métodos: `calculate` (`ca`), `set`, `setproperties` (`sps`), `multiply` (`mul`), `apply`, `echo`, `info`, `commands`, `validate` (`val`), `save` (`sv`), `close`, `rename`, `undo`, `redo`, `unassign`, `getmetadata`, `setmetadata`.
- `addphase`, `insertphase`, `deletephase`, `markphasescyclic` e `deletecyclicphases` existem em cada ensaio (`g.Oedometer.addphase()`), não em `g`.
- `echo()` e `info()` devolvem texto (`str`). Propriedades numéricas e enums são objetos com `.value` (ex.: `Triaxial.CellPressure.value` = 100; `Behaviour.value` 0 = Drained).
- Valores iniciais do Triaxial: CellPressure 100, MaximumStrain 10 (%), Steps 100, K0 1, Sigxxinit/Sigyyinit/Sigzzinit = -100.
- No DSS o nome real é `AbsSigyyinit` (o manual escreve `AbsSigyyEinit`).
- Tabelas de fases: `Oedometer.PhaseTable` (Duration, Siginc, Steps) e `CRS.PhaseTable` (Duration, Epsinc, Steps).
- Ainda não confirmado: como ler `Results.<campo>` e como editar o `Material` (modelo e parâmetros). Passo 2: `soiltest_passo2.py`.

## Confirmado no passo 2 (Triaxial calculado no SoilTest real)
- Fluxo que funciona: `g.Material.setproperties("ERef",..,"nu",..,"cRef",..,"phi",..,"psi",..)` → `t.setproperties("Behaviour","Drained","CellPressure",100,"MaximumStrain",15,"Steps",50)` → `g.validate(g.Material)` ("The material definition is valid.") → `g.calculate(t)` ("OK").
- Material padrão da sessão: Mohr-Coulomb (SoilModel 2), ERef 160000 kN/m², nu 0.3, cRef 10 kN/m², phi 25°, psi 0°, TensionCutOff True. Atributos: ERef, nu, cRef, phi, psi, TensileStrength, TensionCutOff, SoilModel, Identification.
- `Results.<campo>` é iterável: `[float(v) for v in t.Results.Epsyy]` (também `len()`, `obj[i]`, `obj.echo()`). Há 1 ponto a mais que os passos (Steps=50 → 51 valores, o primeiro é o estado inicial).
- Sinais: compressão negativa. Epsyy = −0.15 para 15 %; SigyyE/SigxxE negativas; DeviatoricStress (q) positivo; MeanEffStress negativo. Epsyy e volumétrica vêm em fração (não %).
- `Time` vem zerado e `PActive` vazio no ensaio drenado.
- `K0` é somente leitura quando `Consolidation` é Isotropic: não incluí-lo no `setproperties` nesse caso.
- Validação: q de ruptura simulado (177,785 kPa) = solução fechada Mohr-Coulomb para σ3 = 100 kPa, c = 10, φ = 25°.
- Scripts: `soiltest_descoberta.py`, `soiltest_passo2.py`, `soiltest_triaxial.py` (driver com CSV/PNG/JSON e comparação com laboratório). Rodam pelo Executar_script_PLAXIS.bat.

## Confirmado no passo 3 (SoilTest 2024.2, outros ensaios)
- **`Material.SoilModel` é somente leitura.** O modelo é o do material com que o SoilTest foi aberto (o comando `soiltest <Material>` no Input). Para usar HS ou HS small, abrir o SoilTest a partir de um material nesse modelo (ou trocar o material na interface do SoilTest) e então rodar `soiltest_material.py`. Parâmetros do Mohr-Coulomb editáveis: ERef, nu, cRef, phi, psi.
- Os comandos enviados por script aparecem no histórico da linha de comando do SoilTest (`0001> ...`; falhas aparecem como `!!!!> ...`). Isso ajuda a depurar.
- **Oedometer**: `t.PhaseTable[i].setproperties("Duration", d, "Siginc", s, "Steps", n)`. Siginc em kPa, negativo = compressão, incremento da fase. `t.addphase()` / `t.deletephase(i)` adicionam/removem linhas. Conferido: Siginc −100 kPa → Epsyy = −0,000464 = 100/E_oed (E_oed = 215385 kPa) e SigxxE/SigyyE = K0 elástico = ν/(1−ν) = 0,4286.
- **CRS**: PhaseTable com Duration, **Epsinc (em %, incremento total da fase)**, Steps. Conferido: Epsinc −0,05 → Epsyy final −0,0005 e SigyyE −107,69 kPa = E_oed × 0,0005.
- **DSS**: `AbsSigyyinit` (kPa) já ajusta Sigxxinit/Sigyyinit/Sigzzinit; `MaximumShearStrain` em %; Gamxy sai em fração. Conferido: τ máx = 51,32 kPa = c·cosφ + p·senφ (isotrópico, p = 100).
- **CDSS e CycTriaxial**: `NumberOfCycles`, `NumberOfStepsPerQuarterCycle`, `DurationPerCycle`, `TestControlType` ("Strain"), `ShearStrainAmplitude`/`AxialStrainAmplitude` em %. Ao definir os ciclos, o SoilTest cria as fases (6 fases para 2 ciclos). Pontos = (4 × ciclos + 1) × passos por quarto + 1 (91 para 2 ciclos × 10; 261 para 3 × 20): os primeiros "passos por quarto" pontos são uma fase inicial sem carga; depois vêm os ciclos completos, que começam e terminam em zero (corrigido no passo 11). Gamxy/Epsyy oscilam ±0,005 para amplitude 0,5 %.
- **General**: sem PhaseTable; as fases são `Phases[i]` com Steps, Duration, Sigxxinc…Sigzxinc, Epsxxinc…Gamzxinc e BoundaryCondition{xx,yy,zz,xy,yz,zx} (0 = FixedStrain). Ainda não calculado.
- `Time` fica zerado no Triaxial/DSS e avança (0 a Duration) no Oedometer/CRS/CDSS/CycTriaxial.
- Scripts: `soiltest_ensaios.py` (Oedometer, CRS, DSS), `soiltest_material.py` (descoberta por modelo), `soiltest_triaxial.py`.

## Confirmado no passo 4 (criar material no Input e abrir o SoilTest por script)
- No Input (porta 10000): `m = g_i.soilmat()`; `m.setproperties("Identification","HS_teste")`; `m.setproperties("SoilModel", 3)` (3 = Hardening Soil); `m.setproperties("DrainageType","Drained")`. Em seguida os parâmetros.
- **`g_i.soiltest(m)` não trava e devolve a porta do servidor do SoilTest** (int, ex.: 10001). O SoilTest abre já com o material (echo mostra `Identification: "HS_teste"`, `SoilModel: Hardening Soil (3)`, `validate` OK). O Input fica em 10000 e o SoilTest em outra porta; os scripts de ensaio devem se conectar nessa porta (`new_server("localhost", porta, password=...)`), não usar o `g_i` do executor.
- Nomes dos atributos do material HS no Input: `E50Ref, EOedRef, EURRef, PowerM (expoente m), cRef, phi, psi, nuUR, pRef, K0NC, RF, TensionCutOff, TensileStrength, K0Determination, OCR, POP, UseDefaults, DrainageType, gammaUnsat, gammaSat`. No SoilTest o echo do Material mostra E50Ref, EOedRef, EURRef, nuUR, PowerM, pRef, cRef, phi, psi, TensionCutOff, TensileStrength, K0NC, RF.
- **`RF` (e `K0NC`) são somente leitura enquanto `UseDefaults` = True** (RF = 0,9 e K0NC automático = 1 − sen φ). O script tenta `UseDefaults False` antes; ainda não verificado se isso libera os dois.
- Material HS de teste (E50ref 40000, Eoedref 40000, Eurref 120000, m 0,5, c 1, φ 35, ψ 5, νur 0,2, pref 100): triaxial drenado, σ3 = 100, 15 %: q_max 272,877 kPa, q final 272,859 = q_f de Mohr-Coulomb (272,86). Contração inicial (εv mín −0,0025) seguida de dilatação (εv final +0,022).
- Ainda não visto: nomes dos parâmetros do HSsmall no Input (G0Ref, gamma07?), triaxial não drenado com material `DrainageType` Drained, e o Oedometer com HS.
- Scripts: `plaxis_criar_material_soiltest.py` (cria material + abre SoilTest + verifica), `plaxis_soiltest_auto.py` (fluxo completo com entrada interativa, triaxiais por pressão confinante, edômetro, CSV/PNG/JSON).

## Confirmado no passo 5 (descoberta de modelos, rodada 1: SoilTest 2024.2 + Input)
- **Mapa SoilModel (Input):** 0 None, 1 Linear Elastic, 2 Mohr-Coulomb, 3 Hardening Soil, 4 HS small, 5 Soft Soil, 6 Soft Soil Creep, 7 Jointed Rock, 8 Modified Cam-Clay, 9 NGI-ADP, 10 Hoek-Brown, 11 Sekiguchi-Ohta Inviscid, 12 Sekiguchi-Ohta Viscid, 13 Concrete, 15 UDCAM-S (14 e 16 recusados). `setproperties("SoilModel", n)` aceita o número.
- **DrainageType:** aceita número ou nome ("Undrained A", "Undrained (A)"). O echo mostra `Undrained A (1)`, `Undrained B (2)`, `Undrained C (3)`, `Non-porous (4)`, `Drained (0)`. Opções por modelo na interface: MC = D, UA, UB, UC, NP; LE = D, UA, UC, NP; HS e HS small = D, UA, UB; MCC e Soft Soil = D, UA.
- **Cada `g_i.soiltest(mat)` abre uma nova janela do SoilTest em porta nova** (10002, 10003, ...). Feche as janelas ao terminar.
- **Atributos por modelo (Input):**
  - MC (D/UA/NP): ERef, nu, cRef, phi, psi (+ TensileStrength, TensionCutOff, EInc, cInc).
  - MC UB: ERef, nu, **sURef**, phiU (padrão 0), sUInc; `cRef`/`phi` não existem e `psi` é somente leitura.
  - MC UC: ERef, **nuU** (padrão 0, gera aviso "nu seems to be too low"; usar ~0,495), sURef, phiU; sem `nu`, `cRef`, `phi`.
  - LE: ERef, nu (UC: nuU).
  - HS / HS small: E50Ref, EOedRef, EURRef, PowerM, nuUR, pRef, cRef, phi, psi, K0NC, RF (RF e K0NC são somente leitura enquanto UseDefaults = True), DilatancyCutOff, eMin, eMax; HS small acrescenta G0Ref e gamma07.
  - MCC: **lambda, kappa**, M, nuUR, eInit, OCR, POP, K0NC, CInter, PhiInter, PsiInter. **O SoilTest recusa o material se PhiInter e CInter forem ambos zero** ("Both PhiInter and CInter are zero"); o material aparece como [Invalid] no Input.
- **SoilTest:** o `Behaviour` do Triaxial independe do DrainageType do material (o triaxial não drenado roda em material Drained). Em material Non-porous só vale "drained" (`Invalid value: "Undrained"`). `PreconsolidationPressure` é editável só em HS e HS small (somente leitura em MC e LE).
- **Sinal de PExcess:** segue o PLAXIS (compressão negativa), então a poropressão em excesso geotécnica é **du = −PExcess**. Conferido: MC não drenado, PExcess final −42,9 com Δp total = q/3 = 43,8; HS dilatante, PExcess mín −50,9 (contração inicial) e máx +605 (sucção na dilatação).
- **Validações numéricas (σ3 = 100 kPa, 15 %):** MC D c=5 φ=30: q_f 217,33 (teórico 217,32). MC UB/UC (su = 50): q = 100 = 2 su, igual em drenado/não drenado. LE: q = E·ε = 4500. HS e HS small drenados: q_f 272,88 (teórico 272,86). HS não drenado chega a q = 1902 kPa porque a sucção por dilatância não é limitada (DilatancyCutOff desligado, sem cavitação). Edômetro com 100 kPa: MC/LE ε = 0,002476 (K0 = ν/(1−ν) = 0,4286), HS 0,00437, HS small 0,00410.
- Script de descoberta ampliado: `plaxis_soiltest_modelos.py` (19 combinações modelo × drenagem, inclui Soft Soil e MCC com PhiInter).

## Confirmado no passo 6 (descoberta de modelos, rodada 2)
- **Dilatancy cut-off (HS e HS small) funciona no triaxial drenado e não altera o não drenado.** Com `DilatancyCutOff` = True, `eInit` = 0,5, `eMax` = 0,52 no material do Input: ε_v máx (dilatação) caiu de 0,02199 para 0,01339 no HS e de 0,02181 para 0,01379 no HS small (previsto: (eMax − eInit)/(1 + eInit) = 0,0133). No não drenado nada mudou (q_max 1901,73 kPa; PExcess máx +605,5), porque o volume quase não varia e o índice de vazios não chega a eMax. O Material do SoilTest **não expõe** `DilatancyCutOff`/`eInit`/`eMax`, mas o corte viaja com o material.
- **Resultado do SoilTest independe do DrainageType do material**, salvo UB/UC (resistência por su, `q = 2 su`) e Non-porous (só `Behaviour` "drained"). UA dá o mesmo que D.
- **MCC** (λ = 0,1, κ = 0,02, M = 1,2, eInit = 1, σ3 = 100): drenado q_max 183,99 kPa (estado crítico teórico 3Mσ3/(3−M) = 200, o ensaio de 15 % não chega lá); não drenado q_f 68,72 kPa (teórico normalmente adensado M·p0'/2^((λ−κ)/λ) = 68,9) e PExcess mín −65,6. `PreconsolidationPressure` é editável. **O edômetro do MCC parte de tensão zero e dá ε = 27 % para 100 kPa** (não representativo).
- **Soft Soil** (SoilModel 5): atributos `lambdaModified` e `kappaModified` (λ* e κ*; exige λ* > κ* > 0; com zeros o SoilTest recusa o material), cRef, phi, psi, nuUR, `M` (calculado), K0NC, OCR, POP. Não tem `PhiInter`. Os nomes `lambda`/`kappa` valem só para o MCC.
- **MC UC/LE UC:** com `nuU` = 0,495 o edômetro dá ε = 9,87e-5 (E_oed muito alto) e σh = 0 reportado quando nuU = 0; PExcess = 0 (análise em tensões totais).
- Edômetro 100 kPa: MC e LE (D/UA/NP) ε = 0,002476; HS 0,00437; HS small 0,00410; HS UB 0,001116; HS small UB 0,000785.
- Scripts: `plaxis_soiltest_auto.py` agora escolhe qualquer modelo × drenagem (menu), cria o material, abre o SoilTest, roda triaxiais e edômetro e compara com soluções teóricas; `plaxis_soiltest_modelos.py` continua sendo a descoberta (21 combinações).

## Confirmado no passo 7 (Soft Soil, rodada 3)
- Soft Soil roda no SoilTest com `lambdaModified` = 0,1, `kappaModified` = 0,02, cRef = 1, phi = 25, psi = 0, nuUR = 0,15. O Material do SoilTest expõe `lambdaModified`, `kappaModified`, `nuUR`, `cRef`, `phi`, `psi`, `K0NC` e `M` (M é calculado: 1,362 com K0NC = 0,577). Não há `PhiInter`.
- Triaxial σ3 = 100 kPa, 15 %: drenado q_max 149,54 kPa = q_f de Mohr-Coulomb (149,53); contração volumétrica 7,4 %. Não drenado q_max 74,06 kPa e PExcess −51,6 (acréscimo de 51,6 kPa). A fórmula M·p0'/2^((λ*−κ*)/λ*) dá 78,2 kPa (5 % acima; não verificado se o ensaio de 15 % chegou ao fim da curva ou se a superfície de ruptura/cap do Soft Soil explica a diferença).
- `PreconsolidationPressure` é editável no Soft Soil. O edômetro parte de tensão zero e dá ε = 42,6 % em 100 kPa (não representativo), como no MCC.
- UA e D dão resultados idênticos, como nos outros modelos.

## Passo 8 (teste real do `_auto.py` + nova versão com mais ensaios)
- **Rodada real do usuário (2026-10-29), `plaxis_soiltest_auto.py`, Mohr-Coulomb drenado** (E' = 30000, ν' = 0,3, c' = 10, φ' = 30, ψ = 0; σ3 = 50/100/200): q_max 134,647 / 234,652 / 434,658 kPa contra q_f teórico 134,641 / 234,641 / 434,641; dilatação 0 %. Edômetro de 6 fases × 10 passos: 61 pontos (= soma dos passos + 1), σv máx 400 kPa, ε_v máx 0,9905 % = 400/E_oed (E_oed = 40384,6). O SoilTest abriu na porta 10001 e o valor digitado com vírgula (",3") foi aceito.
- **Nova versão do `_auto.py` (testada só em mock; falta rodar no PLAXIS):**
  - **Um PNG por gráfico** em `graficos/` (antes eram figuras 2×2). Triaxial: q×ε_a, ε_v×ε_a, du×ε_a, trajetória p'-q. Edômetro/CRS: σ_v×ε_v e ε_v×log σ_v. DSS: τ×γ, ε_v×γ, du×γ, trajetória σ_v'-τ. CDSS e triaxial cíclico: laços, deformação × tempo, tensão × tempo, du × tempo, trajetória. Gráficos de du são omitidos quando não há poropressão.
  - **Novos ensaios:** CRS (`Epsinc` em %, total da fase), DSS (`AbsSigyyinit`, `MaximumShearStrain`, `Steps`), CDSS e CycTriaxial (atributos já confirmados no passo 3: `TestControlType`, `ShearStrainAmplitude`/`AxialStrainAmplitude`, `NumberOfCycles`, `NumberOfStepsPerQuarterCycle`, `DurationPerCycle`; para controle de tensão `ShearStressAmplitude`/`AxialStressAmplitude`, nomes vistos na lista de atributos mas ainda não calculados). Pontos de um ensaio cíclico = (4 × ciclos + 1) × passos por quarto + 1 (confirmado: 91 e 261).
  - **Métricas do último ciclo:** módulo secante (G_sec no CDSS, E_sec no triaxial cíclico = amplitude de q / amplitude de ε_a) e amortecimento D = área do laço / (4π·Ws), Ws = 0,5·τ_a·γ_a. Conferência teórica só para Linear Elastic: G = E/(2(1+ν)); triaxial drenado E; triaxial não drenado 3G.
  - **Consolidação K0** (Triaxial, DSS, CDSS, triaxial cíclico): `Consolidation` = "K0" e depois `K0` (valor; é somente leitura enquanto a consolidação é isotrópica, então vai numa chamada separada). K0 automático: K0nc do material; no MCC 1 − sen φcs com sen φcs = 3M/(6+M); com φ' a fórmula de Jaky 1 − sen φ'; sem φ', ν/(1−ν). O script lê `Sigxxinit`/`Sigyyinit` depois de configurar para mostrar as tensões iniciais reais e usa σ3 = −Sigxxinit nas checagens teóricas.
  - **Pré-adensamento:** modo "pressao" (σ'p em kPa) ou "OCR" (σ'p = OCR × σ'v0, com σ'v0 lida de `Sigyyinit` no triaxial/cíclico e igual a `AbsSigyyinit` no DSS/CDSS). OCR não se aplica ao edômetro/CRS (partem de tensão zero). Só HS, HS small, MCC e Soft Soil; MC e LE ignoram (somente leitura). Não foi verificado se o SoilTest lê `OCR`/`POP` do material; por isso o OCR é convertido em `PreconsolidationPressure` do ensaio.
- **A verificar no PLAXIS real:** (1) se `CellPressure` no triaxial com K0 é σx (o script lê `Sigxxinit`/`Sigyyinit` e mostra); (2) se o valor "K0" de `Consolidation` é aceito no DSS/CDSS/CycTriaxial; (3) os atributos de controle de tensão dos ensaios cíclicos; (4) se `PreconsolidationPressure` aceita 0 ao restaurar; (5) triaxial/DSS não drenados cíclicos (poropressão acumulada).

## Passo 9 (rodada real do `_auto.py` v3: Linear Elastic drenado, 2026-10-30)
Todos os ensaios rodaram (E' = 30000, ν' = 0,3; consolidação isotrópica; σ = 50 triaxial/DSS, 100 cíclicos; 3 ciclos × 20 passos, amplitude 0,5 %):
- Triaxial: q_max 4500 kPa = E·ε (15 %). Edômetro: ε_v 0,9905 % em 400 kPa. CRS (−5 %, 50 passos): 51 pontos, σ_v 2019,23 kPa = E_oed × 5 %.
- DSS (10 %): τ_max 1153,85 kPa = G·γ, G = E/(2(1+ν)) = 11538,46.
- CDSS: G_sec 11538,5 kPa (teórico 11538,46), amplitude 57,69 kPa = G × 0,005, amortecimento 0 %. Triaxial cíclico: E_sec 30000 kPa, amortecimento 0 %.
- Os atributos dos ensaios cíclicos em controle de **deformação** estão confirmados em execução real. Consolidação K0, pré-adensamento, controle por tensão e cíclicos não drenados continuam sem teste real.
- Com consolidação isotrópica, `Sigxxinit`/`Sigyyinit` lidos do ensaio dão σx = σy = pressão informada (K = 1), tanto no triaxial quanto no DSS/CDSS/CycTriaxial.

## Passo 10 (rodada real: HS drenado com consolidação K0 e pré-adensamento por OCR, 2026-10-30)
Parâmetros: E50ref = Eoedref = 40000, Eurref = 120000, m = 0,5, νur = 0,2, pref = 100, c' = 1, φ' = 35, ψ = 5, corte de dilatância ligado (eInit 0,5; eMax 0,52). Triaxial drenado, σ3 = 50/100/200 kPa, 15 %, consolidação K0 = 0,5, OCR = 2.
- **K0 confirmado no triaxial:** `Consolidation` = "K0" seguido de `setproperties("K0", 0.5)` é aceito. `CellPressure` é a **tensão lateral efetiva σ'x**: com CellPressure = 50 o SoilTest dá σ'y = 100 e σ'x = 50 (K = 0,500); para 100 e 200 idem (σ'y = 200 e 400). A leitura de `Sigxxinit`/`Sigyyinit` funciona.
- **Pré-adensamento por OCR confirmado:** `PreconsolidationPressure` = OCR × σ'y0 (200, 400, 800 kPa) é aceito no HS, e o restaurar para 0 também.
- **Resistência:** q_max 138,359 / 272,877 / 541,913 kPa contra q_f Mohr-Coulomb 138,351 / 272,859 / 541,876 (σ3 = σ'x). K0 e OCR não mudam q_f no HS, como esperado (a ruptura é Mohr-Coulomb).
- **Corte de dilatância no K0 + OCR:** dilatação máx. 1,357 / 1,340 / 1,334 %; o previsto é (eMax − eInit)/(1 + eInit) = 1,333 %.
- **Ainda sem teste real:** K0 no DSS, CDSS e triaxial cíclico; o efeito do OCR na rigidez inicial (falta uma rodada normalmente adensada para comparar); controle por tensão; cíclicos não drenados.

## Passo 11 (bateria real de 08/11/2026, rodada por controle remoto do PC)
Bateria `soiltest_bateria.py`, 5 casos, sem erros:
- **Cíclicos não drenados (MC, c' = 5, φ' = 30, ψ = 0, σ = 100 kPa, ±0,5 %, 5 ciclos):** rodam. CDSS: Δu = 0 e σ'v constante; é o correto para MC com ψ = 0, porque cisalhamento simples não tem tendência volumétrica (elástica nem plástica). Triaxial cíclico: Δu oscila (+26,1 em extensão, −13,4 em compressão) com laços estáveis (E_sec 22410 kPa, amortecimento 22,3 %), sem acumular. **O MC não acumula poropressão em ciclos**: para isso é preciso modelo com contração plástica (HS small, MCC, Soft Soil ou modelos de liquefação).
- **Controle por tensão:** `ShearStressAmplitude` e `AxialStressAmplitude` aceitos. Amplitudes saem exatas (τ = 20 kPa, q = 50 kPa). Drenado elástico: G = 11538,5, E = 30000. Não drenado: E_u = 34500 kPa = 2G(1 + ν_u) com ν_u = 0,495; Δu = ±16,30 kPa ≈ Δp = q/3 = 16,67 (B ≈ 0,98 pela água compressível). **O triaxial cíclico por tensão começa em extensão** (q = −50 no primeiro meio ciclo).
- **K0 no DSS, CDSS e triaxial cíclico:** aceito. DSS/CDSS: σ'y = AbsSigyyinit = 100, σ'x = 50. Triaxial cíclico: CellPressure = σ'x = 100, σ'y = 200. G e E iguais aos do isotrópico (LE).
- **Ordem dos pontos nos cíclicos:** os primeiros `NumberOfStepsPerQuarterCycle` pontos são fase inicial (γ = 0 e tempo = 0); depois os ciclos começam em zero e terminam em zero. 5 ciclos × 20 = 421 pontos. Tempo final = ciclos × DurationPerCycle, na unidade de tempo do projeto (o projeto usa `UnitTime "day"`, logo **dia**).
- **HS normalmente adensado × OCR = 2 (K0 = 0,5, σ3 = 100):** mesma resistência (272,877 kPa). Início da curva só um pouco mais rígido com OCR: q em ε_a = 0,15 % passa de 139,4 para 144,0 kPa (+3 %); em 1 %, de 228,0 para 231,7. No HS o pré-adensamento age sobretudo no cap (compressão volumétrica), não na rigidez de cisalhamento do triaxial; para ver o efeito do OCR no HS, usar edômetro ou CRS com σ'p.

## Passo 12 (bateria 2 real, 08/11/2026): cíclicos com modelos contráteis e OCR no edômetro/CRS
Cíclico não drenado por deformação, ±0,2 %, 10 ciclos, σ = 100 kPa, valores de teste do script. Δu ao fim de cada ciclo (deformação de volta a zero):
- **HS small (ψ = 5°):** CDSS sobe a +14,9 kPa no 2º ciclo e depois inverte até −34,1 (σ'v de 100 → 134); triaxial cíclico vai a −143,5 kPa (p' 100 → 204). Contrai no início e depois **dilata**: com ψ > 0 o HS small gera poropressão negativa. Laços histeréticos reais (amortecimento 16 % no CDSS, 26 % no triaxial).
- **MCC (normalmente adensado):** Δu salta no 1º ciclo (CDSS 3,78; triaxial 11,1 kPa) e **fica constante**: os ciclos seguintes ficam dentro da superfície de escoamento, em regime elástico, sem amortecimento.
- **Soft Soil:** CDSS igual ao MCC (1,94 kPa constante); triaxial cíclico acumula devagar, cerca de +0,5 kPa por ciclo (5,5 → 10,2).
- **Conclusão:** nenhum dos 6 modelos mapeados reproduz acúmulo progressivo de poropressão típico de ensaio cíclico (liquefação/degradação). Para isso são necessários modelos cíclicos próprios do PLAXIS (por exemplo UBC3D-PLM, PM4Sand, PM4Silt), ainda não mapeados neste projeto.

Edômetro (carga até 400 kPa) e CRS (−10 %), sem pré-adensamento × σ'p = 100 kPa:
- **MCC com σ'p = 100:** d(ε)/d(ln σ'v) = 0,0108 entre 25 e 50 kPa (teoria κ/(1 + e0) = 0,010) e 0,054–0,057 acima de 100 kPa (teoria λ/(1 + e0) = 0,050; cresce porque e diminui). Transição em σ'p, como esperado. ε em 400 kPa: 13,8 %.
- **MCC sem pré-adensamento:** parte de tensão zero e vira lixo numérico (ε = 18 % já em 25 kPa; CRS chega a só 6,4 kPa em 10 %). **No MCC, sempre informar σ'p no edômetro e no CRS.**
- **HS com σ'p = 100:** antes de 100 kPa deforma cerca de metade (inclinação 0,0008–0,0012 contra 0,0015–0,0021, recompressão mais rígida); acima de 100 kPa a inclinação é igual à do normalmente adensado (0,0029 e 0,0042). ε em 400 kPa: 0,743 % contra 0,930 %. Aqui o OCR do HS aparece claramente (no triaxial era só +3 %).
- O CRS saiu drenado (Δu = 0) nos dois modelos.

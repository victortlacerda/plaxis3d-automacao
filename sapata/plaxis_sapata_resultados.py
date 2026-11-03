# -*- coding: utf-8 -*-
"""
PLAXIS 3D - Sapata: resultados (curva carga x deslocamento e critérios de capacidade de carga).

Pré-requisito: plaxis_sapata_interativo.py já rodado (projeto calculado e aberto no PLAXIS Input).
Lê "ultimo_modelo.json" (gravado pelo script interativo, na mesma pasta deste script) para saber o
valor/unidade/direção da carga e a geometria da sapata. Sem o JSON, usa os valores do Exemplo 1.

Gera na mesma pasta deste script:
  - sapata_curva.csv                (SumMstage, carga, deslocamento [mm])
  - sapata_grafico_curva.png        (curva carga x deslocamento completa, sem critérios)
  - sapata_grafico_tangentes.png    (curva + retas tangentes + qu pela interseção)
  - sapata_grafico_10pctB.png       (somente carga vertical para baixo)
  - sapata_grafico_25mm.png         (somente carga vertical para baixo; Terzaghi e Peck, 1948)
E imprime um resumo dos critérios.

Quatro módulos (lidos do JSON, escritos por plaxis_sapata_interativo.py):
  - CARGA: curva = ΣMstage x carga aplicada (Exemplo 1, validado).
  - DESLOCAMENTO PRESCRITO: curva = força de reação lida do Output / área da sapata, contra o
    deslocamento do nó (Exemplo 2, validado).
  - COMBINADO (não testado): em sequência (fase Load e depois fase Displacement, mesma direção; a curva
    junta as duas fases, com força total = carga + reação) ou na mesma fase (eixos diferentes; curva
    pela reação do eixo prescrito).
  - SEM AÇÃO (não testado): só o peso próprio da sapata; não há curva nem critérios, apenas o
    recalque do nó sob a sapata na fase de construção (grava sapata_peso_proprio.csv).
  - CARGA com segunda carga (surface load + point load, não testado): a curva usa a carga total
    equivalente em kN/m² (soma das duas cargas / área da sapata).
Em todos os casos os mesmos critérios são aplicados à curva tensão x recalque.

Convenção: o deslocamento é positivo no sentido da carga (recalque positivo para baixo, para carga
vertical descendente; levantamento positivo para cima, para tração; etc.).
"""
import os
import json
import getpass

from plxscripting.easy import new_server

HOST = "localhost"
FS = 3.0                      # fator de segurança (qa = qu / FS)
FRACAO_B = 0.10               # critério: recalque = 10% de B
RECALQUE_ADM_MM = 25.0        # critério: recalque admissível (Terzaghi e Peck, 1948)
N_PONTOS_INICIAIS = 5         # pontos usados na tangente inicial
N_PONTOS_FINAIS = 5           # pontos usados na tangente final
DECIMAL_VIRGULA = True        # True: Excel em português (vírgula). False: ponto decimal
ZOOM = True                   # True: eixo focado na região de interesse; False: curva inteira

PASTA = os.path.dirname(os.path.abspath(globals().get("__file__", ".")))
ARQUIVO_JSON = os.path.join(PASTA, "ultimo_modelo.json")
CSV = os.path.join(PASTA, "sapata_curva.csv")
PNG_CURVA = os.path.join(PASTA, "sapata_grafico_curva.png")
PNG_TANGENTES = os.path.join(PASTA, "sapata_grafico_tangentes.png")
PNG_10B = os.path.join(PASTA, "sapata_grafico_10pctB.png")
PNG_25MM = os.path.join(PASTA, "sapata_grafico_25mm.png")
CSV_PESO = os.path.join(PASTA, "sapata_peso_proprio.csv")


def obter_senha():
    pw = globals().get("PLAXIS_PASSWORD") or os.environ.get("PLAXIS_PASSWORD")
    if not pw:
        pw = getpass.getpass("Senha do servidor PLAXIS: ")
    return pw


def valor(x):
    return x.value if hasattr(x, "value") else x


def mstage_do_passo(step):
    reached = step.Reached
    for nome in ("SumMstage", "SumMStage", "Mstage", "SigmaMstage"):
        if hasattr(reached, nome):
            return float(valor(getattr(reached, nome)))
    raise RuntimeError("Não achei SumMstage em step.Reached. Atributos: {}".format(
        [a for a in dir(reached) if not a.startswith("_")][:40]))


# ----------------------------------------------------------------------------
# Dados do modelo
# ----------------------------------------------------------------------------
if os.path.exists(ARQUIVO_JSON):
    with open(ARQUIVO_JSON, encoding="utf-8") as fh:
        M = json.load(fh)
    print(">>> Parâmetros lidos de", ARQUIVO_JSON)
else:
    print(">>> ultimo_modelo.json não encontrado: usando os valores do Exemplo 1 (1 x 1 m, 1000 kN/m2)")
    M = dict(carga=dict(valor=1000.0, unidade="kN/m2", direcao=1, tipo=1, componente="Uz", sinal=-1.0),
             sapata=dict(cx=0.0, cy=0.0, cz=0.0, L=1.0, W=1.0, B=1.0))

C, S = M["carga"], M["sapata"]
MODO = C.get("modo", "carga")
MODO_DESL = MODO in ("deslocamento", "combinado")
SEQ = (MODO == "combinado" and C.get("sub") == "sequencia")
P_KN = C.get("carga_kN")
DSIGN = -1.0 if C.get("direcao") == 1 else 1.0      # sentido do deslocamento prescrito no eixo
CARGA_TOTAL = float(C["valor"])
UNID = "kN/m²" if MODO_DESL else C["unidade"].replace("m2", "m²")
COMPONENTE = C.get("componente")
SINAL = float(C.get("sinal", -1.0))
B_SAPATA = float(S["B"])
VERTICAL_BAIXO = (C["direcao"] == 1)
AREA = float(S["L"]) * float(S["W"])
EXTRA = (MODO == "carga" and C.get("carga_total_kN") is not None)     # surface load + point load
UNID_CSV = C["unidade"]
if EXTRA:
    CARGA_TOTAL = float(C["carga_total_kN"]) / AREA      # kN/m² equivalente (as duas cargas crescem juntas)
    UNID = "kN/m²"
    UNID_CSV = "kN/m2"

if COMPONENTE is None:
    raise RuntimeError("Carga do tipo momento: este script ainda não extrai rotações. "
                       "Use a curva de momento x rotação direto no PLAXIS Output.")

if SEQ and P_KN is None:
    raise RuntimeError("Combinação em sequência sem 'carga_kN' no JSON (carga tipo momento não é suportada).")
if MODO == "nenhuma":
    print("    Módulo: sem ação (só o peso próprio da sapata) | componente {} | B = {:g} m".format(
        COMPONENTE, B_SAPATA))
elif MODO_DESL:
    print("    Módulo: {} | deslocamento prescrito {:g} mm | componente {} | B = {:g} m | A = {:g} m²".format(
        MODO, CARGA_TOTAL * 1000.0, COMPONENTE, B_SAPATA, AREA))
    if MODO == "combinado":
        print("    Combinação: {} | carga {:g} {}".format(
            "em sequência (fase Load, depois Displacement)" if SEQ else "na mesma fase",
            C.get("carga_valor", 0), C.get("carga_unidade", "")))
else:
    print("    Carga total {:g} {} | componente {} | B = {:g} m".format(CARGA_TOTAL, UNID, COMPONENTE, B_SAPATA))
    if EXTRA:
        print("    (duas cargas combinadas: total {:g} kN = {:g} kN/m² na área de {:g} m²)".format(
            float(C["carga_total_kN"]), CARGA_TOTAL, AREA))

# ----------------------------------------------------------------------------
# Conectar no Output da última fase
# ----------------------------------------------------------------------------
def formatar(x, casas):
    t = "{:.{}f}".format(x, casas)
    return t.replace(".", ",") if DECIMAL_VIRGULA else t


if MODO == "nenhuma":
    # Só peso próprio: sem curva carga x recalque. Lê o recalque do nó sob a sapata no fim da última fase.
    print(">>> Abrindo o Output da última fase (peso próprio da sapata)")
    porta_out = g_i.view(g_i.Phases[-1])
    s_o, g_o = new_server(HOST, porta_out, password=obter_senha())
    fase = g_o.Phases[-1]
    nome_fase = valor(fase.Identification) if hasattr(fase, "Identification") else str(fase)
    print("    Fase:", nome_fase)
    try:
        no = g_o.Nodes[0]
    except Exception as e:
        raise RuntimeError("Não achei o nó pré-selecionado em g_o.Nodes (rodou o plaxis_sapata_interativo.py "
                           "até o fim?): {}".format(e))
    tipo_resultado = getattr(g_o.ResultTypes.Soil, COMPONENTE)
    ultimo = fase.Steps.value[-1]
    u_no = float(g_o.getcurveresults(no, ultimo, tipo_resultado))
    s_mm = SINAL * u_no * 1000.0                      # positivo para baixo
    print("\n" + "=" * 70)
    print("PESO PRÓPRIO DA SAPATA (sem carga e sem deslocamento prescrito)")
    print("=" * 70)
    print("Recalque do nó sob a sapata ({} no fim da fase {}): {:.3f} mm".format(COMPONENTE, nome_fase, s_mm))
    gamma_s, d_s = S.get("gamma"), S.get("d")
    peso_kn = None
    if gamma_s is not None and d_s is not None:
        peso_kn = float(gamma_s) * float(d_s) * AREA
        print("Peso próprio da sapata: {:.2f} kN ({:.2f} kN/m² em {:g} m²)".format(
            peso_kn, peso_kn / AREA, AREA))
    print("=" * 70)
    with open(CSV_PESO, "w") as f:
        f.write("Fase;Deslocamento_{}_mm;Peso_proprio_kN\n".format(COMPONENTE))
        f.write("{};{};{}\n".format(nome_fase, formatar(s_mm, 4), formatar(peso_kn, 3) if peso_kn is not None else ""))
    print("    resultado salvo em", CSV_PESO)
    try:
        g_o.close()
    except Exception:
        pass
else:
    print(">>> Abrindo o Output da última fase")
    fase_in = g_i.Phases[-1]
    porta_out = g_i.view(fase_in)
    s_o, g_o = new_server(HOST, porta_out, password=obter_senha())

    fase = g_o.Phases[-1]
    print("    Fase:", valor(fase.Identification) if hasattr(fase, "Identification") else fase)

    try:
        no = g_o.Nodes[0]
    except Exception as e:
        raise RuntimeError("Não achei o nó pré-selecionado em g_o.Nodes (rodou o plaxis_sapata_interativo.py "
                           "até o fim?): {}".format(e))

    tipo_resultado = getattr(g_o.ResultTypes.Soil, COMPONENTE)

    # ----------------------------------------------------------------------------
    # Força de reação (modo deslocamento prescrito)
    # ----------------------------------------------------------------------------
    def ler_reacao(obj, passo, rt):
        """Soma a reação nos nós do deslocamento prescrito (PLAXIS 3D 2024.2: ...ReactionForceZ)."""
        erros = []
        for loc in ("node", None):
            try:
                r = g_o.getresults(obj, passo, rt, loc) if loc else g_o.getresults(obj, passo, rt)
                try:
                    return float(sum(float(v) for v in r))
                except TypeError:
                    return float(r)
            except Exception as e:  # noqa
                erros.append(str(e).strip().splitlines()[-1] if str(e).strip() else repr(e))
        raise RuntimeError("; ".join(erros))


    leitor = None
    if MODO_DESL:
        nome_rt = C.get("reacao") or "ReactionForceZ"
        print(">>> Procurando a reação {} do deslocamento prescrito".format(nome_rt))
        rt_reacao = None
        for cat in ("PrescribedDisplacement", "SurfaceDisplacement"):
            try:
                rt_reacao = getattr(getattr(g_o.ResultTypes, cat), nome_rt)
                break
            except Exception:
                continue
        if rt_reacao is None:
            raise RuntimeError("Não achei g_o.ResultTypes.PrescribedDisplacement.{}.".format(nome_rt))
        for nome_obj in ("PrescribedDisplacements", "SurfaceDisplacements", "PrescribedDisplacement_1",
                         "SurfaceDisplacement_1"):
            try:
                o = getattr(g_o, nome_obj)
            except Exception:
                continue
            try:
                if hasattr(o, "__getitem__") and not isinstance(o, str):
                    o = o[0]
            except Exception:
                pass
            try:
                v = ler_reacao(o, g_o.Phases[-1].Steps.value[-1], rt_reacao)
            except Exception:
                continue
            leitor = (nome_obj, o, rt_reacao)
            print("    usando {} / {}: {:.1f} kN no último passo".format(nome_obj, nome_rt, v))
            break
        if leitor is None:
            raise RuntimeError("Não consegui ler a reação do deslocamento prescrito. Rode exemplo2_resultados.py "
                               "(ele lista as grandezas disponíveis) e me envie a saída.")

    # ----------------------------------------------------------------------------
    # Extrair a curva de cada passo
    # ----------------------------------------------------------------------------
    print(">>> Lendo passos de cálculo")
    linhas = [(0.0, 0.0, 0.0)]
    forca_por_m = {0.0: 0.0}
    offset_m = 0.0
    if SEQ:
        # Fase anterior (Load): curva carga x deslocamento como no módulo de carga
        fase_load = g_o.Phases[-2]
        print("    Fase de carga:", valor(fase_load.Identification) if hasattr(fase_load, "Identification") else fase_load)
        for step in fase_load.Steps.value:
            m = mstage_do_passo(step)
            u = float(g_o.getcurveresults(no, step, tipo_resultado))
            F = m * P_KN
            forca_por_m[m] = F
            linhas.append((m, F / AREA, SINAL * u * 1000.0))
        offset_m = 1.0            # ΣMstage da fase Displacement é somado a 1 (fim da fase Load) no CSV
    # Força por passo: step.Reached.ForceX/Y/Z existe em TODOS os passos (o PLAXIS só guarda os resultados
    # completos do último). Só é usada se coincidir com a reação lida no último passo (ReactionForce*).
    comp_forca = "Force" + (C.get("reacao") or "ReactionForceZ")[-1]      # ForceX / ForceY / ForceZ
    usar_reached = False
    if MODO_DESL:
        try:
            ultimo = fase.Steps.value[-1]
            R_ref = ler_reacao(leitor[1], ultimo, leitor[2])
            R_rea = float(valor(getattr(ultimo.Reached, comp_forca)))
            usar_reached = abs(R_rea - R_ref) <= 0.01 * max(abs(R_ref), 1.0)
            print("    Reached.{} no último passo: {:.1f} kN | reação: {:.1f} kN -> {}".format(
                comp_forca, R_rea, R_ref,
                "usando Reached por passo" if usar_reached else "NÃO coincidem; Reached não será usado"))
        except Exception as e:  # noqa
            print("    (aviso) não consegui conferir Reached.{}: {}".format(comp_forca, e))

    passos_desl = []            # (ΣMstage, deslocamento mm, força kN ou None)
    for step in fase.Steps.value:
        m = mstage_do_passo(step) + offset_m
        u = float(g_o.getcurveresults(no, step, tipo_resultado))
        s_mm = SINAL * u * 1000.0               # mm, positivo no sentido da carga/deslocamento
        if MODO_DESL:
            try:
                if usar_reached:
                    R = float(valor(getattr(step.Reached, comp_forca)))
                else:
                    R = ler_reacao(leitor[1], step, leitor[2])
                F = (P_KN + R * DSIGN) if SEQ else abs(R)   # sequência: carga já aplicada + força adicional
            except Exception:
                F = None            # o PLAXIS só guarda resultados completos de alguns passos
            passos_desl.append((m, s_mm, F))
        else:
            linhas.append((m, m * CARGA_TOTAL, s_mm))

    CURVA_COMPLETA = True
    if MODO_DESL:
        com_forca = [p_ for p_ in passos_desl if p_[2] is not None]
        CURVA_COMPLETA = len(com_forca) >= max(3, int(0.9 * len(passos_desl)))
        for m, s_mm, F in com_forca:
            forca_por_m[m] = F
            linhas.append((m, F / AREA, s_mm))             # tensão média (kN/m²), recalque (mm)
        print("    Reação lida em {} de {} passos".format(len(com_forca), len(passos_desl)))
        if not CURVA_COMPLETA:
            print("    (AVISO) O PLAXIS guarda por padrão só o último passo de cada fase; sem os passos")
            print("    intermediários não há curva força x recalque, apenas o resultado final.")
            print("    Para ter a curva: no PLAXIS, fase > Max steps stored (MaxStepsStored) = 100 e recalcule.")

    linhas = sorted(set(linhas), key=lambda r: r[1])


    def num(x, casas):
        t = "{:.{}f}".format(x, casas)
        return t.replace(".", ",") if DECIMAL_VIRGULA else t


    with open(CSV, "w") as f:
        if MODO_DESL:
            f.write("SumMstage;Tensao_kN_m2;Forca_kN;Deslocamento_{}_mm\n".format(COMPONENTE))
            linhas_csv = [(m, q_, forca_por_m.get(m, q_ * AREA), s_) for m, q_, s_ in linhas
                          if m not in [p_[0] for p_ in passos_desl]]
            linhas_csv += [(m, (F / AREA if F is not None else None), F, s_mm) for m, s_mm, F in passos_desl]
            for m, q_, F, s_ in sorted(linhas_csv, key=lambda r: r[0]):
                f.write("{};{};{};{}\n".format(num(m, 6), num(q_, 4) if q_ is not None else "",
                                              num(F, 3) if F is not None else "", num(s_, 4)))
        else:
            f.write("SumMstage;Carga_{};Deslocamento_{}_mm\n".format(
                UNID_CSV.replace("/", "_").replace(".", ""), COMPONENTE))
            for m, q_, s_ in linhas:
                f.write("{};{};{}\n".format(num(m, 6), num(q_, 4), num(s_, 4)))
    print("    {} pontos salvos em {}".format(len(linhas), CSV))

    q = [l[1] for l in linhas]
    s = [l[2] for l in linhas]
    q_max, s_max = max(q), max(s)
    if s_max <= 0:
        raise RuntimeError("Deslocamento máximo <= 0 no sentido da carga: confira o sinal/direção em "
                           "ultimo_modelo.json (componente {}, sinal {}).".format(COMPONENTE, SINAL))


    # ----------------------------------------------------------------------------
    # Análise
    # ----------------------------------------------------------------------------
    def regressao(x, y):
        n = float(len(x))
        mx, my = sum(x) / n, sum(y) / n
        sxx = sum((a - mx) ** 2 for a in x)
        sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
        c = sxy / sxx
        return c, my - c * mx


    def carga_no_recalque(s_alvo):
        """Carga em que a curva cruza o recalque s_alvo (mm). None se a curva não chega lá."""
        for (q0, s0), (q1, s1) in zip(zip(q, s), zip(q[1:], s[1:])):
            if s1 != s0 and (s0 - s_alvo) * (s1 - s_alvo) <= 0:
                return q0 + (q1 - q0) * (s_alvo - s0) / (s1 - s0)
        # Tolerância: o último ponto pode ficar um pouco abaixo do alvo por arredondamento
        # (ex.: deslocamento prescrito de 25 mm chega a 24,9998 mm). Usa o último ponto nesse caso.
        tol = max(0.05, 0.002 * s_alvo)
        if s and 0 < s_alvo - max(s) <= tol:
            i = s.index(max(s))
            return q[i]
        return None


    def recalque_na_carga(q_alvo):
        for (q0, s0), (q1, s1) in zip(zip(q, s), zip(q[1:], s[1:])):
            if q1 > q0 and q0 <= q_alvo <= q1:
                return s0 + (s1 - s0) * (q_alvo - q0) / (q1 - q0)
        return None


    def como_tensao(x):
        """Para carga concentrada, tensão média equivalente na sapata (kN/m²)."""
        return x / AREA if C["tipo"] == 2 and AREA > 0 and not EXTRA else None


    ANALISE = CURVA_COMPLETA
    if not ANALISE:
        print("\n" + "=" * 70)
        print("RESULTADO FINAL (sem curva completa)")
        print("=" * 70)
        print("Deslocamento final: {:.1f} mm -> força {:.1f} kN, tensão média F/A = {:.1f} kN/m² "
              "({:.2f} kgf/cm²)".format(s_max, q_max * AREA, q_max, q_max / 98.0665))
        print("(critérios por curva e gráficos exigem os passos intermediários; veja o aviso acima)")
        print("=" * 70)
    if ANALISE:
        qu_tang = s_int = k = c = d = None
        if len(q) > N_PONTOS_INICIAIS + N_PONTOS_FINAIS:
            ini = slice(1, 1 + N_PONTOS_INICIAIS)
            fim = slice(-N_PONTOS_FINAIS, None)
            k = sum(a * b for a, b in zip(s[ini], q[ini])) / sum(a * a for a in s[ini])
            c, d = regressao(s[fim], q[fim])
            if abs(k - c) > 1e-9:
                s_int = d / (k - c)
                qu_tang = k * s_int
                if qu_tang <= 0 or s_int <= 0:
                    qu_tang = s_int = None

        s_10b = FRACAO_B * B_SAPATA * 1000.0
        q_10b = carga_no_recalque(s_10b) if VERTICAL_BAIXO else None
        q_25 = carga_no_recalque(RECALQUE_ADM_MM) if VERTICAL_BAIXO else None


        def linha_tensao(x):
            t = como_tensao(x)
            return "   (tensão média na sapata = {:.1f} kN/m²)".format(t) if t is not None else ""


        print("\n" + "=" * 70)
        print("RESUMO DOS CRITÉRIOS (B = {:.2f} m, FS = {})".format(B_SAPATA, FS))
        print("=" * 70)
        print("Carga máxima atingida no cálculo : {:.1f} {} (deslocamento {:.1f} mm)".format(q_max, UNID, s_max))
        if MODO_DESL:
            print("Deslocamento final              : {:.1f} mm -> força {:.1f} kN, tensão média {:.1f} kN/m² "
                  "({:.2f} kgf/cm²)".format(s_max, q_max * AREA, q_max, q_max / 98.0665))
            print("   (com deslocamento imposto, a tensão no último passo já é a tensão para esse recalque)")
            if SEQ:
                print("   (força total = carga da fase Load {:.1f} kN + reação do deslocamento prescrito; "
                      "recalque acumulado das duas fases)".format(P_KN))
            elif MODO == "combinado":
                print("   (curva pela reação do eixo prescrito; a carga simultânea em outro eixo não entra na força)")
        elif q_max >= 0.999 * CARGA_TOTAL:
            print("   (AVISO) o cálculo chegou ao fim da carga aplicada sem ruptura clara: aumente a carga e refaça.")

        if qu_tang is not None:
            qa = qu_tang / FS
            sa = recalque_na_carga(qa)
            print("\n1) Interseção das tangentes")
            if MODO_DESL:
                print("   (só faz sentido se o deslocamento prescrito foi grande o bastante para a curva formar patamar)")
            print("   qu = {:.0f} {}  (deslocamento na interseção ~ {:.1f} mm)".format(qu_tang, UNID, s_int))
            print("   qa = qu/FS = {:.1f} {}  (deslocamento em qa ~ {})".format(
                qa, UNID, "{:.1f} mm".format(sa) if sa is not None else "n/d"))
            if linha_tensao(qu_tang):
                print(linha_tensao(qu_tang))
        else:
            print("\n1) Interseção das tangentes: não foi possível calcular (poucos pontos ou curva sem patamar).")

        if VERTICAL_BAIXO:
            print("\n2) Recalque = {:.0f}% de B = {:.0f} mm".format(FRACAO_B * 100, s_10b))
            if q_10b is not None:
                sa = recalque_na_carga(q_10b / FS)
                print("   qu = {:.0f} {}".format(q_10b, UNID))
                print("   qa = qu/FS = {:.1f} {}  (recalque em qa ~ {})".format(
                    q_10b / FS, UNID, "{:.1f} mm".format(sa) if sa is not None else "n/d"))
                if linha_tensao(q_10b):
                    print(linha_tensao(q_10b))
            else:
                print("   A curva só chegou a {:.2f} mm; não atinge {:.0f} mm.".format(s_max, s_10b))

            print("\n3) Recalque de {:.0f} mm (Terzaghi e Peck, 1948)".format(RECALQUE_ADM_MM))
            if q_25 is not None:
                print("   carga que causa {:.0f} mm = {:.1f} {}  (já é admissível por recalque, sem FS)".format(
                    RECALQUE_ADM_MM, q_25, UNID))
                if linha_tensao(q_25):
                    print(linha_tensao(q_25))
            else:
                print("   A curva só chegou a {:.3f} mm; não atinge {:.0f} mm.".format(s_max, RECALQUE_ADM_MM))
        else:
            print("\n(Critérios de 10% de B e de 25 mm aplicados apenas a carga vertical para baixo.)")
        print("=" * 70)

        # ----------------------------------------------------------------------------
        # Gráficos
        # ----------------------------------------------------------------------------
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except Exception as e:
            plt = None
            print("\n(sem gráficos: matplotlib indisponível: {})".format(e))

        COR_CURVA = "#1f4e9c"
        COR_A = "#d9730d"
        COR_B = "#2a8c4a"
        COR_MARCA = "#c0392b"
        ROTULO_DESLOC = "Recalque (mm)" if VERTICAL_BAIXO else "Deslocamento {} (mm)".format(COMPONENTE)


        def limite_s(s_lim):
            if ZOOM and s_lim is not None:
                return min(s_lim, s_max * 1.05)
            return s_max * 1.05


        def figura_base(titulo, s_lim=None):
            fig, ax = plt.subplots(figsize=(8.5, 5.8))
            ax.plot(q, s, "-", color=COR_CURVA, lw=2.2, label="Curva do PLAXIS (nó sob a sapata)")
            ax.set_xlabel("Carga ({})".format(UNID))
            ax.set_ylabel(ROTULO_DESLOC)
            ax.set_title(titulo)
            ax.set_xlim(0, q_max * 1.1)
            ax.set_ylim(limite_s(s_lim), 0)
            ax.grid(True, alpha=0.3)
            return fig, ax


        def grafico_curva():
            """Curva completa, sem zoom e sem nenhum critério."""
            fig, ax = plt.subplots(figsize=(8.5, 5.8))
            ax.plot(q, s, "-", color=COR_CURVA, lw=2.2)
            ax.set_xlabel("Carga ({})".format(UNID))
            ax.set_ylabel(ROTULO_DESLOC)
            ax.set_title("Curva carga x {}".format("recalque" if VERTICAL_BAIXO else "deslocamento"))
            ax.set_xlim(0, q_max * 1.05)
            ax.set_ylim(s_max * 1.05, 0)
            ax.grid(True, alpha=0.3)
            fig.tight_layout()
            fig.savefig(PNG_CURVA, dpi=150)
            plt.close(fig)
            print("    gráfico salvo em", PNG_CURVA)


        def grafico_tangentes():
            s_lim = max(6 * s_int, 80.0) if s_int else None
            fig, ax = figura_base("qu pela interseção das tangentes", s_lim)
            if qu_tang is not None:
                s_topo = limite_s(s_lim)
                q_fim_ini = q_max * 1.08
                ax.plot([0, q_fim_ini], [0, q_fim_ini / k], "--", color=COR_A, lw=1.8, label="Tangente inicial")
                s_ini_fin = max(s_int * 0.4, 0.0)
                ax.plot([c * s_ini_fin + d, c * s_topo + d], [s_ini_fin, s_topo], "--", color=COR_B, lw=1.8,
                        label="Tangente final")
                ax.plot([qu_tang], [s_int], "o", color=COR_MARCA, ms=8, zorder=5)
                ax.annotate("qu = {:.0f} {}\n(desloc. {:.1f} mm)".format(qu_tang, UNID, s_int),
                            xy=(qu_tang, s_int), xytext=(qu_tang * 0.45, s_int + s_topo * 0.3),
                            arrowprops=dict(arrowstyle="->", color=COR_MARCA), color=COR_MARCA)
                ax.axvline(qu_tang, color=COR_MARCA, ls=":", lw=1)
            ax.legend(loc="lower left")
            fig.tight_layout()
            fig.savefig(PNG_TANGENTES, dpi=150)
            plt.close(fig)
            print("    gráfico salvo em", PNG_TANGENTES)


        def grafico_criterio(arquivo, titulo, s_alvo, q_alvo, rotulo):
            s_lim = 2.2 * s_alvo
            fig, ax = figura_base(titulo, s_lim)
            ax.axhline(s_alvo, color=COR_A, ls="--", lw=1.5, label="Recalque = {:.0f} mm".format(s_alvo))
            if q_alvo is not None:
                ax.plot([q_alvo, q_alvo], [0, s_alvo], ":", color=COR_MARCA, lw=1.5)
                ax.plot([q_alvo], [s_alvo], "o", color=COR_MARCA, ms=8, zorder=5)
                ax.annotate("{} = {:.0f} {}".format(rotulo, q_alvo, UNID),
                            xy=(q_alvo, s_alvo), xytext=(q_alvo * 0.3, s_alvo + limite_s(s_lim) * 0.25),
                            arrowprops=dict(arrowstyle="->", color=COR_MARCA), color=COR_MARCA)
            else:
                ax.text(0.5, 0.5, "A curva não atinge {:.0f} mm".format(s_alvo),
                        transform=ax.transAxes, ha="center", color=COR_MARCA)
            ax.legend(loc="lower left")
            fig.tight_layout()
            fig.savefig(arquivo, dpi=150)
            plt.close(fig)
            print("    gráfico salvo em", arquivo)


        if plt is not None:
            print("\n>>> Gerando gráficos")
            grafico_curva()
            grafico_tangentes()
            if VERTICAL_BAIXO:
                grafico_criterio(PNG_10B, "Critério de {:.0f}% de B ({:.0f} mm)".format(FRACAO_B * 100, s_10b),
                                 s_10b, q_10b, "qu")
                grafico_criterio(PNG_25MM, "Carga para {:.0f} mm de recalque (Terzaghi e Peck, 1948)".format(
                    RECALQUE_ADM_MM), RECALQUE_ADM_MM, q_25, "q")

    try:
        g_o.close()
    except Exception:
        pass

# -*- coding: utf-8 -*-
"""
PLAXIS 3D - Sapata: modelo interativo (domínio, camadas, sapata, carga, malha).

Roda pelo executor externo (ele já entrega s_i e g_i). O script PERGUNTA os dados no terminal;
apertar Enter aceita o valor entre colchetes. Os valores padrão são os do Exemplo 1 do PDF
(sapata 1 x 1 x 0,5 m na superfície, carga distribuída de 1000 kN/m2, malha "fine").

Etapas: perguntas e validações -> resumo -> cria o modelo -> salva -> (opcional) calcula.
Grava "ultimo_modelo.json" na pasta do script para o plaxis_sapata_resultados.py.

Três módulos de ação na sapata (independentes; escolhidos na pergunta 5):
  1) SÓ CARGA (padrão; é o Exemplo 1 validado): surface load ou point load.
  2) SÓ DESLOCAMENTO PRESCRITO (Exemplo 2): surface displacement uniforme na sapata; a força
     necessária é lida do Output pelo script de resultados.
  3) COMBINADO: carga + deslocamento prescrito, em sequência (mesma direção) ou na mesma fase
     (direções diferentes). Não testado no PLAXIS real.
  4) SEM AÇÃO: nenhuma carga e nenhum deslocamento; só a fase de construção da sapata (peso próprio).
Os módulos 1 e 2 seguem exatamente os mesmos comandos de antes (as perguntas novas têm padrão que
reproduz o comportamento anterior).

Opções adicionais (todas com padrão = comportamento anterior):
  - porta do servidor Input: só é perguntada (antes da senha) se o script rodar SEM o executor externo;
    pelo executor, usa a conexão que ele já abriu;
  - Title e Company do projeto (perguntados no início);
  - nome do material da sapata (padrão "Footing");
  - sapata como VOLUME de material Linear Elástico NÃO POROSO (como o "Building" do manual da Bentley)
    em vez de placa  [não testado];
  - segunda carga de forma diferente (surface load + point load) nos módulos 1 e 3  [não testado].

Trechos validados no PLAXIS real (Exemplo 1 e 2): projeto, contorno, 1 camada, nível d'água,
materiais, placa + carga distribuída vertical, deslocamento prescrito vertical para baixo,
coarseness, malha, curva, fases e cálculo.
Trechos escritos a partir da documentação e marcados "(não testado)" ao rodar: várias camadas,
sapata embutida (z < 0), carga concentrada, tração, carga horizontal, momento e deslocamento
prescrito para cima ou horizontal.
"""
import os
import json
import getpass

from plxscripting.easy import new_server

HOST = "localhost"
PORTA_PADRAO = 10000
TITULO_PADRAO = "PLAXIS 3D: Sapata (modelo interativo)"
PASTA = os.path.dirname(os.path.abspath(globals().get("__file__", ".")))
ARQUIVO_JSON = os.path.join(PASTA, "ultimo_modelo.json")

# Presets do GUI (lidos no histórico de comandos do PLAXIS 3D 2024.2)
PRESETS_MALHA = (("very coarse", 0.1), ("coarse", 0.075), ("medium", 0.05),
                 ("fine", 0.035), ("very fine", 0.025))


# ----------------------------------------------------------------------------
# Utilitários de entrada
# ----------------------------------------------------------------------------
def fmt(x):
    return "{:g}".format(x)


def _ler(prompt, default_txt):
    sufixo = " [{}]".format(default_txt) if default_txt not in (None, "") else ""
    try:
        return input("  {}{}: ".format(prompt, sufixo)).strip()
    except EOFError:
        raise RuntimeError("Sem terminal interativo para ler as respostas.")


def perguntar_float(prompt, default=None, lo=None, hi=None, lo_incl=True, hi_incl=True, unidade=""):
    rotulo = prompt + (" ({})".format(unidade) if unidade else "")
    while True:
        txt = _ler(rotulo, fmt(default) if default is not None else None)
        if txt == "" and default is not None:
            v = float(default)
        else:
            try:
                v = float(txt.replace(",", "."))
            except ValueError:
                print("    ! Digite um número (use ponto ou vírgula).")
                continue
        if lo is not None and (v < lo if lo_incl else v <= lo):
            print("    ! O valor deve ser {} {}.".format(">=" if lo_incl else ">", fmt(lo)))
            continue
        if hi is not None and (v > hi if hi_incl else v >= hi):
            print("    ! O valor deve ser {} {}.".format("<=" if hi_incl else "<", fmt(hi)))
            continue
        return v


def perguntar_int(prompt, default, lo, hi):
    while True:
        txt = _ler(prompt, str(default))
        try:
            v = default if txt == "" else int(txt)
        except ValueError:
            print("    ! Digite um número inteiro.")
            continue
        if v < lo or v > hi:
            print("    ! Digite um valor entre {} e {}.".format(lo, hi))
            continue
        return v


def perguntar_texto(prompt, default):
    txt = _ler(prompt, default)
    return txt or default


def perguntar_sim_nao(prompt, default=True):
    padrao = "s" if default else "n"
    while True:
        txt = _ler(prompt + " (s/n)", padrao).lower()
        if txt == "":
            return default
        if txt in ("s", "sim", "y", "yes"):
            return True
        if txt in ("n", "nao", "não", "no"):
            return False
        print("    ! Responda s ou n.")


def perguntar_opcao(titulo, opcoes, default=1):
    print("\n  " + titulo)
    for i, o in enumerate(opcoes, 1):
        print("    {}) {}".format(i, o))
    return perguntar_int("Opção", default, 1, len(opcoes))


def aviso(msg):
    print("    (aviso) " + msg)


def etapa(msg):
    print("\n>>> " + msg)


def titulo(msg):
    print("\n" + "-" * 70)
    print(msg)
    print("-" * 70)


# ----------------------------------------------------------------------------
# Perguntas
# ----------------------------------------------------------------------------
EIXO_DIR = {1: "z", 2: "z", 3: "x", 4: "y", 5: None}
NOME_DIR = {1: "vertical para baixo", 2: "vertical para cima", 3: "horizontal +X",
            4: "horizontal +Y", 5: "momento"}


def perguntar_carga(direcao_fixa=None, eixos_proibidos=(), dica=None, tipo_fixo=None):
    """Pergunta direção/forma/valor de uma CARGA. Devolve dict(tipo, direcao, eixo, valor, unidade)."""
    if direcao_fixa is None:
        permitidas = [i for i in (1, 2, 3, 4, 5) if EIXO_DIR[i] not in eixos_proibidos or EIXO_DIR[i] is None]
        if tipo_fixo == 1:
            permitidas = [i for i in permitidas if i != 5]      # momento é sempre concentrado
        while True:
            direcao = perguntar_opcao("Direção/tipo da ação:", [
                "Vertical para baixo (compressão)",
                "Vertical para cima (tração / arrancamento)  [não testado]",
                "Horizontal em +X  [não testado]",
                "Horizontal em +Y  [não testado]",
                "Momento (carga concentrada)  [não testado]"], permitidas[0])
            if direcao in permitidas:
                break
            print("    ! Essa direção não é permitida aqui (eixo do deslocamento prescrito ou forma da carga). "
                  "Escolha outra.")
    else:
        direcao = direcao_fixa
        print("\n  Direção da carga: {} (igual à do deslocamento prescrito).".format(NOME_DIR[direcao]))
    if direcao == 5:
        tipo = 2
        print("\n  Momento: aplicado como carga concentrada no centro da sapata.")
        eixo = perguntar_opcao("Eixo do momento:", ["Mx (em torno de x)", "My (em torno de y)",
                                                    "Mz (em torno de z)"], 2)
    else:
        eixo = None
        if tipo_fixo:
            tipo = tipo_fixo
            print("\n  Forma de aplicação: {}.".format(
                "distribuída em toda a sapata (surface load)" if tipo == 1
                else "concentrada no centro da sapata (point load)"))
        else:
            tipo = perguntar_opcao("Forma de aplicação:", [
                "Distribuída em toda a sapata (surface load)  [kN/m2]",
                "Concentrada no centro da sapata (point load)  [kN]  [não testado]"], 1)
    if direcao == 5:
        unidade, padrao_v = "kN.m", 1000.0
    elif tipo == 1:
        unidade, padrao_v = "kN/m2", 1000.0
    else:
        unidade, padrao_v = "kN", 1000.0
    print("\n  " + (dica or "Dica: use um valor MAIOR que a capacidade esperada para a curva chegar à ruptura."))
    valor = perguntar_float("Valor da carga (módulo)", padrao_v, lo=0.0, lo_incl=False, unidade=unidade)
    return dict(tipo=tipo, direcao=direcao, eixo=eixo, valor=valor, unidade=unidade)


def perguntar_extra(cc, direcao_fixa=None, eixos_proibidos=()):
    """Opcional: segunda carga de FORMA diferente da primeira (surface load + point load).
    As duas crescem juntas na mesma fase (mesmo ΣMstage). Devolve dict ou None."""
    primeira_distribuida = (cc["tipo"] == 1)
    if not perguntar_sim_nao("Combinar com uma segunda carga ({})? [não testado]".format(
            "concentrada/momento" if primeira_distribuida else "distribuída (surface load)"), False):
        return None
    print("\n  Segunda carga (aplicada junto com a primeira, na mesma fase):")
    return perguntar_carga(direcao_fixa=direcao_fixa, eixos_proibidos=eixos_proibidos,
                           tipo_fixo=(2 if primeira_distribuida else 1),
                           dica="Dica: as duas cargas crescem juntas (mesmo ΣMstage).")


def perguntar_desl():
    """Pergunta direção e valor do DESLOCAMENTO PRESCRITO. Devolve dict(direcao, valor [m])."""
    direcao = perguntar_opcao("Direção do deslocamento prescrito:", [
        "Vertical para baixo (recalque)",
        "Vertical para cima (levantamento)  [não testado]",
        "Horizontal em +X  [não testado]",
        "Horizontal em +Y  [não testado]"], 1)
    print("\n  O deslocamento é imposto uniformemente a toda a superfície da sapata.")
    print("  Dica: para o critério de 25 mm ou 10% de B, prescreva um valor maior que esses limites.")
    cm = perguntar_float("Valor do deslocamento prescrito (módulo)", 2.5, lo=0.0, lo_incl=False, unidade="cm")
    passos = perguntar_int("Número mínimo de passos de cálculo (mais passos = curva com mais pontos)", 50, 5, 1000)
    return dict(direcao=direcao, valor=cm / 100.0, passos=passos)


def perguntar_tudo():
    P = {}
    print("=" * 70)
    print(" PLAXIS 3D - SAPATA: MODELO INTERATIVO")
    print(" Enter aceita o valor entre colchetes (padrão = Exemplo 1 do PDF).")
    print(" Unidades: m, kN, dia. Eixo z positivo para cima (terreno em z = 0).")
    print("=" * 70)

    # --- 0. Title e Company (opcional)
    P["info"] = dict(titulo=TITULO_PADRAO, empresa="")
    if perguntar_sim_nao("Definir Title e Company do projeto (n = manter o padrão)?", False):
        P["info"]["titulo"] = perguntar_texto("Title", TITULO_PADRAO)
        P["info"]["empresa"] = perguntar_texto("Company", "")

    # --- 1. Domínio
    titulo("1) DOMÍNIO DO MODELO")
    xmin = perguntar_float("x mínimo", -5.0, unidade="m")
    xmax = perguntar_float("x máximo", 5.0 if 5.0 > xmin else xmin + 10.0, lo=xmin, lo_incl=False, unidade="m")
    ymin = perguntar_float("y mínimo", -5.0, unidade="m")
    ymax = perguntar_float("y máximo", 5.0 if 5.0 > ymin else ymin + 10.0, lo=ymin, lo_incl=False, unidade="m")
    H = perguntar_float("Profundidade total do modelo (positiva; o fundo fica em z = -H)", 10.0,
                        lo=0.0, lo_incl=False, unidade="m")
    P["dominio"] = dict(xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax, H=H)

    # --- 2. Camadas
    titulo("2) CAMADAS DE SOLO (Mohr-Coulomb, drenado)")
    n = perguntar_int("Quantas camadas de solo?", 1, 1, 10)
    camadas, restante, nomes = [], H, set()
    for i in range(n):
        print("\n  --- Camada {} (de cima para baixo) ---".format(i + 1))
        while True:
            nome = perguntar_texto("Nome do material", "Soil" if i == 0 else "Soil_{}".format(i + 1))
            if nome in nomes:
                print("    ! Já existe uma camada com esse nome.")
                continue
            nomes.add(nome)
            break
        if i < n - 1:
            esp = perguntar_float("Espessura", min(restante / 2.0, 5.0), lo=0.0, hi=restante,
                                  lo_incl=False, hi_incl=False, unidade="m")
        else:
            esp = restante
            print("  Espessura: {} m (o que falta para completar a profundidade do modelo)".format(fmt(esp)))
        gu = perguntar_float("Peso específico não saturado", 18.0, lo=0.0, lo_incl=False, unidade="kN/m3")
        gs = perguntar_float("Peso específico saturado", max(20.0, gu), lo=0.0, lo_incl=False, unidade="kN/m3")
        if gs < gu:
            aviso("γsat menor que γunsat é incomum.")
        E = perguntar_float("Módulo de Young E'", 40000.0, lo=0.0, lo_incl=False, unidade="kN/m2")
        nu = perguntar_float("Coeficiente de Poisson ν'", 0.3, lo=0.0, hi=0.5, lo_incl=False, hi_incl=False)
        c = perguntar_float("Coesão c'", 30.0, lo=0.0, unidade="kN/m2")
        if c < 0.2:
            aviso("c' < 0,2 kN/m2 pode dificultar a convergência no PLAXIS.")
        phi = perguntar_float("Ângulo de atrito φ'", 20.0, lo=0.0, hi=89.0, unidade="graus")
        psi = perguntar_float("Ângulo de dilatância ψ", 0.0, lo=0.0, hi=phi, unidade="graus")
        camadas.append(dict(nome=nome, espessura=esp, gamma_unsat=gu, gamma_sat=gs, E=E, nu=nu,
                            c=c, phi=phi, psi=psi))
        restante -= esp
    P["camadas"] = camadas

    # --- 3. Nível d'água
    titulo("3) NÍVEL D'ÁGUA")
    padrao_na = -6.0 if H > 6.0 else -0.6 * H
    na = perguntar_float("Cota z do nível freático (0 = superfície; -H = fundo do modelo)", padrao_na,
                         lo=-H, hi=0.0, unidade="m")
    P["nivel_agua"] = na

    # --- 4. Sapata
    titulo("4) SAPATA")
    d = P["dominio"]
    while True:
        cx = perguntar_float("x do centro da sapata", 0.0, lo=d["xmin"], hi=d["xmax"], unidade="m")
        cy = perguntar_float("y do centro da sapata", 0.0, lo=d["ymin"], hi=d["ymax"], unidade="m")
        cz = perguntar_float("z do plano da sapata (0 = no terreno; negativo = embutida; profundidade = -z)",
                             0.0, lo=-H, hi=0.0, lo_incl=False, unidade="m")
        L = perguntar_float("Comprimento (direção x)", 1.0, lo=0.0, lo_incl=False, unidade="m")
        W = perguntar_float("Largura (direção y)", 1.0, lo=0.0, lo_incl=False, unidade="m")
        esp_s = perguntar_float("Espessura da sapata (d da placa)", 0.5, lo=0.0, lo_incl=False, unidade="m")
        erros = []
        if cx - L / 2.0 < d["xmin"] or cx + L / 2.0 > d["xmax"]:
            erros.append("a sapata sai do domínio em x ({} a {})".format(fmt(cx - L / 2.0), fmt(cx + L / 2.0)))
        if cy - W / 2.0 < d["ymin"] or cy + W / 2.0 > d["ymax"]:
            erros.append("a sapata sai do domínio em y ({} a {})".format(fmt(cy - W / 2.0), fmt(cy + W / 2.0)))
        if cz - esp_s / 2.0 <= -H:
            erros.append("a espessura leva a sapata até o fundo do modelo")
        if erros:
            print("    ! Dimensões inválidas: " + "; ".join(erros) + ". Digite de novo.\n")
            continue
        break
    Bmax = max(L, W)
    folgas = [cx - L / 2.0 - d["xmin"], d["xmax"] - (cx + L / 2.0),
              cy - W / 2.0 - d["ymin"], d["ymax"] - (cy + W / 2.0)]
    if min(folgas) < 2.0 * Bmax:
        aviso("a sapata fica a menos de {} m de uma borda lateral (2 x maior lado); as bordas podem "
              "influenciar o resultado. Considere aumentar o domínio.".format(fmt(2.0 * Bmax)))
    if cz + H < 2.0 * Bmax:
        aviso("há menos de {} m de solo abaixo da sapata (2 x maior lado).".format(fmt(2.0 * Bmax)))
    if cz < 0:
        aviso("sapata embutida (não testado): o solo acima dela é mantido (sem escavação).")
    modelo_i = perguntar_opcao("Como modelar a sapata?", [
        "PLACA elástica (plate)  - Exemplos 1 e 2",
        "VOLUME sólido, material Linear Elástico NÃO POROSO (como o 'Building' do manual da Bentley)"
        "  [não testado]"], 1)
    print("\n  Material da sapata:")
    nomes_solo = set(cam["nome"] for cam in camadas)
    while True:
        nome_mat_f = perguntar_texto("Nome do material da sapata", "Footing")
        if nome_mat_f in nomes_solo:
            print("    ! Esse nome já é de um material de solo. Escolha outro.")
            continue
        break
    gamma_f = perguntar_float("Peso específico", 24.0, lo=0.0, lo_incl=False, unidade="kN/m3")
    E_f = perguntar_float("Módulo de Young E", 2.35e7, lo=0.0, lo_incl=False, unidade="kN/m2")
    nu_f = perguntar_float("Coeficiente de Poisson ν", 0.2, lo=0.0, hi=0.5, lo_incl=False, hi_incl=False)
    P["sapata"] = dict(cx=cx, cy=cy, cz=cz, L=L, W=W, d=esp_s, B=min(L, W),
                       gamma=gamma_f, E=E_f, nu=nu_f, nome_material=nome_mat_f,
                       modelo="placa" if modelo_i == 1 else "volume")

    # --- 5. Ação na sapata (três módulos independentes)
    titulo("5) AÇÃO NA SAPATA")
    modo_i = perguntar_opcao("O que será aplicado na sapata?", [
        "Só CARGA (força)  - Exemplo 1",
        "Só DESLOCAMENTO PRESCRITO (o PLAXIS calcula a força necessária)  - Exemplo 2",
        "COMBINADO: carga + deslocamento prescrito  [não testado]",
        "SEM AÇÃO: nenhuma carga nem deslocamento, só o peso próprio da sapata  [não testado]"], 1)
    if modo_i == 4:
        P["carga"] = dict(modo="nenhuma", tipo=1, direcao=1, eixo=None, valor=0.0, unidade="kN/m2")
    elif modo_i == 1:
        cc = perguntar_carga()
        P["carga"] = dict(modo="carga", **cc)
        ex = perguntar_extra(cc)
        if ex:
            P["carga"]["extra"] = ex
    elif modo_i == 2:
        cd = perguntar_desl()
        P["carga"] = dict(modo="deslocamento", tipo=1, direcao=cd["direcao"], eixo=None,
                          valor=cd["valor"], unidade="m", passos=cd["passos"])
    else:
        sub_i = perguntar_opcao("Como combinar?", [
            "EM SEQUÊNCIA: fase Load (carga) e depois fase Displacement (deslocamento adicional, MESMA direção)",
            "NA MESMA FASE, em direções (eixos) DIFERENTES (ex.: recalque prescrito + carga horizontal)"], 1)
        cd = perguntar_desl()
        if sub_i == 1:
            print("\n  Carga da 1ª fase (use um valor MENOR que a ruptura: é a carga de serviço/pré-carga).")
            cc = perguntar_carga(direcao_fixa=cd["direcao"],
                                 dica="Dica: a carga é aplicada primeiro; depois o deslocamento é acrescentado.")
        else:
            print("\n  Carga aplicada junto com o deslocamento (eixo diferente do deslocamento).")
            cc = perguntar_carga(eixos_proibidos=(EIXO_DIR[cd["direcao"]],),
                                 dica="Dica: carga e deslocamento crescem juntos (mesmo ΣMstage).")
        if sub_i == 1:
            ex = perguntar_extra(cc, direcao_fixa=cd["direcao"])
        else:
            ex = perguntar_extra(cc, eixos_proibidos=(EIXO_DIR[cd["direcao"]],))
        P["carga"] = dict(modo="combinado", sub="sequencia" if sub_i == 1 else "simultaneo",
                          carga_parte=cc, desl_parte=cd,
                          tipo=1, direcao=cd["direcao"], eixo=None, valor=cd["valor"], unidade="m",
                          passos=cd["passos"])
        if ex:
            P["carga"]["extra"] = ex

    # --- 6. Malha
    titulo("6) MALHA")
    nomes_m = ["{} (fator {})".format(n_, fmt(f)) for n_, f in PRESETS_MALHA]
    idx = perguntar_opcao("Element distribution:", nomes_m, 4)
    refinar = perguntar_sim_nao("Refinar a malha na sapata?", True)
    coars = 0.1
    if refinar:
        coars = perguntar_float("Coarseness factor da sapata (menor = mais fino; padrão do PLAXIS = 0,5)",
                                0.1, lo=0.0, hi=1.0, lo_incl=False)
    P["malha"] = dict(nome=PRESETS_MALHA[idx - 1][0], fator=PRESETS_MALHA[idx - 1][1],
                      refinar=refinar, coarseness=coars)

    # --- 7. Projeto
    titulo("7) PROJETO E CÁLCULO")
    arq = perguntar_texto("Nome do arquivo do projeto", "Sapata_modelo.p3d")
    if not arq.lower().endswith(".p3d"):
        arq += ".p3d"
    P["projeto"] = os.path.join(PASTA, arq)
    P["calcular"] = perguntar_sim_nao("Calcular agora?", True)
    return P


def resumo(P):
    d, f, c, m = P["dominio"], P["sapata"], P["carga"], P["malha"]
    dirs = {1: "vertical para baixo", 2: "vertical para cima", 3: "horizontal +X",
            4: "horizontal +Y", 5: "momento"}
    print("\n" + "=" * 70)
    print(" RESUMO")
    print("=" * 70)
    print(" Domínio : x [{}, {}]  y [{}, {}]  profundidade {} m".format(
        fmt(d["xmin"]), fmt(d["xmax"]), fmt(d["ymin"]), fmt(d["ymax"]), fmt(d["H"])))
    top = 0.0
    for i, cam in enumerate(P["camadas"], 1):
        base = top - cam["espessura"]
        print(" Camada {}: {:<10} z {} a {}  γ {}/{}  E' {}  ν' {}  c' {}  φ' {}  ψ {}".format(
            i, cam["nome"], fmt(top), fmt(base), fmt(cam["gamma_unsat"]), fmt(cam["gamma_sat"]),
            fmt(cam["E"]), fmt(cam["nu"]), fmt(cam["c"]), fmt(cam["phi"]), fmt(cam["psi"])))
        top = base
    print(" N.A.    : z = {} m".format(fmt(P["nivel_agua"])))
    print(" Sapata  : centro ({}, {}, {})  {} x {} m  d = {} m  (γ {}, E {}, ν {})".format(
        fmt(f["cx"]), fmt(f["cy"]), fmt(f["cz"]), fmt(f["L"]), fmt(f["W"]), fmt(f["d"]),
        fmt(f["gamma"]), fmt(f["E"]), fmt(f["nu"])))
    print("           modelada como {} | material \"{}\"".format(
        "PLACA elástica" if f.get("modelo", "placa") == "placa" else "VOLUME linear elástico não poroso",
        f.get("nome_material", "Footing")))
    info = P.get("info", {})
    if info.get("titulo", TITULO_PADRAO) != TITULO_PADRAO or info.get("empresa"):
        print(" Projeto : Title \"{}\"  Company \"{}\"".format(info.get("titulo"), info.get("empresa", "")))
    if c.get("modo") == "nenhuma":
        print(" Ação    : NENHUMA (sem carga e sem deslocamento): só o peso próprio da sapata")
    elif c.get("modo") == "combinado":
        cp, dp = c["carga_parte"], c["desl_parte"]
        print(" Ação    : COMBINADA ({})".format("em sequência: carga e depois deslocamento"
                                                if c["sub"] == "sequencia" else "na mesma fase"))
        print("           carga: {} {} - {} - {}".format(
            fmt(cp["valor"]), cp["unidade"], dirs[cp["direcao"]],
            "distribuída" if cp["tipo"] == 1 else "concentrada"))
        print("           deslocamento prescrito: {} cm - {} (mín. {} passos)".format(
            fmt(dp["valor"] * 100.0), dirs[dp["direcao"]], dp["passos"]))
    elif c.get("modo") == "deslocamento":
        print(" Ação    : deslocamento prescrito de {} cm - {} (mín. {} passos)".format(
            fmt(c["valor"] * 100.0), dirs[c["direcao"]], c["passos"]))
    else:
        print(" Carga   : {} {} - {} - {}".format(
            fmt(c["valor"]), c["unidade"], dirs[c["direcao"]],
            "distribuída" if c["tipo"] == 1 else "concentrada"))
    if c.get("extra"):
        ex = c["extra"]
        print("           + segunda carga: {} {} - {} - {}".format(
            fmt(ex["valor"]), ex["unidade"], dirs[ex["direcao"]],
            "distribuída" if ex["tipo"] == 1 else "concentrada"))
    print(" Malha   : {} (fator {}); refino na sapata: {}".format(
        m["nome"], fmt(m["fator"]), "coarseness {}".format(fmt(m["coarseness"])) if m["refinar"] else "não"))
    print(" Projeto : {}  | calcular: {}".format(P["projeto"], "sim" if P["calcular"] else "não"))
    print("=" * 70)


# ----------------------------------------------------------------------------
# Utilitários de modelagem
# ----------------------------------------------------------------------------
def primeiro(res):
    if isinstance(res, (tuple, list)):
        return res[0]
    return res


def tentar(descricao, *funcs):
    erros = []
    for i, f in enumerate(funcs):
        try:
            r = f()
            if i > 0:
                print("    (aviso) '{}' funcionou pela alternativa {}".format(descricao, i + 1))
            return r
        except Exception as e:  # noqa
            msg = str(e).strip().splitlines()
            erros.append("alt {}: {}".format(i + 1, msg[-1] if msg else repr(e)))
    raise RuntimeError("Falhou: {}\n    ".format(descricao) + "\n    ".join(erros))


def definir_props(obj, descricao, lista):
    """Seta uma propriedade por vez (nomes/valores alternativos) e lista tudo que falhar."""
    falhas = []
    for nomes, valores in lista:
        if isinstance(nomes, str):
            nomes = (nomes,)
        if not isinstance(valores, tuple):
            valores = (valores,)
        ok, ultimo = False, None
        for nome in nomes:
            for v in valores:
                try:
                    obj.setproperties(nome, v)
                    ok = True
                    break
                except Exception as e:  # noqa
                    ultimo = e
            if ok:
                break
        if not ok:
            falhas.append("{} (erro: {})".format("/".join(nomes), str(ultimo).strip().splitlines()[-1]))
    if falhas:
        try:
            print("\n    --- propriedades reais de '{}' (echo) ---".format(descricao))
            print(obj.echo())
            print("    --- fim do echo ---")
        except Exception:
            pass
        raise RuntimeError("Propriedades de '{}' que NÃO foram aceitas:\n    - ".format(descricao)
                           + "\n    - ".join(falhas))


def setar_attr(obj, nome, valor):
    tentar(nome, lambda: setattr(obj, nome, valor), lambda: obj.setproperties(nome, valor))


def obter_senha():
    pw = globals().get("PLAXIS_PASSWORD") or os.environ.get("PLAXIS_PASSWORD")
    if not pw:
        pw = getpass.getpass("Senha do servidor PLAXIS: ")
    return pw


def _ler_lista(obj, nome="CoarsenessFactor"):
    try:
        cf = getattr(obj, nome)
    except Exception:
        return None
    for conv in (lambda: [float(v) for v in cf],
                 lambda: [float(v) for v in cf.value],
                 lambda: [float(cf)]):
        try:
            return conv()
        except Exception:
            continue
    return None


def _num_ou_lista(txt):
    """Extrai os números que aparecem depois de 'CoarsenessFactor' num texto de echo()."""
    import re
    achados = []
    for mt in re.finditer(r"CoarsenessFactor[^0-9\-+\n]*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)", txt):
        achados.append(float(mt.group(1)))
    return achados or None


def ler_coarseness_servidor(nome):
    """Lê o coarseness de um objeto buscado de novo em g_i (echo() vem do servidor)."""
    try:
        obj = getattr(g_i, nome)
    except Exception:
        return None
    try:
        v = _num_ou_lista(str(obj.echo()))
        if v:
            return v
    except Exception:
        pass
    return _ler_lista(obj)


def _confere(nome, valor):
    lido = ler_coarseness_servidor(nome)
    return bool(lido) and all(abs(v - valor) < 1e-9 for v in lido), lido


def aplicar_coarseness(valor):
    """
    O coarseness de uma superfície fica nos polígonos do modo Mesh (Polygon_1_1, ...), e não em
    Polygon_1. No log do Exemplo 1 o comando que funcionou foi 'set Polygon_1_1.CoarsenessFactor 0.1'.
    Tenta (1) direto nos Polygon_1_N existentes e (2) por índice em Polygon_1.CoarsenessFactor[i].
    Devolve True se algum caminho foi confirmado lendo de volta do servidor.
    """
    nomes = []
    for j in range(1, 13):
        nome = "Polygon_1_{}".format(j)
        try:
            getattr(g_i, nome).echo()
            nomes.append(nome)
        except Exception:
            pass
    print("    Polígonos do modo Mesh encontrados: {}".format(nomes or "nenhum"))

    for nome in nomes:
        print("    {}: coarseness atual = {}".format(nome, ler_coarseness_servidor(nome)))
        for rotulo, f in (
            ("atribuição direta", lambda n=nome: setattr(getattr(g_i, n), "CoarsenessFactor", valor)),
            ("setproperties", lambda n=nome: g_i.setproperties(getattr(g_i, n), "CoarsenessFactor", valor)),
        ):
            try:
                f()
            except Exception as e:  # noqa
                msg = str(e).strip().splitlines()
                print("    - {} em {}: erro ({})".format(rotulo, nome, msg[0] if msg else repr(e)))
                continue
            ok, lido = _confere(nome, valor)
            if ok:
                print("    {}: coarseness = {}  (OK via '{}', conferido no servidor)".format(nome, lido, rotulo))
                break
            print("    - {} em {}: não confirmado (lido de volta: {})".format(rotulo, nome, lido))
    if nomes and all(_confere(n, valor)[0] for n in nomes):
        return True

    # Caminho 2: lista em Polygon_1 (era assim no primeiro teste do Exemplo 1)
    try:
        poly = g_i.Polygon_1
        antes = _ler_lista(poly)
        print("    Polygon_1.CoarsenessFactor antes: {}".format(antes))
        for i in range(len(antes) if antes else 1):
            poly.CoarsenessFactor[i] = valor
        ok, lido = _confere("Polygon_1", valor)
        print("    Polygon_1.CoarsenessFactor depois: {} ({})".format(lido, "OK" if ok else "não confirmado"))
        if ok and (not nomes or all(_confere(n, valor)[0] for n in nomes)):
            return True
    except Exception as e:  # noqa
        msg = str(e).strip().splitlines()
        print("    - por índice em Polygon_1: erro ({})".format(msg[0] if msg else repr(e)))

    # Caminho 3: a MESMA sequência de tentativas do exemplo1_modelo.py (a que funcionou no Exemplo 1),
    # na mesma ordem, caso o índice só funcione depois das tentativas anteriores.
    try:
        poly = g_i.Polygon_1
        n = len(_ler_lista(poly) or [1])

        def _por_indice():
            for i in range(n):
                poly.CoarsenessFactor[i] = valor

        for rotulo, f in (
            ("setproperties escalar", lambda: g_i.setproperties(poly, "CoarsenessFactor", valor)),
            ("atribuição escalar", lambda: setattr(poly, "CoarsenessFactor", valor)),
            ("atribuição em lista", lambda: setattr(poly, "CoarsenessFactor", [valor] * n)),
            ("setproperties em lista", lambda: g_i.setproperties(poly, "CoarsenessFactor", [valor] * n)),
            ("por índice", _por_indice),
        ):
            try:
                f()
            except Exception as e:  # noqa
                msg = str(e).strip().splitlines()
                print("    - (sequência do Ex.1) {}: erro ({})".format(rotulo, msg[0] if msg else repr(e)))
        for nome in (nomes or ["Polygon_1"]):
            ok, lido = _confere(nome, valor)
            print("    {}: coarseness após a sequência do Ex.1 = {} ({})".format(
                nome, lido, "OK" if ok else "não confirmado"))
            if ok:
                return True
    except Exception as e:  # noqa
        msg = str(e).strip().splitlines()
        print("    - sequência do Ex.1: erro ({})".format(msg[0] if msg else repr(e)))
    return False


def definir_passos_minimos(fase, n):
    """
    Limita a fração de carga/deslocamento por passo (Deform.MaxLoadFractionPerStep = 1/n) para a fase
    ter pelo menos n passos, ou seja, mais pontos na curva. Precisa desligar UseDefaultIterationParams.
    Não é fatal: se falhar, o cálculo segue com os passos automáticos do PLAXIS.
    """
    frac = 1.0 / float(n)
    try:
        fase.Deform.setproperties("UseDefaultIterationParams", False)
        fase.Deform.setproperties("MaxLoadFractionPerStep", frac)
    except Exception as e:  # noqa
        msg = str(e).strip().splitlines()
        print("    (aviso) não consegui limitar o passo da fase: {}".format(msg[-1] if msg else repr(e)))
        return False
    try:
        lido = None
        for linha in str(fase.Deform.echo()).splitlines():
            if "MaxLoadFractionPerStep" in linha:
                lido = float(linha.split(":")[1].split()[0])
        print("    MaxLoadFractionPerStep = {:g} (pelo menos {} passos){}".format(
            frac, n, "" if lido is not None and abs(lido - frac) < 1e-9 else "  [não confirmado: lido {}]".format(lido)))
    except Exception:
        print("    MaxLoadFractionPerStep = {:g} (pelo menos {} passos)".format(frac, n))
    return True


def ativar(descricao, nomes, fase):
    """Ativa um objeto numa fase pelo NOME (activate Plate_1 Phase_1 funcionou no PLAXIS real)."""
    tentativas = [(lambda n=n: g_i.activate(getattr(g_i, n), fase)) for n in nomes]
    tentar(descricao, *tentativas)


# ----------------------------------------------------------------------------
# Construção do modelo
# ----------------------------------------------------------------------------
def construir(P):
    d, f, c, m = P["dominio"], P["sapata"], P["carga"], P["malha"]
    volume = (f.get("modelo", "placa") == "volume")
    # Pelo executor externo, s_i/g_i já chegam conectados (porta do executor): não pergunta a porta.
    # Só se o script for rodado sem o executor (sem g_i) é que pergunta a porta antes da senha.
    sem_executor = globals().get("g_i") is None
    porta_in = PORTA_PADRAO
    if sem_executor:
        print("\n  Conexão com o PLAXIS Input (executor externo não detectado):")
        porta_in = perguntar_int("Porta do servidor Input", PORTA_PADRAO, 1, 65535)
    senha = obter_senha()
    if sem_executor:
        etapa("Conectando ao PLAXIS Input em {}:{}".format(HOST, porta_in))
        s_novo, g_novo = new_server(HOST, porta_in, password=senha)
        globals()["s_i"], globals()["g_i"] = s_novo, g_novo

    verificar_conexao()
    info = P.get("info", {})
    etapa("Novo projeto")
    s_i.new()
    g_i.setproperties("Title", info.get("titulo") or TITULO_PADRAO,
                      "UnitForce", "kN", "UnitLength", "m", "UnitTime", "day", "WaterWeight", 10.0)
    if info.get("empresa"):
        try:
            g_i.setproperties("Company", info["empresa"])
        except Exception as e:  # noqa
            aviso("não consegui definir Company: {}".format(str(e).strip().splitlines()[-1]))
    g_i.SoilContour.initializerectangular(d["xmin"], d["ymin"], d["xmax"], d["ymax"])

    etapa("Borehole em ({}, {}), N.A. z = {}".format(fmt(d["xmin"]), fmt(d["ymin"]), fmt(P["nivel_agua"])))
    borehole = g_i.borehole(d["xmin"], d["ymin"])
    borehole.Head = P["nivel_agua"]
    if len(P["camadas"]) > 1:
        aviso("várias camadas (não testado).")
    for cam in P["camadas"]:
        g_i.soillayer(cam["espessura"])

    etapa("Materiais do solo (Mohr-Coulomb, drenado)")
    mats = []
    for cam in P["camadas"]:
        mat = g_i.soilmat()
        definir_props(mat, "solo " + cam["nome"], [
            (("Identification", "MaterialName"), cam["nome"]),
            ("SoilModel", (2, "Mohr-Coulomb")),
            ("DrainageType", ("Drained", 0)),
            (("gammaUnsat", "gamma_unsat"), cam["gamma_unsat"]),
            (("gammaSat", "gamma_sat"), cam["gamma_sat"]),
            (("Eref", "E"), cam["E"]),
            ("nu", cam["nu"]),
            (("cref", "c"), cam["c"]),
            (("phi", "phi_ref"), cam["phi"]),
            ("psi", cam["psi"]),
        ])
        mats.append(mat)
    etapa("Atribuindo materiais às camadas")
    for i, mat in enumerate(mats):
        g_i.Soillayers[i].Soil.Material = mat

    if not volume:
        etapa("Material da sapata (placa elástica isotrópica)")
        mat_sapata = g_i.platemat()
        definir_props(mat_sapata, "sapata (identificação/tipo)", [
            (("Identification", "MaterialName"), f.get("nome_material", "Footing")),
            (("MaterialType", "PlateType"), ("Elastic", 0)),
        ])
        definir_props(mat_sapata, "sapata", [
            (("Isotropic", "isotropic"), True),
            (("gamma", "Gamma"), f["gamma"]),
            (("d", "D", "Thickness"), f["d"]),
            (("E1", "E", "Eref"), f["E"]),
            (("StructNu12", "nu12", "nu", "Nu12"), f["nu"]),
        ])
    else:
        etapa("Material da sapata (volume Linear Elástico, não poroso) (não testado)")
        mat_sapata = g_i.soilmat()
        definir_props(mat_sapata, "sapata (volume linear elástico não poroso)", [
            (("Identification", "MaterialName"), f.get("nome_material", "Footing")),
            ("SoilModel", (1, "Linear Elastic")),
            ("DrainageType", ("Non-porous", "NonPorous", 4)),
            (("gammaUnsat", "gamma_unsat"), f["gamma"]),
            (("Eref", "E"), f["E"]),
            ("nu", f["nu"]),
        ])

    etapa("Modo Structures: superfície {} x {} m em z = {}".format(fmt(f["L"]), fmt(f["W"]), fmt(f["cz"])))
    g_i.gotostructures()
    hx, hy, z0 = f["L"] / 2.0, f["W"] / 2.0, f["cz"]
    x0, y0 = f["cx"], f["cy"]
    poly = primeiro(g_i.surface((x0 - hx, y0 + hy, z0), (x0 + hx, y0 + hy, z0),
                                (x0 + hx, y0 - hy, z0), (x0 - hx, y0 - hy, z0)))
    alvos = [poly]
    try:
        alvos.append(g_i.Polygon_1)
    except Exception:
        pass

    def criar(cmds, objs=None):
        """Tenta cada comando em cada alvo; se tudo falhar mostra todos os erros."""
        if isinstance(cmds, str):
            cmds = (cmds,)
        erros = []
        for cmd in cmds:
            for a in (objs or alvos):
                try:
                    return primeiro(getattr(g_i, cmd)(a))
                except Exception as e:  # noqa
                    msg = str(e).strip().splitlines()
                    erros.append("g_i.{}({}) -> {}".format(cmd, a, msg[-1] if msg else repr(e)))
        raise RuntimeError("Nenhuma tentativa funcionou:\n    " + "\n    ".join(erros))

    vol_objs = []
    if volume:
        etapa("Extrudando a superfície em volume: z de {} até {} (não testado)".format(
            fmt(z0), fmt(z0 - f["d"])))
        res_ext = tentar("extrude",
                         lambda: g_i.extrude(poly, 0, 0, -f["d"]),
                         lambda: g_i.extrude(g_i.Polygon_1, 0, 0, -f["d"]),
                         lambda: g_i.extrude([poly], 0, 0, -f["d"]))
        vol_objs = list(res_ext) if isinstance(res_ext, (list, tuple)) else [res_ext]
    else:
        etapa("Convertendo a superfície em placa")
        placa = criar("plate")
        placa.Material = mat_sapata

    # --- Ação: funções independentes por tipo (os comandos de cada uma não mudam)
    def criar_carga(cc):
        if cc["direcao"] == 5:
            etapa("Momento concentrado no centro da sapata (não testado)")
            rot = {1: "Mx", 2: "My", 3: "Mz"}[cc["eixo"]]
            pt = tentar("ponto no centro da sapata",
                        lambda: primeiro(g_i.point(x0, y0, z0)),
                        lambda: (x0, y0, z0))
            carga = tentar("criar momento",
                           lambda: primeiro(g_i.pointmoment(pt)),
                           lambda: primeiro(g_i.moment(pt)),
                           lambda: primeiro(g_i.pointmoment(x0, y0, z0)))
            setar_attr(carga, rot, cc["valor"])
            return carga, ["PointMoment_1", "Moment_1", "PointLoad_1"]
        if cc["tipo"] == 1:
            etapa("Carga distribuída (surface load)")
            carga = criar(("surfload", "surfaceload", "surfaceLoad"))
            comp = {1: ("sigz", -1.0), 2: ("sigz", 1.0), 3: ("sigx", 1.0), 4: ("sigy", 1.0)}[cc["direcao"]]
            setar_attr(carga, comp[0], comp[1] * cc["valor"])
            return carga, ["SurfaceLoad_1"]
        etapa("Carga concentrada no centro da sapata (point load) (não testado)")
        pt = tentar("ponto no centro da sapata",
                    lambda: primeiro(g_i.point(x0, y0, z0)),
                    lambda: (x0, y0, z0))
        carga = tentar("criar carga pontual",
                       lambda: primeiro(g_i.pointload(pt)),
                       lambda: primeiro(g_i.pointload((x0, y0, z0))),
                       lambda: primeiro(g_i.pointload(x0, y0, z0)))
        comp = {1: ("Fz", -1.0), 2: ("Fz", 1.0), 3: ("Fx", 1.0), 4: ("Fy", 1.0)}[cc["direcao"]]
        setar_attr(carga, comp[0], comp[1] * cc["valor"])
        return carga, ["PointLoad_1"]

    def criar_desl(dd):
        etapa("Deslocamento prescrito de superfície: {} cm".format(fmt(dd["valor"] * 100.0)))
        if dd["direcao"] != 1:
            aviso("deslocamento prescrito para cima/horizontal (não testado).")
        obj = criar(("surfdispl", "surfacedisplacement", "surfdisplacement", "surfdisp"))
        eixo_i = {1: "z", 2: "z", 3: "x", 4: "y"}[dd["direcao"]]
        sgn = {1: -1.0, 2: 1.0, 3: 1.0, 4: 1.0}[dd["direcao"]]
        # Eixo prescrito = Prescribed; os outros ficam livres (validado no Exemplo 2: Free/Free/Prescribed).
        for eixo_o in ("x", "y", "z"):
            modo_txt = "Prescribed" if eixo_o == eixo_i else "Free"
            try:
                definir_props(obj, "deslocamento prescrito (eixo " + eixo_o + ")",
                              [(("Displacement_" + eixo_o,), (modo_txt, 2 if modo_txt == "Prescribed" else 0))])
            except Exception as e:  # noqa
                if eixo_o == eixo_i:
                    raise
                print("    (aviso) não consegui deixar {} livre: {}".format(eixo_o, str(e).splitlines()[0]))
        definir_props(obj, "deslocamento prescrito (valor)",
                      [((("u" + eixo_i), "u" + eixo_i + "_start"), sgn * dd["valor"])])
        try:
            print(obj.echo())
        except Exception:
            pass
        return obj, ["SurfaceDisplacement_1", "PrescribedDisplacement_1", "SurfDispl_1"]

    modo = c.get("modo", "carga")
    modo_desl = (modo in ("deslocamento", "combinado"))      # curva por reação do deslocamento prescrito
    nomes_carga, nomes_desl, nomes_extra = [], [], []
    if modo == "nenhuma":
        etapa("Sem carga e sem deslocamento: só o peso próprio da sapata")
    elif modo == "carga":
        _, nomes_carga = criar_carga(c)
    elif modo == "deslocamento":
        _, nomes_desl = criar_desl(c)
    else:
        _, nomes_carga = criar_carga(c["carga_parte"])
        _, nomes_desl = criar_desl(c["desl_parte"])
    if c.get("extra"):
        _, nomes_extra = criar_carga(c["extra"])
    if volume and modo == "nenhuma":
        try:
            g_i.delete(poly)          # como no manual: a superfície auxiliar é apagada, o volume fica
        except Exception as e:  # noqa
            aviso("não consegui apagar a superfície auxiliar: {}".format(str(e).strip().splitlines()[-1]))

    # --- Malha
    etapa("Modo Mesh: preset '{}' (fator {})".format(m["nome"], fmt(m["fator"])))
    g_i.gotomesh()
    if m["refinar"]:
        ok = False
        try:
            ok = aplicar_coarseness(m["coarseness"])
        except Exception as e:  # noqa
            print("    - coarseness: {}".format(str(e).strip().splitlines()[0]))
        if not ok:
            print("\n    (ATENÇÃO) Não consegui aplicar/confirmar o coarseness factor {} por script.".format(
                fmt(m["coarseness"])))
            print("    Sem o refino a malha fica mais grossa sob a sapata e a capacidade de carga sai SUPERESTIMADA.")
            print("    No PLAXIS Input (modo Mesh): selecione a superfície da sapata (Polygon_1_1) e coloque")
            print("    Coarseness factor = {} no Selection explorer.".format(fmt(m["coarseness"])))
            resp = _ler("Depois de ajustar, tecle Enter para gerar a malha (ou digite x para cancelar)", "")
            if resp.lower() == "x":
                raise RuntimeError("Cancelado pelo usuário: coarseness não aplicado.")
    res_malha = g_i.mesh(m["fator"])
    if res_malha not in (None, "", True):
        print("    mesh ->", res_malha)
    print("    Malha gerada. Confira 'Generated N elements' no log do PLAXIS "
          "(Exemplo 1 com 'fine' + coarseness 0,1 = 23855).")

    etapa("Nó para a curva carga x deslocamento em ({}, {}, {})".format(fmt(x0), fmt(y0), fmt(z0)))
    porta_out = g_i.selectmeshpoints()
    s_o, g_o = new_server(HOST, porta_out, password=senha)
    g_o.addcurvepoint("node", x0, y0, z0)
    g_o.update()

    # --- Fases
    if modo == "nenhuma":
        seq_fases = "(nenhuma: só peso próprio)"
    elif modo == "carga":
        seq_fases = "Load"
    elif modo == "deslocamento":
        seq_fases = "Displacement"
    elif c["sub"] == "sequencia":
        seq_fases = "Load -> Displacement"
    else:
        seq_fases = "Combined"
    etapa("Modo Staged construction: Initial (K0) -> Footing -> {}".format(seq_fases))
    g_i.gotostages()
    tentar("Initial phase = K0 procedure",
           lambda: setattr(g_i.InitialPhase, "DeformCalcType", "K0 procedure"),
           lambda: g_i.InitialPhase.setproperties("DeformCalcType", "K0 procedure"))
    fase_sapata = g_i.phase(g_i.InitialPhase)
    fase_sapata.Identification = "Footing"
    fase_sapata.Deform.ResetDisplacementsToZero = True
    if volume:
        etapa("Atribuindo o material '{}' ao volume da sapata na fase Footing (não testado)".format(
            f.get("nome_material", "Footing")))
        # O extrude devolve vários objetos (ex.: Volume_1 e Soil_2). No PLAXIS real o comando que funcionou
        # foi 'setmaterial Volume_1 Phase_1 Building'; os demais objetos podem falhar sem problema.
        feito, erros_vol = False, []
        for v in vol_objs:
            try:
                tentar("material do volume da sapata na fase Footing",
                       lambda v=v: g_i.setmaterial(v, fase_sapata, mat_sapata),
                       lambda v=v: v.Soil.Material.__setitem__(fase_sapata, mat_sapata),
                       lambda v=v: g_i.setmaterial(v.Soil, fase_sapata, mat_sapata),
                       lambda v=v: v.Material.__setitem__(fase_sapata, mat_sapata))
                feito = True
                break
            except Exception as e:  # noqa
                erros_vol.append(str(e))
        if not feito:
            for e_txt in erros_vol:
                print("    - {}".format(e_txt))
            for v in vol_objs:
                try:
                    print(v.echo())
                except Exception:
                    pass
        if not feito:
            print("\n    (ATENÇÃO) Não consegui atribuir o material por script.")
            print("    No PLAXIS Input (Staged construction): na fase 'Footing', clique com o botão direito no")
            print("    volume da sapata > Set material > '{}'.".format(f.get("nome_material", "Footing")))
            resp = _ler("Depois de atribuir, tecle Enter para continuar (ou digite x para cancelar)", "")
            if resp.lower() == "x":
                raise RuntimeError("Cancelado pelo usuário: material do volume não atribuído.")
    else:
        ativar("ativar placa na fase Footing", ["Plate_1"], fase_sapata)

    if modo == "nenhuma":
        pass                                  # só a fase Footing (peso próprio)
    elif modo in ("carga", "deslocamento"):
        nome_fase = "Load" if modo == "carga" else "Displacement"
        fase_carga = g_i.phase(fase_sapata)
        fase_carga.Identification = nome_fase
        fase_carga.Deform.ResetDisplacementsToZero = True     # deslocamento só após aplicar a ação
        ativar("ativar ação na fase " + nome_fase, nomes_carga or nomes_desl, fase_carga)
        if nomes_extra:
            ativar("ativar a segunda carga na fase " + nome_fase, nomes_extra, fase_carga)
        if modo == "deslocamento":
            definir_passos_minimos(fase_carga, c["passos"])
    elif c["sub"] == "sequencia":
        fase_carga = g_i.phase(fase_sapata)
        fase_carga.Identification = "Load"
        fase_carga.Deform.ResetDisplacementsToZero = True
        ativar("ativar carga na fase Load", nomes_carga, fase_carga)
        if nomes_extra:
            ativar("ativar a segunda carga na fase Load", nomes_extra, fase_carga)
        definir_passos_minimos(fase_carga, c["passos"])
        fase_desl = g_i.phase(fase_carga)
        fase_desl.Identification = "Displacement"
        fase_desl.Deform.ResetDisplacementsToZero = False     # recalque acumulado (carga + deslocamento)
        ativar("ativar deslocamento prescrito na fase Displacement", nomes_desl, fase_desl)
        definir_passos_minimos(fase_desl, c["passos"])
    else:
        fase_comb = g_i.phase(fase_sapata)
        fase_comb.Identification = "Combined"
        fase_comb.Deform.ResetDisplacementsToZero = True
        ativar("ativar carga na fase Combined", nomes_carga, fase_comb)
        if nomes_extra:
            ativar("ativar a segunda carga na fase Combined", nomes_extra, fase_comb)
        ativar("ativar deslocamento prescrito na fase Combined", nomes_desl, fase_comb)
        definir_passos_minimos(fase_comb, c["passos"])

    # --- Parâmetros para o script de resultados
    dir_ref = c["direcao"]        # nos módulos 2 e 3 é a direção do deslocamento prescrito
    componente = {1: "Uz", 2: "Uz", 3: "Ux", 4: "Uy", 5: None}[dir_ref]
    sinal_u = {1: -1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0}[dir_ref]
    def kn_da(cc):
        if cc["direcao"] == 5:
            return None
        return cc["valor"] * (f["L"] * f["W"] if cc["tipo"] == 1 else 1.0)

    def total_kn_alinhado(prim, extra):
        """Força total (kN) na direção da carga principal, somando a 2ª carga se estiver no mesmo eixo."""
        base = kn_da(prim)
        if base is None or not extra:
            return base
        if extra["direcao"] != 5 and EIXO_DIR[extra["direcao"]] == EIXO_DIR[prim["direcao"]]:
            return base + kn_da(extra) * (1.0 if extra["direcao"] == prim["direcao"] else -1.0)
        aviso("a segunda carga não está no mesmo eixo da primeira: ela não entra na carga total da curva.")
        return base

    carga_json = dict(modo=modo, valor=c["valor"], unidade=c["unidade"],
                      direcao=dir_ref, tipo=c["tipo"], componente=componente, sinal=sinal_u,
                      reacao={1: "ReactionForceZ", 2: "ReactionForceZ", 3: "ReactionForceX",
                              4: "ReactionForceY", 5: None}[dir_ref])
    if modo == "combinado":
        cp = c["carga_parte"]
        kn_total = total_kn_alinhado(cp, c.get("extra"))
        carga_json.update(sub=c["sub"], carga_kN=kn_total, carga_direcao=cp["direcao"],
                          carga_tipo=cp["tipo"], carga_valor=cp["valor"], carga_unidade=cp["unidade"])
    if c.get("extra"):
        carga_json["extra"] = c["extra"]
        if modo == "carga":
            carga_json["carga_total_kN"] = total_kn_alinhado(c, c["extra"])
    dados = dict(
        versao=3, projeto=P["projeto"],
        carga=carga_json,
        sapata=dict(cx=x0, cy=y0, cz=z0, L=f["L"], W=f["W"], B=f["B"],
                    modelo=f.get("modelo", "placa"), gamma=f["gamma"], d=f["d"]),
    )
    with open(ARQUIVO_JSON, "w", encoding="utf-8") as fh:
        json.dump(dados, fh, indent=2, ensure_ascii=False)
    print("    Parâmetros gravados em {}".format(ARQUIVO_JSON))

    etapa("Salvando em " + P["projeto"])
    g_i.save(P["projeto"])

    if P["calcular"]:
        if modo == "nenhuma":
            etapa("Calculando (só peso próprio da sapata)")
        elif modo_desl:
            etapa("Calculando (com deslocamento imposto as fases devem terminar sem falha)")
        else:
            etapa("Calculando (a fase Load deve parar por falha de convergência perto da ruptura)")
        try:
            g_i.calculate()
        except Exception as e:  # noqa
            print("    calculate() levantou: {}".format(e))
        for fase in g_i.Phases:
            try:
                print("    {:<14} -> LogInfo {}".format(fase.Identification.value, fase.LogInfo.value))
            except Exception:
                pass
        try:
            g_i.save(P["projeto"])
        except Exception:
            pass
        print("\nModelo calculado. Rode plaxis_sapata_resultados.py com este projeto aberto.")
    else:
        print("\nModelo criado e salvo (sem calcular).")


# ----------------------------------------------------------------------------
# Principal
# ----------------------------------------------------------------------------
def verificar_conexao():
    """Leitura inofensiva só para detectar cedo se o servidor do PLAXIS Input parou de responder
    (evita preencher todas as perguntas e só então falhar em s_i.new())."""
    gi = globals().get("g_i")
    if gi is None:
        return
    try:
        gi.echo()
    except Exception as e:  # noqa
        txt = "{} {}".format(type(e).__name__, e)
        if "Connection" in txt or "10061" in txt or "Max retries" in txt:
            raise RuntimeError(
                "O PLAXIS Input não está respondendo (conexão recusada). Confira se o PLAXIS 3D Input continua "
                "aberto e se o servidor de scripts está ativo (Expert > Configure remote scripting server, "
                "'Start server', porta {}), e rode o executor de novo.".format(PORTA_PADRAO))


verificar_conexao()
dados_modelo = perguntar_tudo()
resumo(dados_modelo)
print("\n  ATENÇÃO: isto cria um NOVO projeto no PLAXIS (o projeto aberto agora será descartado).")
if perguntar_sim_nao("Continuar?", True):
    construir(dados_modelo)
else:
    print("\nCancelado. Nada foi alterado no PLAXIS.")

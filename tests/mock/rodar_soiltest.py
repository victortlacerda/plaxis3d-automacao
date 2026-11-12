# -*- coding: utf-8 -*-
"""Mock do PLAXIS (Input + SoilTest) para o soiltest/plaxis_soiltest_auto.py. Roda SEM o PLAXIS.

Uso: python3 rodar_soiltest.py <script> <modelo> <drenagem> ['{"json": "com ajustes do CONFIG"}']
Os resultados do falso SoilTest sao aproximados (servem para exercitar o fluxo, nao a mecanica).
"""
import sys, types, os, math, io
MODS={1:"Linear Elastic",2:"Mohr-Coulomb",3:"Hardening Soil",4:"HS small",5:"Soft Soil",8:"Modified Cam-Clay"}
DR={0:"Drained",1:"Undrained A",2:"Undrained B",3:"Undrained C",4:"Non-porous"}
class Num:
    def __init__(s,v): s.value=v
class Mat:
    def __init__(s): s.m=0; s.d=0; s.attrs=["Identification","SoilModel","DrainageType"]; s.v={}
    def build(s):
        m,d=s.m,s.d
        a=[]
        if m==2: a=["ERef","cRef","phi","psi","nu"]
        if m==1: a=["ERef","nu"]
        if m in (3,4): a=["E50Ref","EOedRef","EURRef","PowerM","nuUR","pRef","cRef","phi","psi","K0NC","RF","UseDefaults","DilatancyCutOff","eInit","eMax"]+(["G0Ref","gamma07"] if m==4 else [])
        if m==8: a=["lambda","kappa","M","nuUR","eInit","PhiInter"]
        if m==5: a=["lambdaModified","kappaModified","cRef","phi","psi","nuUR"]
        if d in (2,3):
            a=[x for x in a if x not in ("cRef","phi","psi","nu")]+["sURef","phiU"]+(["nuU"] if d==3 else (["nu"] if m in (1,2) else []))
        s.attrs=["Identification","SoilModel","DrainageType"]+a
    def setproperties(s,*a):
        for i in range(0,len(a),2):
            k,v=a[i],a[i+1]
            if k=="SoilModel":
                if isinstance(v,str): v=[n for n,x in MODS.items() if x==v][0]
                if v not in MODS: raise Exception("bad model")
                s.m=v; s.build()
            elif k=="DrainageType":
                if isinstance(v,str):
                    r=[n for n,x in DR.items() if x==v]
                    if not r: raise Exception("bad dren")
                    v=r[0]
                s.d=v; s.build()
            elif k in ("RF","K0NC") and s.v.get("UseDefaults",True): raise Exception("Cannot set read-only property "+k)
            elif k not in s.attrs: raise Exception("unknown "+k)
            else: s.v[k]=v
        return "OK"
    def __dir__(s): return s.attrs+["echo","setproperties"]
    def __getattr__(s,n):
        if n in s.__dict__.get("attrs",[]): return Num(s.v.get(n,0))
        raise AttributeError(n)
    def echo(s): return "SoilMat\n  SoilModel: %s (%d)\n  DrainageType: %s (%d)\n"%(MODS.get(s.m,"?"),s.m,DR[s.d],s.d)
class Gi:
    def __init__(s): s.Soils=[]
    def soilmat(s): m=Mat(); s.Soils.append(m); return m
    def soiltest(s,m):
        if m.m==5 and (m.v.get("lambdaModified",0)==0): raise Exception("Error: kappaModified is zero.")
        STATE["m"]=m; return 10001
STATE={}
class Res: pass

import json as _json, math as _m
class Ph:
    def setproperties(s,*a): return 'OK'
class Tst:
    NOME = ""
    def __init__(s):
        s.Results = Res(); s.p = {"Consolidation": "Isotropic", "K0": 1.0, "TestControlType": "Strain", "Behaviour": "Drained"}
        s.PhaseTable = []
    def _upd(s):
        P = s.p
        if "CellPressure" in P:
            sx = P["CellPressure"]; k0 = P["K0"] if P["Consolidation"] == "K0" else 1.0
            s.Sigxxinit = Num(-sx); s.Sigyyinit = Num(-sx / k0)
        if "AbsSigyyinit" in P:
            sy = P["AbsSigyyinit"]; k0 = P["K0"] if P["Consolidation"] == "K0" else 1.0
            s.Sigyyinit = Num(-sy); s.Sigxxinit = Num(-sy * k0)
    def setproperties(s, *a):
        for k, v in zip(a[::2], a[1::2]):
            if k == "K0" and s.p.get("Consolidation") == "Isotropic": raise Exception("Cannot set read-only property K0")
            if k == "PreconsolidationPressure" and STATE["m"].m in (1, 2): raise Exception("Cannot set read-only property PreconsolidationPressure")
            if k == "ShearStressAmplitude" and s.p.get("TestControlType") != "Stress": raise Exception("Cannot set read-only property ShearStressAmplitude")
            if k == "Behaviour" and v == "Undrained" and STATE["m"].d == 4: raise Exception('Invalid value: "Undrained"')
            s.p[k] = v
        s._upd(); return "OK"
    def addphase(s): s.PhaseTable.append(Ph())
    def deletephase(s, i): s.PhaseTable.pop(i)
    def __getattr__(s, n):
        if n in ("Sigxxinit", "Sigyyinit"): raise AttributeError(n)
        if n in s.__dict__.get("p", {}): return s.__dict__["p"][n]
        raise AttributeError(n)
def mv(k, d=0.0):
    return STATE["m"].v.get(k, d)
class Tri2(Tst):
    pass
class DSS2(Tst):
    pass
class Oed2(Tst):
    def __init__(s): Tst.__init__(s); s.PhaseTable = [Ph()]
class ST:
    def __init__(s):
        s.Triaxial = Tri2(); s.Oedometer = Oed2(); s.CRS = Oed2(); s.DSS = DSS2(); s.CDSS = DSS2(); s.CycTriaxial = Tri2()
        s.Material = types.SimpleNamespace(SoilModel=Num(0))
    def validate(s, x, *a): return "The material definition is valid."
    def calculate(s, t):
        s.Material.SoilModel = Num(STATE["m"].m)
        P = t.p; r = t.Results
        if t is s.Triaxial:
            n = P["Steps"]; sx = -t.Sigxxinit.value; sy = -t.Sigyyinit.value; q0 = sy - sx
            emax = P["MaximumStrain"] / 100; eps = [emax * i / n for i in range(n + 1)]
            qf = 2 * _m.sin(_m.radians(mv("phi", 30))) / (1 - _m.sin(_m.radians(mv("phi", 30)))) * (sx + mv("cRef", mv("cref", 0)) / _m.tan(_m.radians(mv("phi", 30))))
            q = [q0 + min(qf - q0, e * 40000 / (1 + e * 40000 / max(qf - q0, 1))) for e in eps]
            r.Epsyy = [-e for e in eps]; r.TotalVolumetricStrain = [0.1 * e for e in eps]; r.DeviatoricStress = q
            r.MeanEffStress = [-(sx + x / 3) for x in q]; r.SigyyE = [-(sx + x) for x in q]; r.SigxxE = [-sx for x in q]
            r.PExcess = [(-x / 3 if P["Behaviour"] == "Undrained" else 0.0) for x in q]
        elif t is s.DSS:
            n = P["Steps"]; sy = P["AbsSigyyinit"]; gm = P["MaximumShearStrain"] / 100
            cap = mv("cRef", 0) * _m.cos(_m.radians(mv("phi", 30))) + sy * _m.sin(_m.radians(mv("phi", 30)))
            g = [gm * i / n for i in range(n + 1)]
            r.Time = [0.0] * (n + 1); r.Gamxy = g; r.Sigxy = [min(cap, x * 20000) for x in g]
            r.SigyyE = [-sy] * (n + 1); r.SigxxE = [-sy] * (n + 1); r.TotalVolumetricStrain = [0.0] * (n + 1)
            r.PExcess = [(-x / 5 if P["Behaviour"] == "Undrained" else 0.0) for x in r.Sigxy]
        elif t is s.CDSS or t is s.CycTriaxial:
            spq = P["NumberOfStepsPerQuarterCycle"]; cyc = P["NumberOfCycles"]; N = (4 * cyc + 1) * spq
            A = P.get("ShearStrainAmplitude", P.get("AxialStrainAmplitude", 0.5)) / 100
            E = mv("ERef", 30000); nu = mv("nu", 0.3); G = E / (2 * (1 + nu))
            ph = [2 * _m.pi * k / (4 * spq) for k in range(N + 1)]
            r.Time = [P["DurationPerCycle"] * k / (4 * spq) for k in range(N + 1)]
            if t is s.CDSS:
                sy = P["AbsSigyyinit"]
                r.Gamxy = [A * _m.sin(x) for x in ph]
                r.Sigxy = [G * A * _m.sin(x) + 0.01 * G * A * _m.cos(x) - 0.01 * G * A for x in ph]
                r.SigyyE = [-sy] * (N + 1); r.SigxxE = [-sy] * (N + 1); r.Epsyy = [0.0] * (N + 1)
                r.TotalVolumetricStrain = [0.0] * (N + 1)
                r.PExcess = [(-0.2 * k if P["Behaviour"] == "Undrained" else 0.0) for k in range(N + 1)]
            else:
                sx = -t.Sigxxinit.value; Em = E if P["Behaviour"] == "Drained" else 3 * G
                r.Epsyy = [A * _m.sin(x) for x in ph]
                q = [Em * A * _m.sin(x) for x in ph]
                r.SigyyE = [-(sx + v) for v in q]; r.SigxxE = [-sx] * (N + 1)
                r.MeanEffStress = [-(sx + v / 3) for v in q]; r.TotalVolumetricStrain = [0.0] * (N + 1)
                r.PExcess = [(-0.1 * k if P["Behaviour"] == "Undrained" else 0.0) for k in range(N + 1)]
        else:
            n = 60; r.Time = [i / 10 for i in range(n + 1)]
            E = mv("ERef", 30000); nu = mv("nu", 0.3); eoed = E * (1 - nu) / ((1 + nu) * (1 - 2 * nu))
            sv = [4 * i for i in range(n + 1)]
            r.SigyyE = [-v for v in sv]; r.SigxxE = [-0.43 * v for v in sv]; r.Epsyy = [-v / eoed for v in sv]
            r.PExcess = [0.0] * (n + 1)
        return "OK"
m = types.ModuleType("plxscripting"); e = types.ModuleType("plxscripting.easy")
e.new_server = lambda h, p, **k: (None, ST()) if p > 10000 else (_ for _ in ()).throw(ConnectionError())
sys.modules["plxscripting"] = m; sys.modules["plxscripting.easy"] = e
os.environ["PLAXIS_PASSWORD"] = "x"
script, modelo, dren = sys.argv[1], sys.argv[2], sys.argv[3]
patch = _json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
src = open(script, encoding="utf-8").read()
p = os.path.join(os.getcwd(), os.path.basename(script))   # saidas vao para a pasta atual
ns = {"__name__": "auto", "__file__": p, "s_i": object(), "g_i": Gi()}
exec(compile(src, p, "exec"), ns, ns)
for ex in patch.get("_existentes", []):     # materiais que ja estao no "projeto": {"m":3,"d":0,"nome":"Areia","v":{...}}
    mt = ns["g_i"].soilmat(); mt.setproperties("SoilModel", ex["m"], "DrainageType", ex["d"])
    mt.v.update(ex.get("v", {})); mt.v["Identification"] = ex["nome"]
C = ns["CONFIG"]; C["interativo"] = False; C["modelo"] = modelo; C["drenagem"] = dren
for k, v in patch.items():
    if k in ('_inter', '_existentes'): continue
    if isinstance(v, dict) and isinstance(C.get(k), dict): C[k].update(v)
    else: C[k] = v
if patch.get("_inter"): C["interativo"]=True
rc = ns["main"]()
print("RC", rc)

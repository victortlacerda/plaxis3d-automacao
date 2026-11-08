"""Fake do Output para os estudos: curva carga x recalque com ruptura perto de ΣMstage = 0,8."""
class V:
    def __init__(s, v): s.value = v
class Reached:
    def __init__(s, m):
        s.SumMstage = V(m)
        s.ForceZ = V(-3000.0 * m * (1 - 0.5 * m))
class Step:
    def __init__(s, m): s.Reached = Reached(m)
MS = [i / 100.0 for i in range(2, 80, 2)] + [0.79, 0.795, 0.798]
class Ph:
    def __init__(s, n, ms): s.Identification = V(n); s.Steps = V([Step(m) for m in ms])
class Soil: Uz = "Uz"
class PD: ReactionForceZ = "RFZ"
class RT:
    Soil = Soil; PrescribedDisplacement = PD; SurfaceDisplacement = type("E", (), {})
class GO:
    Phases = [Ph("Footing", [1.0]), Ph("Load", MS)]
    Nodes = ["no"]; ResultTypes = RT(); PrescribedDisplacements = ["pd"]
    def addcurvepoint(s, *a): print("   [O] addcurvepoint", a)
    def update(s): print("   [O] update")
    def getcurveresults(s, no, st, rt):
        m = st.Reached.SumMstage.value
        return -0.004 * m / (0.82 - m)
    def getresults(s, obj, st, rt, loc=None):
        m = st.Reached.SumMstage.value
        if rt == "RFZ": return [-1500.0 * m * (1 - 0.5 * m)] * 2
        raise RuntimeError("nao")
    def close(s): pass
def new_server(h, p, password=None):
    print("   [new_server]", h, p)
    return None, GO()

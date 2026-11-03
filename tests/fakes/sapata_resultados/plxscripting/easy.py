import os
class V:
    def __init__(s, v): s.value = v
class Reached:
    def __init__(s, m):
        s.SumMstage = V(m)
        s.ForceZ = V(-3000.0*m*(1-0.5*m)) if not os.environ.get('RZ_ERRADO') else V(-1.0)
class Step:
    def __init__(s, m): s.Reached = Reached(m)
steps = [Step(i/50.0) for i in range(1, 51)]
class Ph:
    Identification = V("Settlement"); Steps = V(steps)
class Soil: Uz = "Uz"
class Surf: Fz = "SurfFz"; Name = "x"
class PD: ReactionForceZ="RFZ"
class RT:
    Soil = Soil
    PrescribedDisplacement = PD
    SurfaceDisplacement = Surf if os.environ.get("COM_FORCA") else type("E", (), {})
class PhL:
    Identification = V('Load'); Steps = V([Step(i/10.0) for i in range(1, 11)])
class GO:
    Phases = [PhL(), Ph()]; Nodes = ["no"]; ResultTypes = RT()
    PrescribedDisplacements = ["pd"]
    def getcurveresults(s, no, st, rt):
        return -0.0249998 * st.Reached.SumMstage.value
    def getresults(s, obj, st, rt, loc=None):
        if os.environ.get("SO_ULTIMO") and st is not steps[-1]: raise RuntimeError("Invalid step or phase. Phase has not been previewed or calculated yet.")
        if rt == "RFZ": return [-1500.0*st.Reached.SumMstage.value*(1-0.5*st.Reached.SumMstage.value)]*2
        if rt == "SurfFz": return [-1500.0*st.Reached.SumMstage.value]*2   # soma 3000*M
        raise RuntimeError("nao")
    def close(s): pass
def new_server(h, p, password=None): return None, GO()

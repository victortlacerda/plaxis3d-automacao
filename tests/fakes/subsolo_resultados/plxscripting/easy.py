import math, os
class V:
    def __init__(s, v): s.value = v
class Step:
    pass
class Ph:
    def __init__(s, n): s.Identification = V(n); s.Steps = V([Step(), Step()])
class Rt:
    def __init__(s, n): s.n = n
class Soil: Uz=Rt("sUz"); X=Rt("sX"); Y=Rt("sY"); Z=Rt("sZ")
class Plate: Uz=Rt("pUz"); M11=Rt("pM11"); M22=Rt("pM22"); X=Rt("pX"); Y=Rt("pY"); Z=Rt("pZ")
class RTs: pass
RTs.Soil = Soil; RTs.Plate = Plate
PX = [i*3.0 for i in range(7) for j in range(7)]; PY = [j*3.0 for i in range(7) for j in range(7)]
SX = [i*5.0 for i in range(16) for j in range(16)]; SY = [(j*5.0) for i in range(16) for j in range(16)]
class PL: pass
class GO:
    Phases = [Ph("Initial phase"), Ph("Excavation"), Ph("Construction"), Ph("Loading")]
    Nodes = [1,2,3,4]; ResultTypes = RTs
    Plate_1 = PL(); Plate_2 = PL(); Plate_3 = PL()
    Plates = [Plate_1, Plate_2, Plate_3]
    def getcurveresults(s, no, st, rt): return -0.01 * no
    def getresults(s, *a):
        rt = a[-2] if isinstance(a[-1], str) else a[-1]
        obj = a[0] if len(a) >= 3 and not isinstance(a[0], Ph) and not isinstance(a[0], Step) else None
        n = rt.n
        if n.startswith("p"):
            if obj is not s.Plate_1: raise RuntimeError("plate nao e o piso" if obj is not s.Plate_2 else "x")
            return {"pX":PX,"pY":PY,"pZ":[-2.0]*len(PX),"pUz":[-0.02*math.sin(x/6)for x in PX],"pM11":[x-y for x,y in zip(PX,PY)],"pM22":[0.0]*len(PX)}[n]
        return {"sX":SX,"sY":SY,"sZ":[0.0]*len(SX),"sUz":[-0.01*math.cos(x/30) for x in SX]}[n]
    def close(s): pass
def new_server(h, p, password=None): return None, GO()

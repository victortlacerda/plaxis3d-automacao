"""Mock do PLAXIS Input para testar os scripts interativos SEM o PLAXIS.

Uso (a partir de uma pasta de trabalho vazia; as saídas .json/.p3d caem nela):
    python rodar_interativo.py <script.py> < entradas.txt

Todo comando enviado a g_i/s_i é registrado como 'CALL ...' / 'SET ...' no stdout. O mock NÃO valida
nomes reais de propriedades; serve para conferir a ordem dos comandos e a lógica (regressão).
"""
import sys, os
AQUI = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.abspath(sys.argv[1])
sys.path.insert(0, os.path.join(AQUI, "..", "fakes", "interativo"))
class Rec:
    def __init__(self, nome): object.__setattr__(self, "_n", nome)
    def __getattr__(self, k):
        if k.startswith("__"): raise AttributeError(k)
        return Rec(self._n + "." + k)
    def __setattr__(self, k, v): print("   SET {}.{} = {!r}".format(self._n, k, v))
    def __call__(self, *a):
        print("   CALL {}{}".format(self._n, a)); return Rec(self._n + "()")
    def __getitem__(self, i): return Rec("{}[{}]".format(self._n, i))
    def __setitem__(self, i, v): print("   SETITEM {}[{}] = {!r}".format(self._n, i, v))
    def __iter__(self): return iter([Rec(self._n+"[0]"), Rec(self._n+"[1]")])
    def __repr__(self): return "<%s>" % self._n
class Poly(Rec):
    store = [0.5]
    def __getattr__(self, k):
        if k == "CoarsenessFactor": return Cf()
        return Rec.__getattr__(self, k)
class Cf(list):
    def __init__(self): list.__init__(self, Poly.store)
    def __setitem__(self, i, v): print("   SETITEM CoarsenessFactor[%d]=%r" % (i, v)); Poly.store[i] = v
class PM:
    def __init__(self): object.__setattr__(self, "cf", 0.5)
    def echo(self): return "Polygon_1_1\n  CoarsenessFactor = %g\n" % self.cf
    def __setattr__(self, k, v):
        print("   SET Polygon_1_1.%s = %r" % (k, v)); object.__setattr__(self, "cf", v)
PM1 = PM()
class GI(Rec):
    def __getattr__(self, k):
        if k == "Polygon_1_1": return PM1
        if k.startswith("Polygon_1_"): raise AttributeError(k)
        if k == "Polygon_1": return Poly("Polygon_1")
        if k == "surface": return lambda *a: (print("   CALL surface", a), Poly("Polygon_1"))[1]
        if k == "selectmeshpoints": return lambda *a: (print("   CALL selectmeshpoints"), 10001)[1]
        return Rec.__getattr__(self, k)
g_i = GI("g_i"); s_i = Rec("s_i")
os.environ["PLAXIS_PASSWORD"] = "x"
ns = {"g_i": g_i, "s_i": s_i, "__file__": os.path.join(os.getcwd(), os.path.basename(SCRIPT))}
exec(compile(open(SCRIPT, encoding="utf-8").read(), SCRIPT, "exec"), ns, ns)

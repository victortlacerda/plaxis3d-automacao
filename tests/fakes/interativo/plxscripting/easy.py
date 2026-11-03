class GO:
    def addcurvepoint(self, *a): print("   [O] addcurvepoint", a)
    def update(self): print("   [O] update")
def new_server(host, port, password=None):
    print("   [new_server]", host, port)
    return None, GO()

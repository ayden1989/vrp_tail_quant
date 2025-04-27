import core.delta_hedge as dh

class DummyIB:
    def __init__(self): self._d=[]
    def connect(self,*a,**k): pass
    def disconnect(self): pass
    def positions(self): return []          # no positions → delta 0
    def reqMktData(self,*a,**k): return type("T",(),{"last":5000,"close":5000})
    def sleep(self,*a): pass
def test_no_hedge(monkeypatch):
    monkeypatch.setattr(dh,"connect",lambda: DummyIB())
    dh.main()          # should just print "no hedge" and exit
import core.order_manager as om

class DummyIB:
    def __init__(self): self.orders=[]
    def connect(self,*a,**k): pass
    def disconnect(self): pass
    def accountSummary(self): 
        from collections import namedtuple
        Row = namedtuple("Row","tag value")
        return [Row("NetLiquidation","40000")]
    def reqMktData(self,*a,**k):
        class T: bid=1.0; ask=1.2; last=5000; close=5000
        return T()
    def qualifyContracts(self,*a): return
    def placeOrder(self,*a): 
        class O: orderId=1
        self.orders.append(O())
        return [O()]
    def sleep(self,*a): pass

def test_order_skips_if_not_monday(monkeypatch):
    monkeypatch.setattr(om,"is_monday_open",lambda: False)
    monkeypatch.setattr(om,"load_signal",lambda: {"enter_trade":True})
    monkeypatch.setattr(om,"IB",DummyIB)
    om.main()
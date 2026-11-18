from datetime import datetime, timezone
from decimal import Decimal
from ats_tidsbesparelse_models import AtsRule
from ats_tidsbesparelse_classifier import classify_items
from ats_tidsbesparelse_aggregator import aggregate_items

def run_test():
    rules=[
        AtsRule(6,"test-queue","Test","Godkendt",("4.0 Godkendt",),"ANY",Decimal("12.2"),10,"PR_ITEM",Decimal("0"),"SUM_RESULTAT",datetime(2026,1,1).date(),datetime(2099,1,1).date()),
        AtsRule(7,"fast-queue","Fast","Enhed A",("Status A",),"ANY",Decimal("0"),10,"FAST_PR_MÅNED",Decimal("300"),"SUM_RESULTAT",datetime(2026,1,1).date(),datetime(2099,1,1).date()),
        AtsRule(8,"fast-queue","Fast","Enhed B",("Status B",),"ANY",Decimal("0"),20,"FAST_PR_MÅNED",Decimal("300"),"SUM_RESULTAT",datetime(2026,1,1).date(),datetime(2099,1,1).date()),
    ]
    items=[
        {"id":1,"queue_name":"test-queue","updated_at":datetime(2026,8,5,tzinfo=timezone.utc),"data":{"state":["4.0 Godkendt 05-08-2026 10:00:00"],"status":{"status_code":"Færdig"}}},
        {"id":2,"queue_name":"test-queue","updated_at":datetime(2026,8,6,tzinfo=timezone.utc),"data":{"state":["Andet"]}},
        {"id":3,"queue_name":"fast-queue","updated_at":datetime(2026,8,7,tzinfo=timezone.utc),"data":{"status":{"status":"Status A"}}},
        {"id":4,"queue_name":"fast-queue","updated_at":datetime(2026,8,8,tzinfo=timezone.utc),"data":{"status_code":"Status B"}},
    ]
    rows=aggregate_items(classify_items(items,rules))
    assert sum(r["Antal items"] for r in rows)==4
    assert sum(r["Besparede minutter"] for r in rows)==Decimal("0") or round(sum(r["Besparede minutter"] for r in rows),1)==312.2
    assert len([r for r in rows if r["Resultat"]=="Fast månedsbesparelse"])==1
    assert round(sum(r["Besparede minutter"] for r in rows),1)==312.2
    print("OK: syntetisk test bestået. 4 items, 1 no-match og 312,2 sparede minutter.")
if __name__=="__main__": run_test()

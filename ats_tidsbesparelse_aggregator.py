from __future__ import annotations
from collections import defaultdict
from decimal import Decimal
from ats_tidsbesparelse_models import ClassifiedItem, Row


def aggregate_items(items: list[ClassifiedItem]) -> list[Row]:
    groups=defaultdict(list)
    for item in items:
        rule=item.rule
        if rule:
            key=(item.month,item.queue_name,rule.technical_id)
        else:
            key=(item.month,item.queue_name,"NO_MATCH",item.raw_stats)
        groups[key].append(item)
    rows=[]
    for grouped in groups.values():
        first=grouped[0]; rule=first.rule; count=len(grouped)
        matched=_join_unique(v for item in grouped for v in item.matched_stats)
        raw=_join_unique(v for item in grouped for v in item.raw_stats)
        if rule:
            minutes=rule.minutes_per_item*count if rule.calculation_method=="PR_ITEM" else Decimal("0")
            rows.append(_row(first.month, first.queue_name, rule.result or "Resultat", rule.technical_id,
                rule.match_type, matched, raw, count, rule.minutes_per_item,
                Decimal("0"), minutes, rule.detail_level))
        else:
            rows.append(_row(first.month, first.queue_name, "Ingen matchende regel", "INGEN_MATCH",
                "NO_MATCH", "", raw, count, Decimal("0"), Decimal("0"), Decimal("0"), "SUM_RESULTAT"))
    _add_fixed_month_rows(rows, items)
    return sorted(rows,key=lambda r:(r["Måned"],r["Queue Name"].casefold(),r["Resultat"].casefold()))


def _add_fixed_month_rows(rows, items):
    candidates=defaultdict(list)
    for item in items:
        if item.rule and item.rule.calculation_method=="FAST_PR_MÅNED": candidates[(item.month,item.queue_name)].append(item.rule)
    for (month,queue),rules in candidates.items():
        rule=sorted(rules,key=lambda r:(r.priority,r.row_number))[0]
        rows.append(_row(month,queue,"Fast månedsbesparelse",f"ATS_{queue}_FAST_PR_MAANED","NO_STATE_FILTER",
            "","",0,Decimal("0"),rule.fixed_minutes_per_month,rule.fixed_minutes_per_month,rule.detail_level))

def _row(month,queue,result,rule_id,match_type,matched,raw,count,minutes_per_item,fixed,minutes,detail):
    return {"Er sumlinje":"Ja","Rækketype":"Sum","Detailniveau":detail,"Datoperspektiv":"Completed",
        "Måned":month,"Queue Name":queue,"Resultat":result,"Matchregel-ID":rule_id,"Matchtype":match_type,
        "Matchende tags":matched,"Rå tags":raw,"Antal items":count,"Itemmarkør":0,
        "Minutter pr. item":float(minutes_per_item),"Faste minutter pr. måned":float(fixed),
        "Besparede minutter":float(minutes),"Besparede timer":float(minutes/Decimal("60"))}
def _join_unique(values): return "\n".join(dict.fromkeys(value for value in values if value))

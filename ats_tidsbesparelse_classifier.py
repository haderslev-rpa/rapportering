from __future__ import annotations
from datetime import timezone
from zoneinfo import ZoneInfo
from ats_tidsbesparelse_models import AtsRule, ClassifiedItem
DK=ZoneInfo("Europe/Copenhagen")


def classify_items(workitems: list[dict], rules: list[AtsRule]) -> list[ClassifiedItem]:
    by_queue={}
    for rule in rules: by_queue.setdefault(rule.queue_name.casefold(), []).append(rule)
    output=[]
    for item in workitems:
        completed=_as_danish(item["updated_at"])
        raw=_extract_stats(item.get("data") or {})
        rule,matched=_find_rule(by_queue.get(item["queue_name"].casefold(), []), raw, completed.date())
        output.append(ClassifiedItem(int(item["id"]), item["queue_name"], completed,
                     completed.date().replace(day=1), raw, matched, rule))
    return output


def _extract_stats(data: dict) -> tuple[str,...]:
    values=[]
    state=data.get("state", [])
    if isinstance(state,list): values.extend(str(v).strip() for v in state if str(v).strip())
    elif state: values.append(str(state).strip())
    status=data.get("status")
    if isinstance(status,dict):
        for key in ("status","Status","status_code","Status_code","code"):
            value=status.get(key)
            if value not in (None,""): values.append(str(value).strip())
    elif status not in (None,""): values.append(str(status).strip())
    for key in ("status_code","Status_code","Status","status"):
        value=data.get(key)
        if value not in (None,"",status): values.append(str(value).strip())
    return tuple(dict.fromkeys(values))


def _find_rule(rules, raw_stats, completed_date):
    normalized=[value.casefold() for value in raw_stats]
    for rule in rules:
        if not (rule.valid_from <= completed_date < rule.valid_to): continue
        matches=[]
        for configured in rule.stats:
            found=next((raw for raw,norm in zip(raw_stats,normalized) if norm.startswith(configured.casefold())), None)
            if found: matches.append(found)
        if rule.match_type == "NO_STATE_FILTER" or (rule.match_type == "ANY" and matches) or (rule.match_type == "ALL" and len(matches)==len(rule.stats)):
            return rule, tuple(dict.fromkeys(matches))
    return None, ()

def _as_danish(value):
    if value.tzinfo is None: value=value.replace(tzinfo=timezone.utc)
    return value.astimezone(DK)

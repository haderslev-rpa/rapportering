from __future__ import annotations
import logging
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from q_outlook_api.functionality.mail_api import send_mail
from ats_tidsbesparelse_config import ATS_TIDSBESPARELSE_CONFIG, validate_ats_tidsbesparelse_config
from ats_tidsbesparelse_sharepoint import download_rules_workbook
from ats_tidsbesparelse_rules import read_rules
from ats_tidsbesparelse_repository import resolve_queue_ids, fetch_completed_workitems
from ats_tidsbesparelse_classifier import classify_items
from ats_tidsbesparelse_aggregator import aggregate_items
from ats_tidsbesparelse_excel import create_excel
logger=logging.getLogger(__name__); DK=ZoneInfo("Europe/Copenhagen")

def run_ats_tidsbesparelse_report(*, send_email: bool=True, now: datetime|None=None) -> dict:
    validate_ats_tidsbesparelse_config()
    start_dk,end_dk=_full_month_period(now or datetime.now(DK),ATS_TIDSBESPARELSE_CONFIG["months_back"])
    rules=read_rules(download_rules_workbook())
    queue_ids=resolve_queue_ids({rule.queue_name for rule in rules})
    workitems=fetch_completed_workitems(queue_ids,_utc_naive(start_dk),_utc_naive(end_dk))
    classified=classify_items(workitems,rules); rows=aggregate_items(classified)
    period_text=f"{start_dk:%Y-%m-%d}_til_{(end_dk.date()):%Y-%m-%d}"
    excel_path=create_excel(rows,period_text)
    no_match=sum(1 for item in classified if item.rule is None)
    total_hours=sum(row["Besparede timer"] for row in rows)
    logger.info("ATS tidsbesparelse | regler=%s | queues=%s | completed=%s | uden_match=%s | outputrækker=%s | timer=%.2f",
                len(rules),len(queue_ids),len(workitems),no_match,len(rows),total_hours)
    mail_sent=False
    if send_email:
        body=ATS_TIDSBESPARELSE_CONFIG["mail_body"].format(period_text=period_text,months_back=ATS_TIDSBESPARELSE_CONFIG["months_back"])
        subject=ATS_TIDSBESPARELSE_CONFIG["mail_subject"].format(period_text=period_text)
        mail_sent=send_mail(user_mail=ATS_TIDSBESPARELSE_CONFIG["sender_mail"],mail={"subject":subject,"content_type":"Text","body":body,
            "to":ATS_TIDSBESPARELSE_CONFIG["to"],"cc":ATS_TIDSBESPARELSE_CONFIG["cc"],"bcc":ATS_TIDSBESPARELSE_CONFIG["bcc"],
            "save_to_sent_items":ATS_TIDSBESPARELSE_CONFIG["save_to_sent_items"],"attachments":[Path(excel_path)]})
    return {"period_start":start_dk.isoformat(),"period_end_exclusive":end_dk.isoformat(),"completed":len(workitems),
            "without_match":no_match,"rows":len(rows),"hours":round(total_hours,2),"excel_path":str(excel_path),"mail_sent":bool(mail_sent)}

def _full_month_period(now,months_back):
    now=now.astimezone(DK) if now.tzinfo else now.replace(tzinfo=DK)
    end=now.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    year=end.year; month=end.month-months_back
    while month<=0: year-=1; month+=12
    return end.replace(year=year,month=month),end

def _utc_naive(value): return value.astimezone(timezone.utc).replace(tzinfo=None)

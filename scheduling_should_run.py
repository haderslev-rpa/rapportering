# scheduling_should_run.py

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from cronsim import CronSim

logger = logging.getLogger(__name__)

DK_ZONE = ZoneInfo("Europe/Copenhagen")
UTC_ZONE = ZoneInfo("UTC")


def should_run_report(
    cron_text,
    run_now,
    aktiv,
    minimum_dage_efter_sidste_rapport,
    last_mail_sendt_timestamp,
    last_rapportering_end,
    debug,
):
    """
    Afgør om rapporten skal køre.

    funktion (genbrugelig kodeblok)

    Returnerer:
    - should_run
    - koerselstype
    - reason

    VIGTIGT:
    - debug overstyrer IKKE reglerne
    - debug bruges kun til mere log i main.py
    - Run now overstyrer alt
    - Minimum dage vurderes mod sidste mail_sendte rapport
    - Cron vurderes i dansk tid
    - Sidste rapportering_end er stadig teknisk database-tid
    """

    if not _is_yes(aktiv):
        return False, None, "Aktiv er ikke Ja"

    if _is_yes(run_now):
        return True, "run_now", "Run now = Ja -> rapport tvinges igennem"

    if minimum_dage_efter_sidste_rapport > 0:
        ok = _minimum_days_ok(
            minimum_dage_efter_sidste_rapport,
            last_mail_sendt_timestamp,
        )

        if not ok:
            return False, None, "Minimum dage efter sidste rapport er ikke opfyldt"

    if not cron_text:
        return False, None, "Cron mangler"

    due, cron_reason = _cron_is_due_from_last_rapportering_end_dk(
        cron_text,
        last_rapportering_end,
    )

    if not due:
        return False, None, cron_reason

    return True, "cron", cron_reason


def _cron_is_due_from_last_rapportering_end_dk(cron_text, last_rapportering_end):
    """
    Tjekker om cron er due ud fra sidste rapportering_end.

    funktion (genbrugelig kodeblok)

    Logik:
    - fortolk sidste rapportering_end som teknisk database-tid
    - oversæt den til dansk tid
    - find næste cron-tidspunkt efter den danske tid
    - hvis now_dk >= næste cron-tidspunkt -> rapport må køre
    """

    now_dk = datetime.now(DK_ZONE).replace(second=0, microsecond=0)

    base_dk = _parse_rapportering_end_as_danish(last_rapportering_end)

    if not base_dk:
        base_dk = now_dk - timedelta(days=31)

    try:
        sim = CronSim(cron_text, base_dk)
        next_run = next(sim)

        if next_run <= now_dk:
            return (
                True,
                (
                    "Cron er due ud fra sidste rapportering_end (dansk tid) | "
                    f"last_rapportering_end_dk={base_dk} | "
                    f"next_run_dk={next_run} | "
                    f"now_dk={now_dk}"
                ),
            )

        return (
            False,
            (
                "Cron er ikke due endnu ud fra sidste rapportering_end (dansk tid) | "
                f"last_rapportering_end_dk={base_dk} | "
                f"next_run_dk={next_run} | "
                f"now_dk={now_dk}"
            ),
        )

    except Exception as error:
        return False, f"Ugyldigt cron-format '{cron_text}'. Fejl: {error}"


def _minimum_days_ok(minimum_dage_efter_sidste_rapport, last_mail_sendt_timestamp):
    """
    Tjekker minimum dage efter sidste sendte rapport.

    funktion (genbrugelig kodeblok)
    """

    if not last_mail_sendt_timestamp:
        return True

    last_sent = _parse_mail_timestamp_as_danish(last_mail_sendt_timestamp)

    if not last_sent:
        return True

    now_dk = datetime.now(DK_ZONE)
    days_since = (now_dk - last_sent).days

    return days_since >= minimum_dage_efter_sidste_rapport


def _parse_rapportering_end_as_danish(value):
    """
    Parser last_rapportering_end og oversætter til dansk tid.

    funktion (genbrugelig kodeblok)
    """

    if not value:
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()

        try:
            dt = datetime.fromisoformat(text)
        except Exception:
            dt = None

        if dt is None:
            formats = [
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
            ]

            for fmt in formats:
                try:
                    dt = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    pass

    if dt is None:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC_ZONE)

    return dt.astimezone(DK_ZONE).replace(second=0, microsecond=0)


def _parse_mail_timestamp_as_danish(value):
    """
    Parser mail_sendt_tidspunkt som dansk tid.

    funktion (genbrugelig kodeblok)
    """

    if not value:
        return None

    formats = [
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(str(value), fmt)
            return dt.replace(tzinfo=DK_ZONE)
        except ValueError:
            pass

    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=DK_ZONE)
        return dt.astimezone(DK_ZONE)
    except Exception:
        return None


def _is_yes(value):
    """
    Tjekker om SharePoint valg er Ja.

    funktion (genbrugelig kodeblok)
    """

    return str(value or "").strip().lower() == "ja"

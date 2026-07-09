# sharepoint_report_config_repository.py

import logging

from q_sharepoint_api.functionality.sp_list_items import get_list_items
from q_sharepoint_api.functionality.sp_list_item import create_update_sharepoint_list_item

logger = logging.getLogger(__name__)

SITE_NAME = "Automatisering"
LIST_NAME = "Rapportering opsætning"

_SHAREPOINT_CONFIG_CACHE = None


def _log_info(text):
    logger.info(text)


def _log_warning(text):
    logger.warning(text)


def get_sharepoint_report_configs(force_refresh=False):
    """
    Henter rapportopsætninger fra SharePoint-listen.

    funktion (genbrugelig kodeblok)

    Bruger cache (midlertidig hukommelse),
    så SharePoint kun læses én gang pr. proceskørsel.
    """

    global _SHAREPOINT_CONFIG_CACHE

    if _SHAREPOINT_CONFIG_CACHE is not None and not force_refresh:
        return _SHAREPOINT_CONFIG_CACHE

    raw_result = get_list_items(
        site_name=SITE_NAME,
        list_name=LIST_NAME,
        include_raw=False,
    )

    items = []

    if isinstance(raw_result, list):
        items = raw_result

    elif isinstance(raw_result, dict):
        if isinstance(raw_result.get("items"), list):
            items = raw_result.get("items", [])
        else:
            _log_warning("SharePoint result er dict, men 'items' er ikke en liste")
            items = []

    else:
        _log_warning(
            f"Uventet type fra get_list_items: {type(raw_result).__name__}"
        )
        items = []

    configs = []

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            _log_warning(f"SPRINGER ITEM OVER (ikke dict): {item}")
            continue

        normalized = _normalize_sharepoint_config(item)

        _log_info(
            (
                f"SharePoint linje {index} | "
                f"id={normalized.get('id')} | "
                f"title={normalized.get('titel')} | "
                f"aktiv={normalized.get('aktiv')} | "
                f"run_now={normalized.get('run_now')} | "
                f"cron={normalized.get('cron')} | "
                f"til={normalized.get('til')}"
            )
        )

        configs.append(normalized)

    _SHAREPOINT_CONFIG_CACHE = configs
    return _SHAREPOINT_CONFIG_CACHE


def find_sharepoint_config_by_rapport_id(rapport_id):
    """
    Finder SharePoint opsætning hvor title = rapport_id.

    funktion (genbrugelig kodeblok)
    """

    _log_info(f"FINDER SHAREPOINT CONFIG FOR rapport_id={rapport_id}")

    configs = get_sharepoint_report_configs()

    for config in configs:
        config_title = config.get("titel")

        _log_info(
            f"Sammenligner rapport_id='{rapport_id}' med sharepoint title='{config_title}'"
        )

        if config_title == rapport_id:
            _log_info(
                f"MATCH FUNDET | rapport_id={rapport_id} | sharepoint_item_id={config.get('id')}"
            )
            return config

    _log_warning(f"INGEN MATCH fundet for rapport_id={rapport_id}")
    return None


def set_run_now_to_no(sharepoint_item_id):
    """
    Sætter Run now = Nej i SharePoint.

    funktion (genbrugelig kodeblok)
    """

    global _SHAREPOINT_CONFIG_CACHE

    if not sharepoint_item_id:
        _log_warning("sharepoint_item_id mangler - kan ikke sætte Run now = Nej")
        return

    _log_info(f"Sætter Run now = Nej i SharePoint for item_id={sharepoint_item_id}")

    create_update_sharepoint_list_item(
        site_name=SITE_NAME,
        list_name=LIST_NAME,
        sharepoint_data={
            "id": sharepoint_item_id,
            "Run now": "Nej",
        },
    )

    # ryd cache så næste proceskørsel læser seneste SharePoint-data
    _SHAREPOINT_CONFIG_CACHE = None

    _log_info("Run now er sat til Nej")


def _normalize_sharepoint_config(item):
    """
    Normaliserer SharePoint item til faste feltnavne.

    funktion (genbrugelig kodeblok)
    """

    return {
        "id": item.get("id"),
        "titel": _get_first_value(item, ["Title", "Titel", "title", "titel"]),
        "til": _split_mail_list(_get_first_value(item, ["Til", "til"])),
        "cc": _split_mail_list(_get_first_value(item, ["Cc", "CC", "cc"])),
        "bcc": _split_mail_list(_get_first_value(item, ["Bcc", "BCC", "bcc"])),
        "cron": _get_first_value(item, ["Cron", "cron"]),
        "run_now": _get_first_value(item, ["Run now", "Run_x0020_now", "run_now"]),
        "aktiv": _get_first_value(item, ["Aktiv", "aktiv"]),
        "minimum_dage_efter_sidste_rapport": _to_int(
            _get_first_value(
                item,
                [
                    "Minimum dage efter sidste rapport",
                    "Minimum_x0020_dage_x0020_efter_x0020_sidste_x0020_rapport",
                ],
            )
        ),
    }


def _get_first_value(data, keys):
    if not isinstance(data, dict):
        return None

    for key in keys:
        if key in data:
            return data.get(key)

    return None


def _split_mail_list(value):
    if not value:
        return []

    text = str(value).replace(";", ",")
    return [part.strip() for part in text.split(",") if part.strip()]


def _to_int(value):
    if value in (None, ""):
        return 0

    try:
        return int(value)
    except Exception:
        return 0
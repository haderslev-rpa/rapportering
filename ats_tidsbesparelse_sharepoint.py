from __future__ import annotations
from q_sharepoint_api.sp_api import get_client
from ats_tidsbesparelse_config import ATS_TIDSBESPARELSE_CONFIG


def download_rules_workbook() -> bytes:
    client = get_client()
    site_id = client.get_site_id(ATS_TIDSBESPARELSE_CONFIG["site_name"])
    result = client.download_file_to_memory_by_path(
        site_id=site_id,
        file_path=ATS_TIDSBESPARELSE_CONFIG["file_path"],
    )
    if isinstance(result, bytes):
        return result
    if isinstance(result, dict):
        for key in ("content", "file_bytes", "bytes"):
            if isinstance(result.get(key), bytes):
                return result[key]
    if isinstance(result, tuple):
        for value in result:
            if isinstance(value, bytes):
                return value
    raise TypeError("SharePoint-download returnerede ikke filens bytes.")

from __future__ import annotations

ATS_TIDSBESPARELSE_CONFIG = {
    "site_name": "Automatisering",
    "file_path": "Statistik/Statistk - Regelmotor og data.xlsx",
    "sheet_name": "ATS_Regler",
    "table_name": "ATS_ReglerTable",
    "months_back": 3,
    "output_folder": "tests_local",
    "excel_file_prefix": "ATS_tidsbesparelse",
    "sender_mail": "robot-data@haderslev.dk",
    "to": ["automatisering@haderslev.dk"],
    "cc": [],
    "bcc": [],
    "mail_subject": "ATS tidsbesparelse - {period_text}",
    "mail_body": (
        "Hej\n\nVedhæftet er ATS-tidsbesparelsesrapporten for {period_text}.\n"
        "Rapporten indeholder de seneste {months_back} fulde måneder.\n\n"
        "Venlig hilsen\nRobotten"
    ),
    "save_to_sent_items": True,
}


def validate_ats_tidsbesparelse_config() -> None:
    required = (
        "site_name", "file_path", "sheet_name", "table_name", "months_back",
        "output_folder", "excel_file_prefix", "sender_mail", "to", "cc", "bcc",
        "mail_subject", "mail_body", "save_to_sent_items",
    )
    missing = [key for key in required if key not in ATS_TIDSBESPARELSE_CONFIG]
    if missing:
        raise ValueError(f"ATS_TIDSBESPARELSE_CONFIG mangler: {missing}")
    months_back = ATS_TIDSBESPARELSE_CONFIG["months_back"]
    if isinstance(months_back, bool) or not isinstance(months_back, int) or months_back <= 0:
        raise ValueError("months_back skal være et positivt heltal.")
    if not ATS_TIDSBESPARELSE_CONFIG["to"]:
        raise ValueError("ATS-tidsbesparelsesrapporten har ingen modtagere.")

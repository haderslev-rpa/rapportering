# reporting_excel_builder.py

from pathlib import Path

import pandas as pd

from time_helper import now_danish_filename_string


def create_excel_report(
    rapport_navn,
    excel_file_prefix,
    rows,
    output_folder="tests_local",
):
    """
    Opretter Excel-fil på disk.

    funktion (genbrugelig kodeblok)

    VIGTIGT:
    - filnavnet bruger dansk tid
    """

    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = now_danish_filename_string()
    safe_prefix = _safe_filename(excel_file_prefix)

    file_path = output_path / f"{safe_prefix}_{timestamp}.xlsx"

    df = pd.DataFrame(rows)

    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Rapport", index=False)

        worksheet = writer.sheets["Rapport"]

        for column_cells in worksheet.columns:
            max_length = 0
            column_letter = column_cells[0].column_letter

            for cell in column_cells:
                value = cell.value
                if value is not None:
                    max_length = max(max_length, len(str(value)))

            worksheet.column_dimensions[column_letter].width = min(max_length + 2, 60)

    return file_path


def _safe_filename(value):
    """
    Gør tekst sikker som filnavn.

    funktion (genbrugelig kodeblok)
    """

    replacements = {
        " ": "_",
        "/": "_",
        "\\": "_",
        ":": "_",
        ";": "_",
        ",": "_",
        "æ": "ae",
        "ø": "oe",
        "å": "aa",
        "Æ": "Ae",
        "Ø": "Oe",
        "Å": "Aa",
    }

    result = value

    for old, new in replacements.items():
        result = result.replace(old, new)

    return result
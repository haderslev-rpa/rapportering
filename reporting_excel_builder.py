# reporting_excel_builder.py

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from time_helper import (
    now_danish_filename_string,
)

DK_ZONE = ZoneInfo("Europe/Copenhagen")

DEFAULT_DATETIME_FORMAT = (
    "dd-mm-yyyy hh:mm:ss"
)


def create_excel_report(
    rapport_navn,
    excel_file_prefix,
    rows,
    columns,
    output_folder="tests_local",
):
    """
    Opretter en Excel-fil på disk.

    Input:
        rapport_navn:
            Rapportens pæne navn.

        excel_file_prefix:
            Første del af filnavnet.

        rows:
            Mappede Excel-rækker.

        columns:
            Excel-kolonnedefinition med header, source og type.

        output_folder:
            Mappe til den midlertidige Excel-fil.

    Output:
        pathlib.Path:
            Den konkrete sti til den oprettede Excel-fil.

    VIGTIGT:
        datetime-kolonner vises som:
            dd-mm-yyyy hh:mm:ss

        Værdierne bevares som rigtige Excel-datoer.
    """

    output_path = Path(output_folder)
    output_path.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = now_danish_filename_string()
    safe_prefix = _safe_filename(
        excel_file_prefix
    )

    file_path = (
        output_path
        / f"{safe_prefix}_{timestamp}.xlsx"
    )

    ordered_headers = [
        column["header"]
        for column in columns
    ]

    normalized_rows = _prepare_rows_for_excel(
        rows=rows,
        columns=columns,
    )

    dataframe = pd.DataFrame(
        normalized_rows,
        columns=ordered_headers,
    )

    with pd.ExcelWriter(
        file_path,
        engine="openpyxl",
    ) as writer:
        dataframe.to_excel(
            writer,
            sheet_name="Rapport",
            index=False,
        )

        worksheet = writer.sheets["Rapport"]

        _apply_datetime_formats(
            worksheet=worksheet,
            columns=columns,
        )

        _apply_column_widths(
            worksheet
        )

        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = (
            worksheet.dimensions
        )

    return file_path


def _prepare_rows_for_excel(
    rows,
    columns,
):
    """
    Forbereder værdier til Excel.

    datetime-kolonner konverteres til dansk lokal tid.
    Tidszoneinformationen fjernes derefter, fordi Excel ikke
    understøtter timezone-aware datetime direkte.

    Output:
        list:
            Nye Excel-rækker.
    """

    datetime_headers = {
        column["header"]
        for column in columns
        if column.get("type") == "datetime"
    }

    prepared_rows = []

    for row in rows:
        prepared_row = dict(row)

        for header in datetime_headers:
            prepared_row[header] = (
                _datetime_to_danish_excel_value(
                    prepared_row.get(header)
                )
            )

        prepared_rows.append(
            prepared_row
        )

    return prepared_rows


def _datetime_to_danish_excel_value(value):
    """
    Konverterer datetime til dansk lokal tid for Excel.

    Output:
        datetime:
            Dansk tid uden timezone-information.

        Oprindelig værdi:
            Hvis værdien ikke er en datetime.
    """

    if value is None:
        return None

    if not isinstance(value, datetime):
        return value

    if value.tzinfo is None:
        # Vi gætter ikke på tidszone for en naiv værdi.
        # Den bevares som den er.
        return value

    return (
        value
        .astimezone(DK_ZONE)
        .replace(tzinfo=None)
    )


def _apply_datetime_formats(
    worksheet,
    columns,
):
    """
    Anvender Excel-visningsformat på datetime-kolonner.

    Output:
        None.
    """

    for column_index, column in enumerate(
        columns,
        start=1,
    ):
        if column.get("type") != "datetime":
            continue

        number_format = column.get(
            "format",
            DEFAULT_DATETIME_FORMAT,
        )

        for row_index in range(
            2,
            worksheet.max_row + 1,
        ):
            worksheet.cell(
                row=row_index,
                column=column_index,
            ).number_format = number_format


def _apply_column_widths(worksheet):
    """
    Tilpasser kolonnebredderne efter indholdet.

    Output:
        None.
    """

    for column_cells in worksheet.columns:
        max_length = 0
        column_letter = (
            column_cells[0].column_letter
        )

        for cell in column_cells:
            value = cell.value

            if value is not None:
                max_length = max(
                    max_length,
                    len(str(value)),
                )

        worksheet.column_dimensions[
            column_letter
        ].width = min(
            max_length + 2,
            60,
        )


def _safe_filename(value):
    """
    Gør tekst sikker som filnavn.

    Output:
        str:
            Filnavnsvenlig tekst.
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

    result = str(value)

    for old_value, new_value in replacements.items():
        result = result.replace(
            old_value,
            new_value,
        )

    return result
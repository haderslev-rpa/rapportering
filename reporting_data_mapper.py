# reporting_data_mapper.py

from datetime import datetime
from decimal import Decimal, InvalidOperation


def map_rows_to_excel_dicts(
    rows,
    columns,
):
    """
    Oversætter SQL-resultater til Excel-rækker ud fra columns.

    Input:
        rows:
            Liste med dictionaries fra database-repositoryet.

        columns:
            Rapportens Excel-kolonnedefinition.

    Output:
        list:
            Liste med dictionaries, hvor nøglerne er
            Excel-overskrifterne.

            Eksempel:
                [
                    {
                        "Reference": "ABC",
                        "Opdateret": datetime(...),
                    }
                ]
    """

    excel_rows = []

    for row in rows:
        excel_row = {}

        for column in columns:
            header = column["header"]
            source = column["source"]
            column_type = column.get(
                "type",
                "text",
            )

            value = _get_nested_value(
                row,
                source,
            )

            excel_row[header] = _convert_value(
                value,
                column_type,
            )

        excel_rows.append(excel_row)

    return excel_rows


def _get_nested_value(data, path):
    """
    Henter en værdi fra en nested dictionary.

    Eksempel:
        path:
            data.box.cpr

        data:
            {
                "data": {
                    "box": {
                        "cpr": "123"
                    }
                }
            }

    Output:
        Den fundne værdi eller None.
    """

    current = data

    for part in path.split("."):
        if not isinstance(current, dict):
            return None

        current = current.get(part)

    return current


def _convert_value(
    value,
    column_type,
):
    """
    Konverterer værdien ud fra Excel-kolonnens type.

    Output:
        Den konverterede værdi.

    Typer:
        text
        datetime
        integer
        decimal
    """

    if value is None:
        return None

    if column_type == "text":
        return value

    if column_type == "datetime":
        return _to_datetime(value)

    if column_type == "integer":
        try:
            return int(value)
        except (TypeError, ValueError):
            return value

    if column_type == "decimal":
        try:
            return Decimal(str(value))
        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ):
            return value

    return value


def _to_datetime(value):
    """
    Konverterer en værdi til datetime, hvis det er muligt.

    Output:
        datetime:
            Hvis værdien kunne konverteres.

        Oprindelig værdi:
            Hvis konvertering ikke var mulig.
    """

    if isinstance(value, datetime):
        return value

    text = str(value).strip()

    try:
        return datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
    except ValueError:
        pass

    formats = [
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
    ]

    for date_format in formats:
        try:
            return datetime.strptime(
                text,
                date_format,
            )
        except ValueError:
            pass

    return value
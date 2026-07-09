# reporting_data_mapper.py

def map_rows_to_excel_dicts(rows, columns):
    """
    Mapper database rows til Excel-rækker.

    funktion (genbrugelig kodeblok)
    """

    excel_rows = []

    for row in rows:
        excel_row = {}

        for column in columns:
            header = column["header"]
            source = column["source"]

            excel_row[header] = _get_nested_value(row, source)

        excel_rows.append(excel_row)

    return excel_rows


def _get_nested_value(data, path):
    """
    Henter værdi fra nested dict.

    funktion (genbrugelig kodeblok)
    """

    current = data

    for part in path.split("."):
        if not isinstance(current, dict):
            return None

        current = current.get(part)

    return current
# time_helper.py

from datetime import datetime
from zoneinfo import ZoneInfo


DK_ZONE = ZoneInfo("Europe/Copenhagen")
UTC_ZONE = ZoneInfo("UTC")


def now_danish():
    """
    Returnerer nuværende tidspunkt i dansk tidszone.

    Output:
        datetime:
            Timezone-aware dansk datetime.
    """

    return datetime.now(DK_ZONE)


def now_danish_string():
    """
    Returnerer nuværende dansk tid som læsbar tekst.

    Output:
        str:
            Eksempel:
                25-08-2026 10:41:30
    """

    return now_danish().strftime(
        "%d-%m-%Y %H:%M:%S"
    )


def now_danish_filename_string():
    """
    Returnerer dansk tid til et sikkert filnavn.

    Output:
        str:
            Eksempel:
                25-08-2026_10-41-30
    """

    return now_danish().strftime(
        "%d-%m-%Y_%H-%M-%S"
    )


def format_database_window_datetime(value):
    """
    Formatterer rapporteringsvinduet uden tidszonekonvertering.

    Bruges kun til:
        rapportering_start
        rapportering_end

    Output:
        str:
            Den tekniske databaseværdi som tekst.

    VIGTIGT:
        Funktionen må ikke forskyde tidspunktet til dansk tid.
    """

    if value is None:
        return None

    return str(value)


def parse_database_window_datetime(value):
    """
    Parser en teknisk databaseværdi til datetime.

    Output:
        datetime:
            Hvis værdien kunne parses.

        None:
            Hvis værdien mangler eller ikke kunne parses.
    """

    if value is None:
        return None

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
    ]

    for date_format in formats:
        try:
            return datetime.strptime(
                text,
                date_format,
            )
        except ValueError:
            pass

    return None


def database_window_to_danish_string(value):
    """
    Laver en dansk visning af et teknisk database-tidspunkt.

    Bruges eksempelvis i mail-brødtekst.

    Den tekniske værdi i rapportering_start eller
    rapportering_end ændres ikke.

    Output:
        str:
            Dansk visning:
                dd-mm-yyyy hh:mm:ss
    """

    parsed_value = (
        parse_database_window_datetime(
            value
        )
    )

    if parsed_value is None:
        return str(value)

    if parsed_value.tzinfo is None:
        # Hvis databaseværdien ikke har tidszone,
        # bevares klokkeslættet uden at gætte.
        return parsed_value.strftime(
            "%d-%m-%Y %H:%M:%S"
        )

    return (
        parsed_value
        .astimezone(DK_ZONE)
        .strftime("%d-%m-%Y %H:%M:%S")
    )
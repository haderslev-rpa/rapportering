# time_helper.py

from datetime import datetime
from zoneinfo import ZoneInfo


DK_ZONE = ZoneInfo("Europe/Copenhagen")


def now_danish():
    """
    Returnerer dansk datetime (dato/tid objekt).

    funktion (genbrugelig kodeblok)
    """

    return datetime.now(DK_ZONE)


def now_danish_string():
    """
    Returnerer dansk tid som tekst.

    funktion (genbrugelig kodeblok)
    """

    return now_danish().strftime("%d-%m-%Y %H:%M:%S")


def now_danish_filename_string():
    """
    Returnerer dansk tid til filnavn.

    funktion (genbrugelig kodeblok)
    """

    return now_danish().strftime("%d-%m-%Y_%H-%M-%S")


def format_database_window_datetime(value):
    """
    Formatterer rapporteringsvindue uden dansk konvertering.

    funktion (genbrugelig kodeblok)

    VIGTIGT:
    Bruges til rapportering_start og rapportering_end.
    Disse felter skal være tekniske database-værdier.
    """

    if value is None:
        return None

    # Bevar timezone/offset hvis den findes
    if hasattr(value, "isoformat"):
        return str(value)

    return str(value)


def parse_database_window_datetime(value):
    """
    Parser database-vindue fra tekst til datetime (dato/tid objekt).

    funktion (genbrugelig kodeblok)

    Understøtter både:
    - med offset, fx +00:00
    - uden offset
    - gamle tekstformater
    """

    if not value:
        return None

    if isinstance(value, datetime):
        return value

    text = str(value).strip()

    # Prøv som ISO først
    try:
        return datetime.fromisoformat(text)
    except Exception:
        pass

    # Fallback formater
    formats = [
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass

    return None


def database_window_to_danish_string(value):
    """
    Konverterer database-vindue til dansk visningstekst.

    funktion (genbrugelig kodeblok)

    Bruges til mail-brødtekst eller anden visning.
    Ændrer IKKE de tekniske felter i item-data.
    """

    dt = parse_database_window_datetime(value)

    if not dt:
        return str(value)

    if dt.tzinfo is None:
        # Hvis database-værdien er uden timezone,
        # viser vi den uændret for ikke at gætte forkert.
        return dt.strftime("%d-%m-%Y %H:%M:%S")

    dk_dt = dt.astimezone(DK_ZONE)
    return dk_dt.strftime("%d-%m-%Y %H:%M:%S")
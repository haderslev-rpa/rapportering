# logging_helper.py

from pprint import pformat


def log_info(logger, text):
    """
    Skriver info til logger (log-system).

    funktion (genbrugelig kodeblok)
    """

    logger.info(text)


def log_warning(logger, text):
    """
    Skriver warning til logger.

    funktion (genbrugelig kodeblok)
    """

    logger.warning(text)


def log_error(logger, text):
    """
    Skriver error til logger.

    funktion (genbrugelig kodeblok)
    """

    logger.error(text)


def log_debug(logger, text):
    """
    Skriver debug til logger.

    funktion (genbrugelig kodeblok)
    """

    logger.debug(text)


def log_block(logger, title, lines=None):
    """
    Skriver en tydelig log-blok.

    funktion (genbrugelig kodeblok)
    """

    if lines is None:
        lines = []

    border = "=" * 80
    logger.info(border)
    logger.info(title)

    for line in lines:
        logger.info(line)

    logger.info(border)


def log_dict(logger, title, data):
    """
    Logger en dict som DEBUG.

    funktion (genbrugelig kodeblok)

    Bruges kun i debug-kørsel,
    så normal log ikke bliver for lang.
    """

    text = pformat(data, sort_dicts=False)
    logger.debug(f"{title}\n{text}")
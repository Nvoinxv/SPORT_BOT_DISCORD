import logging

def setup_logger():
    logger = logging.getLogger("sport_bot")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Prevent duplicate logs from discord library
    discord_logger = logging.getLogger("discord")
    discord_logger.setLevel(logging.WARNING)
    discord_logger.addHandler(console_handler)

    return logger

logger = setup_logger()

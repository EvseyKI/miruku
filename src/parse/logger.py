import logging


def create_logger(component: str = "main") -> logging.LoggerAdapter:
    logger = logging.getLogger("shikimori-client")

    if not logger.handlers:
        console_handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s %(component)s] - %(message)s"
        )
        console_handler.setFormatter(formatter)
        logger.setLevel(logging.INFO)
        logger.addHandler(console_handler)

    return logging.LoggerAdapter(logger, {"component": component})

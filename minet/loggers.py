import logging
from logging import NullHandler

main_logger = logging.getLogger("minet")
sleepers_logger = main_logger.getChild("sleepers")

main_logger.addHandler(NullHandler())

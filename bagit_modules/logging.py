import logging

from bagit_modules.module import MODULE_NAME

LOGGER = logging.getLogger(MODULE_NAME)


def configure_logging(opts):
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    if opts.quiet:
        level = logging.ERROR
    else:
        level = logging.INFO
    if opts.log:
        logging.basicConfig(filename=opts.log, level=level, format=log_format)
    else:
        logging.basicConfig(level=level, format=log_format)

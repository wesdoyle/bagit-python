from __future__ import division, absolute_import, print_function, unicode_literals

import logging

from bagit import MODULE_NAME

LOGGER = logging.getLogger(MODULE_NAME)


def _configure_logging(opts):
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    if opts.quiet:
        level = logging.ERROR
    else:
        level = logging.INFO
    if opts.log:
        logging.basicConfig(filename=opts.log, level=level, format=log_format)
    else:
        logging.basicConfig(level=level, format=log_format)

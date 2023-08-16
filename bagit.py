#!/usr/bin/env python
# -*- coding: utf-8 -*-

import codecs
import gettext
import hashlib
import sys
from functools import partial

from pkg_resources import DistributionNotFound, get_distribution

from bagit_modules.bag import Bag
from bagit_modules.bagging import make_bag
from bagit_modules.errors import BagError
from bagit_modules.io import find_locale_dir
from bagit_modules.logging import LOGGER, configure_logging
from bagit_modules.parsing import make_parser

TRANSLATION_CATALOG = gettext.translation("bagit-python", localedir=find_locale_dir(), fallback=True)
_ = TRANSLATION_CATALOG.gettext
MODULE_NAME = "bagit" if __name__ == "__main__" else __name__

try:
    VERSION = get_distribution(MODULE_NAME).version
except DistributionNotFound:
    VERSION = "0.0.dev0"

with open("docstring.txt", "r") as f:
    __doc__ = f.read() % globals()

CHECKSUM_ALGOS = hashlib.algorithms_guaranteed

#: Convenience function used everywhere we want to open a file to read text
#: rather than un-decoded bytes:
open_text_file = partial(codecs.open, encoding="utf-8", errors="strict")


def main():
    if "--version" in sys.argv:
        print(_("bagit-python version %s") % VERSION)
        sys.exit(0)

    parser = make_parser()
    args = parser.parse_args()

    if args.processes <= 0:
        parser.error(_("The number of processes must be greater than 0"))

    if args.fast and not args.validate:
        parser.error(_("--fast is only allowed as an option for --validate!"))

    if args.completeness_only and not args.validate:
        parser.error(_("--completeness-only is only allowed as an option for --validate!"))

    configure_logging(args)

    rc = 0
    for bag_dir in args.directory:
        # validate the bag
        if args.validate:
            try:
                bag = Bag(bag_dir)
                # validate throws a BagError or BagValidationError
                bag.validate(
                    processes=args.processes,
                    fast=args.fast,
                    completeness_only=args.completeness_only,
                )
                if args.fast:
                    LOGGER.info(_("%s valid according to Payload-Oxum"), bag_dir)
                elif args.completeness_only:
                    LOGGER.info(_("%s is complete and valid according to Payload-Oxum"), bag_dir)
                else:
                    LOGGER.info(_("%s is valid"), bag_dir)
            except BagError as e:
                LOGGER.error(
                    _("%(bag)s is invalid: %(error)s"), {"bag": bag_dir, "error": e}
                )
                rc = 1

        # make the bag
        else:
            try:
                make_bag(
                    bag_dir,
                    bag_info=args.bag_info,
                    processes=args.processes,
                    checksums=args.checksums,
                )
            except Exception as exc:
                LOGGER.error(
                    _("Failed to create bag in %(bag_directory)s: %(error)s"),
                    {"bag_directory": bag_dir, "error": exc},
                    exc_info=True,
                )
                rc = 1

    sys.exit(rc)


if __name__ == "__main__":
    main()

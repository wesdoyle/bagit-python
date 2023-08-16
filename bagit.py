#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys

from bagit_modules.bag import Bag
from bagit_modules.bagging import make_bag
from bagit_modules.docs import read_global_docs
from bagit_modules.errors import BagError
from bagit_modules.logging import LOGGER, configure_logging
from bagit_modules.parsing import make_parser
from bagit_modules.translation_catalog import _
from bagit_modules.versioning import get_version

version = get_version()

__doc__ = read_global_docs()


def main():
    # Command line argument parsing
    parser = make_parser()
    args = parser.parse_args()

    configure_logging(args)

    # Version check
    if "--version" in sys.argv:
        print(_("bagit-python version %s") % version)
        sys.exit(0)

    # Argument validations
    if args.processes <= 0:
        parser.error(_("The number of processes must be greater than 0"))

    if args.fast and not args.validate:
        parser.error(_("--fast is only allowed as an option for --validate!"))

    if args.completeness_only and not args.validate:
        parser.error(_("--completeness-only is only allowed as an option for --validate!"))

    error_occurred = False

    if args.validate:
        for bag_dir in args.directory:
            try:
                bag = Bag(bag_dir)
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
                error_occurred = True

    else:
        for bag_dir in args.directory:
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
                error_occurred = True

    sys.exit(1 if error_occurred else 0)


if __name__ == "__main__":
    main()

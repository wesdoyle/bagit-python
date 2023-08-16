#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function, unicode_literals

import codecs
import gettext
import hashlib
import os
import signal
import sys
import unicodedata
from functools import partial

from pkg_resources import DistributionNotFound, get_distribution

from bagit_modules.bag import Bag
from bagit_modules.bagging import make_bag
from bagit_modules.errors import BagError, FileNormalizationConflict
from bagit_modules.logging import LOGGER, _configure_logging
from bagit_modules.parsing import _make_parser

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse


def find_locale_dir():
    for prefix in (os.path.dirname(__file__), sys.prefix):
        locale_dir = os.path.join(prefix, "locale")
        if os.path.isdir(locale_dir):
            return locale_dir


TRANSLATION_CATALOG = gettext.translation(
    "bagit-python", localedir=find_locale_dir(), fallback=True
)
if sys.version_info < (3,):
    _ = TRANSLATION_CATALOG.ugettext
else:
    _ = TRANSLATION_CATALOG.gettext

MODULE_NAME = "bagit" if __name__ == "__main__" else __name__

try:
    VERSION = get_distribution(MODULE_NAME).version
except DistributionNotFound:
    VERSION = "0.0.dev0"

PROJECT_URL = "https://github.com/LibraryOfCongress/bagit-python"

with open("docstring.txt", "r") as f:
    __doc__ = f.read() % globals()

# standard bag-info.txt metadata
STANDARD_BAG_INFO_HEADERS = [
    "Source-Organization",
    "Organization-Address",
    "Contact-Name",
    "Contact-Phone",
    "Contact-Email",
    "External-Description",
    "External-Identifier",
    "Bag-Size",
    "Bag-Group-Identifier",
    "Bag-Count",
    "Internal-Sender-Identifier",
    "Internal-Sender-Description",
    "BagIt-Profile-Identifier",
    # Bagging-Date is autogenerated
    # Payload-Oxum is autogenerated
]

try:
    CHECKSUM_ALGOS = hashlib.algorithms_guaranteed
except AttributeError:
    # FIXME: remove when we drop Python 2 (https://github.com/LibraryOfCongress/bagit-python/issues/102)
    # Python 2.7.0-2.7.8
    CHECKSUM_ALGOS = set(hashlib.algorithms)
DEFAULT_CHECKSUMS = ["sha256", "sha512"]

#: Block size used when reading files for hashing:
HASH_BLOCK_SIZE = 512 * 1024

#: Convenience function used everywhere we want to open a file to read text
#: rather than undecoded bytes:
open_text_file = partial(codecs.open, encoding="utf-8", errors="strict")

# This is the same as decoding the byte values in codecs.BOM:
UNICODE_BYTE_ORDER_MARK = "\uFEFF"


def posix_multiprocessing_worker_initializer():
    """Ignore SIGINT in multiprocessing workers on POSIX systems"""
    signal.signal(signal.SIGINT, signal.SIG_IGN)


# The Unicode normalization form used here doesn't matter – all we care about
# is consistency since the input value will be preserved:


def normalize_unicode(s):
    return unicodedata.normalize("NFC", s)


def force_unicode(s):
    return str(s)


# following code is used for command line program


def main():
    if "--version" in sys.argv:
        print(_("bagit-python version %s") % VERSION)
        sys.exit(0)

    parser = _make_parser()
    args = parser.parse_args()

    if args.processes <= 0:
        parser.error(_("The number of processes must be greater than 0"))

    if args.fast and not args.validate:
        parser.error(_("--fast is only allowed as an option for --validate!"))

    if args.completeness_only and not args.validate:
        parser.error(_("--completeness-only is only allowed as an option for --validate!"))

    _configure_logging(args)

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

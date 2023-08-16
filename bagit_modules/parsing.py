from __future__ import division, absolute_import, print_function, unicode_literals

import argparse
import re

from bagit import VERSION, __doc__, _, CHECKSUM_ALGOS, STANDARD_BAG_INFO_HEADERS
from bagit_modules.constants import DEFAULT_CHECKSUMS


class BagArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        argparse.ArgumentParser.__init__(self, *args, **kwargs)
        self.set_defaults(bag_info={})


class BagHeaderAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        opt = option_string.lstrip("--")
        opt_caps = "-".join([o.capitalize() for o in opt.split("-")])
        namespace.bag_info[opt_caps] = values


def make_parser():
    parser = BagArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="bagit-python version %s\n\n%s\n" % (VERSION, __doc__.strip()),
    )
    parser.add_argument(
        "--processes",
        type=int,
        dest="processes",
        default=1,
        help=_(
            "Use multiple processes to calculate checksums faster (default: %(default)s)"
        ),
    )
    parser.add_argument("--log", help=_("The name of the log file (default: stdout)"))
    parser.add_argument(
        "--quiet",
        action="store_true",
        help=_("Suppress all progress information other than errors"),
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help=_(
            "Validate existing bags in the provided directories instead of"
            " creating new ones"
        ),
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help=_(
            "Modify --validate behaviour to only test whether the bag directory"
            " has the number of files and total size specified in Payload-Oxum"
            " without performing checksum validation to detect corruption."
        ),
    )
    parser.add_argument(
        "--completeness-only",
        action="store_true",
        help=_(
            "Modify --validate behaviour to test whether the bag directory"
            " has the expected payload specified in the checksum manifests"
            " without performing checksum validation to detect corruption."
        ),
    )

    checksum_args = parser.add_argument_group(
        _("Checksum Algorithms"),
        _(
            "Select the manifest algorithms to be used when creating bags"
            " (default=%s)"
        )
        % ", ".join(DEFAULT_CHECKSUMS),
    )

    for i in CHECKSUM_ALGOS:
        alg_name = re.sub(r"^([A-Z]+)(\d+)$", r"\1-\2", i.upper())
        checksum_args.add_argument(
            "--%s" % i,
            action="append_const",
            dest="checksums",
            const=i,
            help=_("Generate %s manifest when creating a bag") % alg_name,
        )

    metadata_args = parser.add_argument_group(_("Optional Bag Metadata"))
    for header in STANDARD_BAG_INFO_HEADERS:
        metadata_args.add_argument(
            "--%s" % header.lower(), type=str, action=BagHeaderAction, default=argparse.SUPPRESS
        )

    parser.add_argument(
        "directory",
        nargs="+",
        help=_(
            "Directory which will be converted into a bag in place"
            " by moving any existing files into the BagIt structure"
            " and creating the manifests and other metadata."
        ),
    )

    return parser

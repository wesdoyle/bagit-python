from __future__ import division, absolute_import, print_function, unicode_literals

import os
import tempfile
import warnings
from datetime import date

from bagit import _, open_text_file, VERSION
from bagit_modules.constants import PROJECT_URL, DEFAULT_CHECKSUMS
from bagit_modules.tagging import make_tag_file
from bagit_modules.manifests import make_manifests, make_tagmanifest_file
from bagit_modules.io import _can_bag, _can_read
from bagit_modules.logging import LOGGER
from bagit_modules.bag import Bag
from bagit_modules.errors import BagError


def make_bag(
    bag_dir, bag_info=None, processes=1, checksums=None, checksum=None, encoding="utf-8"
):
    """
    Convert a given directory into a bag. You can pass in arbitrary
    key/value pairs to put into the bag-info.txt metadata file as
    the bag_info dictionary.
    """

    if checksum is not None:
        warnings.warn(
            _(
                "The `checksum` argument for `make_bag` should be replaced with `checksums`"
            ),
            DeprecationWarning,
        )
        checksums = checksum

    if checksums is None:
        checksums = DEFAULT_CHECKSUMS

    bag_dir = os.path.abspath(bag_dir)
    cwd = os.path.abspath(os.path.curdir)

    if cwd.startswith(bag_dir) and cwd != bag_dir:
        raise RuntimeError(
            _("Bagging a parent of the current directory is not supported")
        )

    LOGGER.info(_("Creating bag for directory %s"), bag_dir)

    if not os.path.isdir(bag_dir):
        LOGGER.error(_("Bag directory %s does not exist"), bag_dir)
        raise RuntimeError(_("Bag directory %s does not exist") % bag_dir)

    # FIXME: we should do the permissions checks before changing directories
    old_dir = os.path.abspath(os.path.curdir)

    try:
        # TODO: These two checks are currently redundant since an unreadable directory will also
        #       often be unwritable, and this code will require review when we add the option to
        #       bag to a destination other than the source. It would be nice if we could avoid
        #       walking the directory tree more than once even if most filesystems will cache it

        unbaggable = _can_bag(bag_dir)

        if unbaggable:
            LOGGER.error(
                _("Unable to write to the following directories and files:\n%s"),
                unbaggable,
            )
            raise BagError(_("Missing permissions to move all files and directories"))

        unreadable_dirs, unreadable_files = _can_read(bag_dir)

        if unreadable_dirs or unreadable_files:
            if unreadable_dirs:
                LOGGER.error(
                    _("The following directories do not have read permissions:\n%s"),
                    unreadable_dirs,
                )
            if unreadable_files:
                LOGGER.error(
                    _("The following files do not have read permissions:\n%s"),
                    unreadable_files,
                )
            raise BagError(
                _("Read permissions are required to calculate file fixities")
            )
        else:
            LOGGER.info(_("Creating data directory"))

            # FIXME: if we calculate full paths we won't need to deal with changing directories
            os.chdir(bag_dir)
            cwd = os.getcwd()
            temp_data = tempfile.mkdtemp(dir=cwd)

            for f in os.listdir("."):
                if os.path.abspath(f) == temp_data:
                    continue
                new_f = os.path.join(temp_data, f)
                LOGGER.info(
                    _("Moving %(source)s to %(destination)s"),
                    {"source": f, "destination": new_f},
                )
                os.rename(f, new_f)

            LOGGER.info(
                _("Moving %(source)s to %(destination)s"),
                {"source": temp_data, "destination": "data"},
            )
            os.rename(temp_data, "data")

            # permissions for the payload directory should match those of the
            # original directory
            os.chmod("data", os.stat(cwd).st_mode)

            total_bytes, total_files = make_manifests(
                "data", processes, algorithms=checksums, encoding=encoding
            )

            LOGGER.info(_("Creating bagit.txt"))
            txt = """BagIt-Version: 0.97\nTag-File-Character-Encoding: UTF-8\n"""
            with open_text_file("bagit.txt", "w") as bagit_file:
                bagit_file.write(txt)

            LOGGER.info(_("Creating bag-info.txt"))
            if bag_info is None:
                bag_info = {}

            # allow 'Bagging-Date' and 'Bag-Software-Agent' to be overidden
            if "Bagging-Date" not in bag_info:
                bag_info["Bagging-Date"] = date.strftime(date.today(), "%Y-%m-%d")
            if "Bag-Software-Agent" not in bag_info:
                bag_info["Bag-Software-Agent"] = "bagit.py v%s <%s>" % (
                    VERSION,
                    PROJECT_URL,
                )

            bag_info["Payload-Oxum"] = "%s.%s" % (total_bytes, total_files)
            make_tag_file("bag-info.txt", bag_info)

            for c in checksums:
                make_tagmanifest_file(c, bag_dir, encoding="utf-8")
    except Exception:
        LOGGER.exception(_("An error occurred creating a bag in %s"), bag_dir)
        raise
    finally:
        os.chdir(old_dir)

    return Bag(bag_dir)

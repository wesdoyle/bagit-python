import os
import warnings
from datetime import date

from bagit_modules.translation_catalog import _
from bagit_modules.bag import Bag
from bagit_modules.constants import PROJECT_URL, DEFAULT_CHECKSUMS
from bagit_modules.errors import BagError
from bagit_modules.io import open_text_file
from bagit_modules.logging import LOGGER
from bagit_modules.manifests import make_manifests, make_tagmanifest_file
from bagit_modules.tagging import make_tag_file
from bagit_modules.versioning import get_version


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
            _("The `checksum` argument for `make_bag` should be replaced with `checksums`"),
            DeprecationWarning,
        )
        checksums = checksum

    if checksums is None:
        checksums = DEFAULT_CHECKSUMS

    bag_dir = os.path.abspath(bag_dir)

    if not os.path.isdir(bag_dir):
        LOGGER.error(_("Bag directory %s does not exist"), bag_dir)
        raise RuntimeError(_("Bag directory %s does not exist") % bag_dir)

    if os.path.abspath(os.getcwd()).startswith(bag_dir):
        raise RuntimeError(_("Bagging a parent of the current directory is not supported"))

    LOGGER.info(_("Creating bag for directory %s"), bag_dir)

    permissions = _check_directory_permissions(bag_dir)

    if permissions["unreadable_dirs"] or permissions["unreadable_files"]:
        LOGGER.error(_("The following directories and files do not have read permissions:"))
        for path in permissions["unreadable_dirs"] + permissions["unreadable_files"]:
            LOGGER.error(path)
        raise BagError(_("Read permissions are required to calculate file fixities"))

    if permissions["unwritable_dirs"] or permissions["unwritable_files"]:
        LOGGER.error(_("The following directories and files do not have write permissions:"))
        for path in permissions["unwritable_dirs"] + permissions["unwritable_files"]:
            LOGGER.error(path)
        raise BagError(_("Write permissions are required to move all files and directories"))

    if not os.path.isdir(bag_dir):
        LOGGER.error(_("Bag directory %s does not exist"), bag_dir)
        raise RuntimeError(_("Bag directory %s does not exist") % bag_dir)

    old_dir = os.path.abspath(os.getcwd())

    try:
        # Create data directory and move existing items into it
        data_dir = os.path.join(bag_dir, "data")
        if not os.path.exists(data_dir):
            os.mkdir(data_dir)

        for item in os.listdir(bag_dir):
            item_path = os.path.join(bag_dir, item)
            if item_path != data_dir:
                os.rename(item_path, os.path.join(data_dir, item))

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

        # Allow 'Bagging-Date' and 'Bag-Software-Agent' to be overridden
        if "Bagging-Date" not in bag_info:
            bag_info["Bagging-Date"] = date.strftime(date.today(), "%Y-%m-%d")
        if "Bag-Software-Agent" not in bag_info:
            bag_info["Bag-Software-Agent"] = "bagit.py v%s <%s>" % (
                get_version(),
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


def _check_directory_permissions(directory):
    unreadable_dirs = []
    unwritable_dirs = []
    unreadable_files = []
    unwritable_files = []

    for dir_path, dir_names, filenames in os.walk(directory):
        # Check directories
        for dn in dir_names:
            full_path = os.path.join(dir_path, dn)
            if not os.access(full_path, os.R_OK):
                unreadable_dirs.append(full_path)
            if not os.access(full_path, os.W_OK):
                unwritable_dirs.append(full_path)

        # Check files
        for fn in filenames:
            full_path = os.path.join(dir_path, fn)
            if not os.access(full_path, os.R_OK):
                unreadable_files.append(full_path)
            if not os.access(full_path, os.W_OK):
                unwritable_files.append(full_path)

    return {
        "unreadable_dirs": unreadable_dirs,
        "unwritable_dirs": unwritable_dirs,
        "unreadable_files": unreadable_files,
        "unwritable_files": unwritable_files,
    }

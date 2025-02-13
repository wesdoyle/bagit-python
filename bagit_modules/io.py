import codecs
import os
import sys
from functools import partial


def walk(data_dir):
    for dir_path, dir_names, filenames in os.walk(data_dir):
        # Sort for deterministic order, facilitating fixity testing
        filenames.sort()
        dir_names.sort()
        for fn in filenames:
            path = os.path.normpath(os.path.join(dir_path, fn)).replace(os.path.sep, '/')
            yield path


def can_bag(test_dir):
    """Scan the provided directory for files which cannot be bagged due to insufficient permissions"""
    unbaggable = []

    # Check top-level directory permissions
    if not os.access(test_dir, os.R_OK):
        # We cannot continue without permission to read the source directory
        return [test_dir]

    if not os.access(test_dir, os.W_OK):
        unbaggable.append(test_dir)

    for dir_path, dir_names, _ in os.walk(test_dir):
        unbaggable.extend(os.path.join(dir_path, directory) for directory in dir_names if
                          not os.access(os.path.join(dir_path, directory), os.W_OK))

    return unbaggable


def find_tag_files(bag_dir):
    for item in os.listdir(bag_dir):
        full_path = os.path.join(bag_dir, item)
        if item != "data" and os.path.isfile(full_path) and not item.startswith("tagmanifest-"):
            yield item
        elif os.path.isdir(full_path):
            for dir_name, _, filenames in os.walk(full_path):
                for filename in filenames:
                    if not filename.startswith("tagmanifest-"):
                        yield os.path.relpath(os.path.join(dir_name, filename), bag_dir)


def can_read(test_dir):
    """Returns tuples of unreadable directories and unreadable files."""
    unreadable_dirs = []
    unreadable_files = []

    if not os.access(test_dir, os.R_OK):
        unreadable_dirs.append(test_dir)
    else:
        for dir_path, dir_names, filenames in os.walk(test_dir):
            for dn in dir_names:
                full_path = os.path.join(dir_path, dn)
                if not os.access(full_path, os.R_OK):
                    unreadable_dirs.append(full_path)
            for fn in filenames:
                full_path = os.path.join(dir_path, fn)
                if not os.access(full_path, os.R_OK):
                    unreadable_files.append(full_path)
    return tuple(unreadable_dirs), tuple(unreadable_files)


def find_locale_dir():
    for prefix in (os.path.dirname(__file__), sys.prefix):
        locale_dir = os.path.join(prefix, "locale")
        if os.path.isdir(locale_dir):
            return locale_dir


#: Convenience function used everywhere we want to open a file to read text
#: rather than un-decoded bytes:
open_text_file = partial(codecs.open, encoding="utf-8", errors="strict")

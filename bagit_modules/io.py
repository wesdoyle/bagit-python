from __future__ import division, absolute_import, print_function, unicode_literals

import os
import sys
from os.path import join


def _walk(data_dir):
    for dirpath, dirnames, filenames in os.walk(data_dir):
        # if we don't sort here the order of entries is non-deterministic
        # which makes it hard to test the fixity of tagmanifest-md5.txt
        filenames.sort()
        dirnames.sort()
        for fn in filenames:
            path = os.path.join(dirpath, fn)
            # BagIt spec requires manifest to always use '/' as path separator
            if os.path.sep != "/":
                parts = path.split(os.path.sep)
                path = "/".join(parts)
            yield path


def _can_bag(test_dir):
    """Scan the provided directory for files which cannot be bagged due to insufficient permissions"""
    unbaggable = []

    if not os.access(test_dir, os.R_OK):
        # We cannot continue without permission to read the source directory
        unbaggable.append(test_dir)
        return unbaggable

    if not os.access(test_dir, os.W_OK):
        unbaggable.append(test_dir)

    for dirpath, dirnames, filenames in os.walk(test_dir):
        for directory in dirnames:
            full_path = os.path.join(dirpath, directory)
            if not os.access(full_path, os.W_OK):
                unbaggable.append(full_path)

    return unbaggable


def _find_tag_files(bag_dir):
    for dir in os.listdir(bag_dir):
        if dir != "data":
            if os.path.isfile(dir) and not dir.startswith("tagmanifest-"):
                yield dir
            for dir_name, _, filenames in os.walk(dir):
                for filename in filenames:
                    if filename.startswith("tagmanifest-"):
                        continue
                    # remove everything up to the bag_dir directory
                    p = join(dir_name, filename)
                    yield os.path.relpath(p, bag_dir)


def _can_read(test_dir):
    """
    returns ((unreadable_dirs), (unreadable_files))
    """
    unreadable_dirs = []
    unreadable_files = []

    if not os.access(test_dir, os.R_OK):
        unreadable_dirs.append(test_dir)
    else:
        for dirpath, dirnames, filenames in os.walk(test_dir):
            for dn in dirnames:
                full_path = os.path.join(dirpath, dn)
                if not os.access(full_path, os.R_OK):
                    unreadable_dirs.append(full_path)
            for fn in filenames:
                full_path = os.path.join(dirpath, fn)
                if not os.access(full_path, os.R_OK):
                    unreadable_files.append(full_path)
    return (tuple(unreadable_dirs), tuple(unreadable_files))


def find_locale_dir():
    for prefix in (os.path.dirname(__file__), sys.prefix):
        locale_dir = os.path.join(prefix, "locale")
        if os.path.isdir(locale_dir):
            return locale_dir

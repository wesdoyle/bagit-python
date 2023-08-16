from __future__ import division, absolute_import, print_function, unicode_literals

import codecs
import multiprocessing
import os
import warnings
from os.path import abspath, isfile, isdir
from urllib.parse import urlparse

from bagit import _, CHECKSUM_ALGOS, normalize_unicode, open_text_file, UNICODE_BYTE_ORDER_MARK, \
    force_unicode, posix_multiprocessing_worker_initializer
from bagit_modules.hashing import _calc_hashes
from bagit_modules.tagging import _make_tag_file, _load_tag_file
from bagit_modules.filenames import _decode_filename
from bagit_modules.manifests import make_manifests, _make_tagmanifest_file
from bagit_modules.io import _can_bag, _can_read
from bagit_modules.logging import LOGGER
from bagit_modules.errors import BagError, BagValidationError, ChecksumMismatch, FileMissing, UnexpectedFile


class Bag(object):
    """A representation of a bag."""

    valid_files = ["bagit.txt", "fetch.txt"]
    valid_directories = ["data"]

    def __init__(self, path=None):
        super(Bag, self).__init__()
        self.tags = {}
        self.info = {}
        #: Dictionary of manifest entries and the checksum values for each
        #: algorithm:
        self.entries = {}

        # To reliably handle Unicode normalization differences, we maintain
        # lookup dictionaries in both directions for the filenames read from
        # the filesystem and the manifests so we can handle cases where the
        # normalization form changed between the bag being created and read.
        # See https://github.com/LibraryOfCongress/bagit-python/issues/51.

        #: maps Unicode-normalized values to the raw value from the filesystem
        self.normalized_filesystem_names = {}

        #: maps Unicode-normalized values to the raw value in the manifest
        self.normalized_manifest_names = {}

        self.algorithms = []
        self.tag_file_name = None
        self.path = abspath(path)
        if path:
            # if path ends in a path separator, strip it off
            if path[-1] == os.sep:
                self.path = path[:-1]
            self._open()

    def __str__(self):
        # FIXME: develop a more informative string representation for a Bag
        return self.path

    @property
    def algs(self):
        warnings.warn(_("Use Bag.algorithms instead of Bag.algs"), DeprecationWarning)
        return self.algorithms

    @property
    def version(self):
        warnings.warn(
            _("Use the Bag.version_info tuple instead of Bag.version"),
            DeprecationWarning,
        )
        return self._version

    def _open(self):
        # Open the bagit.txt file, and load any tags from it, including
        # the required version and encoding.
        bagit_file_path = os.path.join(self.path, "bagit.txt")

        if not isfile(bagit_file_path):
            raise BagError(_("Expected bagit.txt does not exist: %s") % bagit_file_path)

        self.tags = tags = _load_tag_file(bagit_file_path)

        required_tags = ("BagIt-Version", "Tag-File-Character-Encoding")
        missing_tags = [i for i in required_tags if i not in tags]
        if missing_tags:
            raise BagError(
                _("Missing required tag in bagit.txt: %s") % ", ".join(missing_tags)
            )

        # To avoid breaking existing code we'll leave self.version as the string
        # and parse it into a numeric version_info tuple. In version 2.0 we can
        # break that.

        self._version = tags["BagIt-Version"]

        try:
            self.version_info = tuple(int(i) for i in self._version.split(".", 1))
        except ValueError:
            raise BagError(
                _("Bag version numbers must be MAJOR.MINOR numbers, not %s")
                % self._version
            )

        if (0, 93) <= self.version_info <= (0, 95):
            self.tag_file_name = "package-info.txt"
        elif (0, 96) <= self.version_info < (2,):
            self.tag_file_name = "bag-info.txt"
        else:
            raise BagError(_("Unsupported bag version: %s") % self._version)

        self.encoding = tags["Tag-File-Character-Encoding"]

        try:
            codecs.lookup(self.encoding)
        except LookupError:
            raise BagValidationError(_("Unsupported encoding: %s") % self.encoding)

        info_file_path = os.path.join(self.path, self.tag_file_name)
        if os.path.exists(info_file_path):
            self.info = _load_tag_file(info_file_path, encoding=self.encoding)

        self._load_manifests()

    def manifest_files(self):
        for filename in ["manifest-%s.txt" % a for a in CHECKSUM_ALGOS]:
            f = os.path.join(self.path, filename)
            if isfile(f):
                yield f

    def tagmanifest_files(self):
        for filename in ["tagmanifest-%s.txt" % a for a in CHECKSUM_ALGOS]:
            f = os.path.join(self.path, filename)
            if isfile(f):
                yield f

    def compare_manifests_with_fs(self):
        """
        Compare the filenames in the manifests to the filenames present on the
        local filesystem and returns two lists of the files which are only
        present in the manifests and the files which are only present on the
        local filesystem, respectively.
        """

        # We compare the filenames after Unicode normalization so we can
        # reliably detect normalization changes after bag creation:
        files_on_fs = set(normalize_unicode(i) for i in self.payload_files())
        files_in_manifest = set(
            normalize_unicode(i) for i in self.payload_entries().keys()
        )

        if self.version_info >= (0, 97):
            files_in_manifest.update(self.missing_optional_tagfiles())

        only_on_fs = list()
        only_in_manifest = list()

        for i in files_on_fs.difference(files_in_manifest):
            only_on_fs.append(self.normalized_filesystem_names[i])

        for i in files_in_manifest.difference(files_on_fs):
            only_in_manifest.append(self.normalized_manifest_names[i])

        return only_in_manifest, only_on_fs

    def compare_fetch_with_fs(self):
        """Compares the fetch entries with the files actually
           in the payload, and returns a list of all the files
           that still need to be fetched.
        """

        files_on_fs = set(self.payload_files())
        files_in_fetch = set(self.files_to_be_fetched())

        return list(files_in_fetch - files_on_fs)

    def payload_files(self):
        """Returns a list of filenames which are present on the local filesystem"""
        payload_dir = os.path.join(self.path, "data")

        for dirpath, _, filenames in os.walk(payload_dir):
            for f in filenames:
                # Jump through some hoops here to make the payload files are
                # returned with the directory structure relative to the base
                # directory rather than the
                normalized_f = os.path.normpath(f)
                rel_path = os.path.relpath(
                    os.path.join(dirpath, normalized_f), start=self.path
                )

                self.normalized_filesystem_names[normalize_unicode(rel_path)] = rel_path
                yield rel_path

    def payload_entries(self):
        """Return a dictionary of items """
        # Don't use dict comprehension (compatibility with Python < 2.7)
        return dict(
            (key, value)
            for (key, value) in self.entries.items()
            if key.startswith("data" + os.sep)
        )

    def save(self, processes=1, manifests=False):
        """
        save will persist any changes that have been made to the bag
        metadata (self.info).

        If you have modified the payload of the bag (added, modified,
        removed files in the data directory) and want to regenerate manifests
        set the manifests parameter to True. The default is False since you
        wouldn't want a save to accidentally create a new manifest for
        a corrupted bag.

        If you want to control the number of processes that are used when
        recalculating checksums use the processes parameter.
        """
        # Error checking
        if not self.path:
            raise BagError(_("Bag.save() called before setting the path!"))

        if not os.access(self.path, os.R_OK | os.W_OK | os.X_OK):
            raise BagError(
                _("Cannot save bag to non-existent or inaccessible directory %s")
                % self.path
            )

        unbaggable = _can_bag(self.path)
        if unbaggable:
            LOGGER.error(
                _(
                    "Missing write permissions for the following directories and files:\n%s"
                ),
                unbaggable,
            )
            raise BagError(_("Missing permissions to move all files and directories"))

        unreadable_dirs, unreadable_files = _can_read(self.path)
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

        # Change working directory to bag directory so helper functions work
        old_dir = os.path.abspath(os.path.curdir)
        os.chdir(self.path)

        # Generate new manifest files
        if manifests:
            total_bytes, total_files = make_manifests(
                "data", processes, algorithms=self.algorithms, encoding=self.encoding
            )

            # Update Payload-Oxum
            LOGGER.info(_("Updating Payload-Oxum in %s"), self.tag_file_name)
            self.info["Payload-Oxum"] = "%s.%s" % (total_bytes, total_files)

        _make_tag_file(self.tag_file_name, self.info)

        # Update tag-manifest for changes to manifest & bag-info files
        for alg in self.algorithms:
            _make_tagmanifest_file(alg, self.path, encoding=self.encoding)

        # Reload the manifests
        self._load_manifests()

        os.chdir(old_dir)

    def tagfile_entries(self):
        return dict(
            (key, value)
            for (key, value) in self.entries.items()
            if not key.startswith("data" + os.sep)
        )

    def missing_optional_tagfiles(self):
        """
        From v0.97 we need to validate any tagfiles listed
        in the optional tagmanifest(s). As there is no mandatory
        directory structure for additional tagfiles we can
        only check for entries with missing files (not missing
        entries for existing files).
        """
        for tagfilepath in self.tagfile_entries().keys():
            if not os.path.isfile(os.path.join(self.path, tagfilepath)):
                yield tagfilepath

    def fetch_entries(self):
        """Load fetch.txt if present and iterate over its contents

        yields (url, size, filename) tuples

        raises BagError for errors such as an unsafe filename referencing
        data outside of the bag directory
        """

        fetch_file_path = os.path.join(self.path, "fetch.txt")

        if isfile(fetch_file_path):
            with open_text_file(
                fetch_file_path, "r", encoding=self.encoding
            ) as fetch_file:
                for line in fetch_file:
                    url, file_size, filename = line.strip().split(None, 2)

                    if self._path_is_dangerous(filename):
                        raise BagError(
                            _('Path "%(payload_file)s" in "%(source_file)s" is unsafe')
                            % {
                                "payload_file": filename,
                                "source_file": os.path.join(self.path, "fetch.txt"),
                            }
                        )

                    yield url, file_size, filename

    def files_to_be_fetched(self):
        """
        Convenience wrapper for fetch_entries which returns only the
        local filename
        """

        for url, file_size, filename in self.fetch_entries():
            yield filename

    def has_oxum(self):
        return "Payload-Oxum" in self.info

    def validate(self, processes=1, fast=False, completeness_only=False):
        """Checks the structure and contents are valid.

        If you supply the parameter fast=True the Payload-Oxum (if present) will
        be used to check that the payload files are present and accounted for,
        instead of re-calculating fixities and comparing them against the
        manifest. By default validate() will re-calculate fixities (fast=False).
        """

        self._validate_structure()
        self._validate_bagittxt()

        self.validate_fetch()

        self._validate_contents(
            processes=processes, fast=fast, completeness_only=completeness_only
        )

        return True

    def is_valid(self, fast=False, completeness_only=False):
        """Returns validation success or failure as boolean.
        Optional fast parameter passed directly to validate().
        """

        try:
            self.validate(fast=fast, completeness_only=completeness_only)
        except BagError:
            return False

        return True

    def _load_manifests(self):
        self.entries = {}
        manifests = list(self.manifest_files())

        if self.version_info >= (0, 97):
            # v0.97+ requires that optional tagfiles are verified.
            manifests += list(self.tagmanifest_files())

        for manifest_filename in manifests:
            if manifest_filename.find("tagmanifest-") != -1:
                search = "tagmanifest-"
            else:
                search = "manifest-"
            alg = (
                os.path.basename(manifest_filename)
                .replace(search, "")
                .replace(".txt", "")
            )
            if alg not in self.algorithms:
                self.algorithms.append(alg)

            with open_text_file(
                manifest_filename, "r", encoding=self.encoding
            ) as manifest_file:
                if manifest_file.encoding.startswith("UTF"):
                    # We'll check the first character to see if it's a BOM:
                    if manifest_file.read(1) == UNICODE_BYTE_ORDER_MARK:
                        # We'll skip it either way by letting line decoding
                        # happen at the new offset but we will issue a warning
                        # for UTF-8 since the presence of a BOM  is contrary to
                        # the BagIt specification:
                        if manifest_file.encoding == "UTF-8":
                            LOGGER.warning(
                                _(
                                    "%s is encoded using UTF-8 but contains an unnecessary"
                                    " byte-order mark, which is not in compliance with the"
                                    " BagIt RFC"
                                ),
                                manifest_file.name,
                            )
                    else:
                        manifest_file.seek(0)  # Pretend the first read never happened

                for line in manifest_file:
                    line = line.strip()

                    # Ignore blank lines and comments.
                    if line == "" or line.startswith("#"):
                        continue

                    entry = line.split(None, 1)

                    # Format is FILENAME *CHECKSUM
                    if len(entry) != 2:
                        LOGGER.error(
                            _(
                                "%(bag)s: Invalid %(algorithm)s manifest entry: %(line)s"
                            ),
                            {"bag": self, "algorithm": alg, "line": line},
                        )
                        continue

                    entry_hash = entry[0]
                    entry_path = os.path.normpath(entry[1].lstrip("*"))
                    entry_path = _decode_filename(entry_path)

                    if self._path_is_dangerous(entry_path):
                        raise BagError(
                            _(
                                'Path "%(payload_file)s" in manifest "%(manifest_file)s" is unsafe'
                            )
                            % {
                                "payload_file": entry_path,
                                "manifest_file": manifest_file.name,
                            }
                        )

                    entry_hashes = self.entries.setdefault(entry_path, {})

                    if alg in entry_hashes:
                        warning_ctx = {
                            "bag": self,
                            "algorithm": alg,
                            "filename": entry_path,
                        }
                        if entry_hashes[alg] == entry_hash:
                            msg = _(
                                "%(bag)s: %(algorithm)s manifest lists %(filename)s"
                                " multiple times with the same value"
                            )
                            if self.version_info >= (1,):
                                raise BagError(msg % warning_ctx)
                            else:
                                LOGGER.warning(msg, warning_ctx)
                        else:
                            raise BagError(
                                _(
                                    "%(bag)s: %(algorithm)s manifest lists %(filename)s"
                                    " multiple times with conflicting values"
                                )
                                % warning_ctx
                            )

                    entry_hashes[alg] = entry_hash

        self.normalized_manifest_names.update(
            (normalize_unicode(i), i) for i in self.entries.keys()
        )

    def _validate_structure(self):
        """
        Checks the structure of the bag to determine whether it conforms to the
        BagIt spec. Returns true on success, otherwise it will raise a
        BagValidationError exception.
        """

        self._validate_structure_payload_directory()
        self._validate_structure_tag_files()

    def _validate_structure_payload_directory(self):
        data_dir_path = os.path.join(self.path, "data")

        if not isdir(data_dir_path):
            raise BagValidationError(
                _("Expected data directory %s does not exist") % data_dir_path
            )

    def _validate_structure_tag_files(self):
        # Note: we deviate somewhat from v0.96 of the spec in that it allows
        # other files and directories to be present in the base directory

        if not list(self.manifest_files()):
            raise BagValidationError(_("No manifest files found"))
        if "bagit.txt" not in os.listdir(self.path):
            raise BagValidationError(
                _('Expected %s to contain "bagit.txt"') % self.path
            )

    def validate_fetch(self):
        """Validate the fetch.txt file

        Raises `BagError` for errors and otherwise returns no value
        """

        for url, file_size, filename in self.fetch_entries():
            # fetch_entries will raise a BagError for unsafe filenames
            # so at this point we will check only that the URL is minimally
            # well formed:
            parsed_url = urlparse(url)

            if not all((parsed_url.scheme, parsed_url.netloc)):
                raise BagError(_("Malformed URL in fetch.txt: %s") % url)

    def _validate_contents(self, processes=1, fast=False, completeness_only=False):
        if fast and not self.has_oxum():
            raise BagValidationError(
                _("Fast validation requires bag-info.txt to include Payload-Oxum")
            )

        # Perform the fast file count + size check so we can fail early:
        self._validate_oxum()

        if fast:
            return

        self._validate_completeness()

        if completeness_only:
            return

        self._validate_entries(processes)

    def _validate_oxum(self):
        oxum = self.info.get("Payload-Oxum")

        if oxum is None:
            return

        # If multiple Payload-Oxum tags (bad idea)
        # use the first listed in bag-info.txt
        if isinstance(oxum, list):
            LOGGER.warning(_("bag-info.txt defines multiple Payload-Oxum values!"))
            oxum = oxum[0]

        oxum_byte_count, oxum_file_count = oxum.split(".", 1)

        if not oxum_byte_count.isdigit() or not oxum_file_count.isdigit():
            raise BagError(_("Malformed Payload-Oxum value: %s") % oxum)

        oxum_byte_count = int(oxum_byte_count)
        oxum_file_count = int(oxum_file_count)
        total_bytes = 0
        total_files = 0

        for payload_file in self.payload_files():
            payload_file = os.path.join(self.path, payload_file)
            total_bytes += os.stat(payload_file).st_size
            total_files += 1

        if oxum_file_count != total_files or oxum_byte_count != total_bytes:
            raise BagValidationError(
                _(
                    "Payload-Oxum validation failed."
                    " Expected %(oxum_file_count)d files and %(oxum_byte_count)d bytes"
                    " but found %(found_file_count)d files and %(found_byte_count)d bytes"
                )
                % {
                    "found_file_count": total_files,
                    "found_byte_count": total_bytes,
                    "oxum_file_count": oxum_file_count,
                    "oxum_byte_count": oxum_byte_count,
                }
            )

    def _validate_completeness(self):
        """
        Verify that the actual file manifests match the files in the data directory
        """
        errors = list()

        # First we'll make sure there's no mismatch between the filesystem
        # and the list of files in the manifest(s)
        only_in_manifests, only_on_fs = self.compare_manifests_with_fs()
        for path in only_in_manifests:
            e = FileMissing(path)
            LOGGER.warning(force_unicode(e))
            errors.append(e)
        for path in only_on_fs:
            e = UnexpectedFile(path)
            LOGGER.warning(force_unicode(e))
            errors.append(e)

        if errors:
            raise BagValidationError(_("Bag is incomplete"), errors)

    def _validate_entries(self, processes):
        """
        Verify that the actual file contents match the recorded hashes stored in the manifest files
        """
        errors = list()

        if os.name == "posix":
            worker_init = posix_multiprocessing_worker_initializer
        else:
            worker_init = None

        args = (
            (
                self.path,
                self.normalized_filesystem_names.get(rel_path, rel_path),
                hashes,
                self.algorithms,
            )
            for rel_path, hashes in self.entries.items()
        )

        try:
            if processes == 1:
                hash_results = [_calc_hashes(i) for i in args]
            else:
                try:
                    pool = multiprocessing.Pool(
                        processes if processes else None, initializer=worker_init
                    )
                    hash_results = pool.map(_calc_hashes, args)
                finally:
                    pool.terminate()

        # Any unhandled exceptions are probably fatal
        except:
            LOGGER.exception(_("Unable to calculate file hashes for %s"), self)
            raise

        for rel_path, f_hashes, hashes in hash_results:
            for alg, computed_hash in f_hashes.items():
                stored_hash = hashes[alg]
                if stored_hash.lower() != computed_hash:
                    e = ChecksumMismatch(
                        rel_path, alg, stored_hash.lower(), computed_hash
                    )
                    LOGGER.warning(force_unicode(e))
                    errors.append(e)

        if errors:
            raise BagValidationError(_("Bag validation failed"), errors)

    def _validate_bagittxt(self):
        """
        Verify that bagit.txt conforms to specification
        """
        bagit_file_path = os.path.join(self.path, "bagit.txt")

        # Note that we are intentionally opening this file in binary mode so we can confirm
        # that it does not start with the UTF-8 byte-order-mark
        with open(bagit_file_path, "rb") as bagit_file:
            first_line = bagit_file.read(4)
            if first_line.startswith(codecs.BOM_UTF8):
                raise BagValidationError(
                    _("bagit.txt must not contain a byte-order mark")
                )

    def _path_is_dangerous(self, path):
        """
        Return true if path looks dangerous, i.e. potentially operates
        outside the bagging directory structure, e.g. ~/.bashrc, ../../../secrets.json,
        \\\\?\\c:\\, D:\\sys32\\cmd.exe
        """
        if os.path.isabs(path):
            return True
        if os.path.expanduser(path) != path:
            return True
        if os.path.expandvars(path) != path:
            return True
        real_path = os.path.realpath(os.path.join(self.path, path))
        real_path = os.path.normpath(real_path)
        bag_path = os.path.realpath(self.path)
        bag_path = os.path.normpath(bag_path)
        common = os.path.commonprefix((bag_path, real_path))
        return not (common == bag_path)

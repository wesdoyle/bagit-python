from __future__ import division, absolute_import, print_function, unicode_literals

from bagit import _
from bagit_modules.string_ops import force_unicode


class BagError(Exception):
    pass


class BagValidationError(BagError):
    def __init__(self, message, details=None):
        super(BagValidationError, self).__init__()

        if details is None:
            details = []

        self.message = message
        self.details = details

    def __str__(self):
        if len(self.details) > 0:
            details = "; ".join([force_unicode(e) for e in self.details])
            return "%s: %s" % (self.message, details)
        return self.message


class ManifestErrorDetail(BagError):
    def __init__(self, path):
        super(ManifestErrorDetail, self).__init__()

        self.path = path


class ChecksumMismatch(ManifestErrorDetail):
    def __init__(self, path, algorithm=None, expected=None, found=None):
        super(ChecksumMismatch, self).__init__(path)

        self.path = path
        self.algorithm = algorithm
        self.expected = expected
        self.found = found

    def __str__(self):
        return _(
            '%(path)s %(algorithm)s validation failed: expected="%(expected)s" found="%(found)s"'
        ) % {
            "path": force_unicode(self.path),
            "algorithm": self.algorithm,
            "expected": self.expected,
            "found": self.found,
        }


class FileMissing(ManifestErrorDetail):
    def __str__(self):
        return _(
            "%s exists in manifest but was not found on filesystem"
        ) % force_unicode(self.path)


class UnexpectedFile(ManifestErrorDetail):
    def __str__(self):
        return _("%s exists on filesystem but is not in the manifest") % self.path


class FileNormalizationConflict(BagError):
    """
    Exception raised when two files differ only in normalization and thus
    are not safely portable
    """

    def __init__(self, file_a, file_b):
        super(FileNormalizationConflict, self).__init__()

        self.file_a = file_a
        self.file_b = file_b

    def __str__(self):
        return _(
            'Unicode normalization conflict for file "%(file_a)s" and "%(file_b)s"'
        ) % {"file_a": self.file_a, "file_b": self.file_b}

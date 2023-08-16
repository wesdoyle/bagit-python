from __future__ import division, absolute_import, print_function, unicode_literals

import unicodedata


def force_unicode(s):
    return str(s)


def normalize_unicode(s):
    return unicodedata.normalize("NFC", s)

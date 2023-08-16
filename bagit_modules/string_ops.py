import unicodedata


def force_unicode(s):
    return str(s)


def normalize_unicode(s):
    return unicodedata.normalize("NFC", s)

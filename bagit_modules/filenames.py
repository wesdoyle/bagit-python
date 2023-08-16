from __future__ import division, absolute_import, print_function, unicode_literals

import re


def _encode_filename(s):
    s = s.replace("\r", "%0D")
    s = s.replace("\n", "%0A")
    return s


def _decode_filename(s):
    s = re.sub(r"%0D", "\r", s, re.IGNORECASE)
    s = re.sub(r"%0A", "\n", s, re.IGNORECASE)
    return s

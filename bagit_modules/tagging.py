import os
import re

from bagit import _, open_text_file
from bagit_modules.string_ops import force_unicode
from bagit_modules.errors import BagValidationError


def make_tag_file(bag_info_path, bag_info):
    headers = sorted(bag_info.keys())
    with open_text_file(bag_info_path, "w") as f:
        for h in headers:
            values = bag_info[h]
            if not isinstance(values, list):
                values = [values]
            for txt in values:
                txt = force_unicode(txt).replace("\n", "").replace("\r", "")
                f.write("%s: %s\n" % (h, txt))


def load_tag_file(tag_file_name, encoding="utf-8-sig"):
    with open_text_file(tag_file_name, "r", encoding=encoding) as tag_file:
        tags = {}
        for name, value in _parse_tags(tag_file):
            tags.setdefault(name, []).append(value)
        return {k: v[0] if len(v) == 1 else v for k, v in tags.items()}


def _parse_tags(tag_file):
    """Parses a tag file, according to RFC 2822.  This
       includes line folding, permitting extra-long
       field values.

       See http://www.faqs.org/rfcs/rfc2822.html for
       more information.
    """

    tag_name = None
    tag_value = None

    # Line folding is handled by yielding values only after we encounter
    # the start of a new tag, or if we pass the EOF.
    for num, line in enumerate(tag_file):
        # Skip over any empty or blank lines.
        if len(line) == 0 or line.isspace():
            continue
        elif line[0].isspace() and tag_value is not None:  # folded line
            tag_value += line
        else:
            # Starting a new tag; yield the last one.
            if tag_name:
                yield tag_name, tag_value.strip()

            if ":" not in line:
                raise BagValidationError(
                    _("%(filename)s contains invalid tag: %(line)s")
                    % {
                        "line": line.strip(),
                        "filename": os.path.basename(tag_file.name),
                    }
                )

            parts = line.strip().split(":", 1)
            tag_name = parts[0].strip()
            tag_value = parts[1]

    # Passed the EOF.  All done after this.
    if tag_name:
        yield tag_name, tag_value.strip()

import os

from bagit_modules.translation_catalog import _
from bagit_modules.io import open_text_file
from bagit_modules.errors import BagValidationError
from bagit_modules.string_ops import force_unicode


def make_tag_file(bag_info_path, bag_info):
    headers = sorted(bag_info.keys())
    output_lines = []

    for h in headers:
        values = bag_info[h]
        if not isinstance(values, list):
            values = [values]
        for txt in values:
            sanitized_txt = force_unicode(txt).replace("\n", "").replace("\r", "")
            output_lines.append(f"{h}: {sanitized_txt}")

    with open_text_file(bag_info_path, "w") as f:
        f.write("\n".join(output_lines))


def load_tag_file(tag_file_name, encoding="utf-8-sig"):
    with open_text_file(tag_file_name, "r", encoding=encoding) as tag_file:
        tags = {}
        for name, value in _parse_tags(tag_file):
            tags.setdefault(name, []).append(value)
        return {k: v[0] if len(v) == 1 else v for k, v in tags.items()}


def _parse_tags(tag_file):
    """Parses a tag file, according to RFC 2822. This includes line folding, permitting extra-long field values."""
    tag_name = None
    tag_value = None
    filename = os.path.basename(tag_file.name)

    for line in tag_file:
        stripped_line = line.strip()

        if not stripped_line:
            continue

        # Check for folded line
        if line[0].isspace() and tag_value is not None:
            tag_value += stripped_line
            continue

        # Yield the last tag before starting a new one
        if tag_name:
            yield tag_name, tag_value

        # Check for invalid tags
        if ":" not in stripped_line:
            raise BagValidationError(
                _("%(filename)s contains invalid tag: %(line)s") % {"line": stripped_line, "filename": filename})

        tag_name, tag_value = stripped_line.split(":", 1)

    # Yield any remaining tag after the loop
    if tag_name:
        yield tag_name, tag_value

from __future__ import division, absolute_import, print_function, unicode_literals

import hashlib
import multiprocessing
import re
from collections import defaultdict
from functools import partial
from os.path import join

from bagit import _, open_text_file
from bagit_modules.constants import HASH_BLOCK_SIZE, DEFAULT_CHECKSUMS
from bagit_modules.hashing import get_hashers
from bagit_modules.filenames import _encode_filename, _decode_filename
from bagit_modules.io import _walk, _find_tag_files
from bagit_modules.logging import LOGGER


def make_manifests(data_dir, processes, algorithms=DEFAULT_CHECKSUMS, encoding="utf-8"):
    LOGGER.info(
        _("Using %(process_count)d processes to generate manifests: %(algorithms)s"),
        {"process_count": processes, "algorithms": ", ".join(algorithms)},
    )

    manifest_line_generator = partial(generate_manifest_lines, algorithms=algorithms)

    if processes > 1:
        pool = multiprocessing.Pool(processes=processes)
        checksums = pool.map(manifest_line_generator, _walk(data_dir))
        pool.close()
        pool.join()
    else:
        checksums = [manifest_line_generator(i) for i in _walk(data_dir)]

    # At this point we have a list of tuples which start with the algorithm name:
    manifest_data = {}
    for batch in checksums:
        for entry in batch:
            manifest_data.setdefault(entry[0], []).append(entry[1:])

    # These will be keyed on the algorithm name so we can perform sanity checks
    # below to catch failures in the hashing process:
    num_files = defaultdict(lambda: 0)
    total_bytes = defaultdict(lambda: 0)

    for algorithm, values in manifest_data.items():
        manifest_filename = "manifest-%s.txt" % algorithm

        with open_text_file(manifest_filename, "w", encoding=encoding) as manifest:
            for digest, filename, byte_count in values:
                manifest.write("%s  %s\n" % (digest, _encode_filename(filename)))
                num_files[algorithm] += 1
                total_bytes[algorithm] += byte_count

    # We'll use sets of the values for the error checks and eventually return the payload oxum values:
    byte_value_set = set(total_bytes.values())
    file_count_set = set(num_files.values())

    # allow a bag with an empty payload
    if not byte_value_set and not file_count_set:
        return 0, 0

    if len(file_count_set) != 1:
        raise RuntimeError(_("Expected the same number of files for each checksum"))

    if len(byte_value_set) != 1:
        raise RuntimeError(_("Expected the same number of bytes for each checksums"))

    return byte_value_set.pop(), file_count_set.pop()


def _make_tagmanifest_file(alg, bag_dir, encoding="utf-8"):
    tagmanifest_file = join(bag_dir, "tagmanifest-%s.txt" % alg)
    LOGGER.info(_("Creating %s"), tagmanifest_file)

    checksums = []
    for f in _find_tag_files(bag_dir):
        if re.match(r"^tagmanifest-.+\.txt$", f):
            continue
        with open(join(bag_dir, f), "rb") as fh:
            m = hashlib.new(alg)
            while True:
                block = fh.read(HASH_BLOCK_SIZE)
                if not block:
                    break
                m.update(block)
            checksums.append((m.hexdigest(), f))

    with open_text_file(
        join(bag_dir, tagmanifest_file), mode="w", encoding=encoding
    ) as tagmanifest:
        for digest, filename in checksums:
            tagmanifest.write("%s %s\n" % (digest, filename))


def generate_manifest_lines(filename, algorithms=DEFAULT_CHECKSUMS):
    LOGGER.info(_("Generating manifest lines for file %s"), filename)

    # For performance we'll read the file only once and pass it block
    # by block to every requested hash algorithm:
    hashers = get_hashers(algorithms)

    total_bytes = 0

    with open(filename, "rb") as f:
        while True:
            block = f.read(HASH_BLOCK_SIZE)

            if not block:
                break

            total_bytes += len(block)
            for hasher in hashers.values():
                hasher.update(block)

    decoded_filename = _decode_filename(filename)

    # We'll generate a list of results in roughly manifest format but prefixed with the algorithm:
    results = [
        (alg, hasher.hexdigest(), decoded_filename, total_bytes)
        for alg, hasher in hashers.items()
    ]

    return results

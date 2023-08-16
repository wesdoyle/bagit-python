from collections import defaultdict
from functools import partial
import hashlib
import multiprocessing
import os
import re

from bagit_modules.translation_catalog import _
from bagit_modules.constants import HASH_BLOCK_SIZE, DEFAULT_CHECKSUMS
from bagit_modules.hashing import get_hashers
from bagit_modules.filenames import encode_filename, decode_filename
from bagit_modules.io import walk, find_tag_files, open_text_file
from bagit_modules.logging import LOGGER


def make_manifests(data_dir, processes, algorithms=DEFAULT_CHECKSUMS, encoding="utf-8"):
    LOGGER.info(_("Using %(process_count)d processes to generate manifests: %(algorithms)s"),
                {"process_count": processes, "algorithms": ", ".join(algorithms)})

    manifest_line_generator = partial(generate_manifest_lines, algorithms=algorithms)

    if processes > 1:
        with multiprocessing.Pool(processes=processes) as pool:
            checksums = pool.map(manifest_line_generator, walk(data_dir))
    else:
        checksums = map(manifest_line_generator, walk(data_dir))

    manifest_data = defaultdict(list)
    num_files = defaultdict(int)
    total_bytes = defaultdict(int)

    for batch in checksums:
        for alg, digest, filename, byte_count in batch:
            manifest_data[alg].append((digest, filename))
            num_files[alg] += 1
            total_bytes[alg] += byte_count

    # We'll use sets of the values for the error checks and eventually return the payload oxum values
    byte_value_set = set(total_bytes.values())
    file_count_set = set(num_files.values())

    if len(byte_value_set) > 1:
        raise RuntimeError(_("Expected the same number of bytes for each checksum"))

    if len(file_count_set) > 1:
        raise RuntimeError(_("Expected the same number of files for each checksum"))

    for algorithm, values in manifest_data.items():
        with open_text_file(f"manifest-{algorithm}.txt", "w", encoding=encoding) as manifest:
            for digest, filename in values:
                manifest.write(f"{digest}  {encode_filename(filename)}\n")

    return byte_value_set.pop(), file_count_set.pop()


def make_tagmanifest_file(alg, bag_dir, encoding="utf-8"):
    tagmanifest_file = os.path.join(bag_dir, f"tagmanifest-{alg}.txt")
    LOGGER.info(_("Creating %s"), tagmanifest_file)

    checksums = []
    m = hashlib.new(alg)

    for f in find_tag_files(bag_dir):
        if not re.match(r"^tagmanifest-.+\.txt$", f):
            with open(os.path.join(bag_dir, f), "rb") as fh:
                for block in iter(lambda: fh.read(HASH_BLOCK_SIZE), b''):
                    m.update(block)
            checksums.append((m.hexdigest(), f))

    with open_text_file(os.path.join(bag_dir, tagmanifest_file), mode="w", encoding=encoding) as tagmanifest:
        for digest, filename in checksums:
            tagmanifest.write(f"{digest} {filename}\n")


def generate_manifest_lines(filename, algorithms=DEFAULT_CHECKSUMS):
    LOGGER.info(_("Generating manifest lines for file %s"), filename)

    # For performance, we'll read the file only once and pass it block
    # by block to every requested hash algorithm:
    hashers = get_hashers(algorithms)
    total_bytes = 0

    with open(filename, "rb") as f:
        for block in iter(lambda: f.read(HASH_BLOCK_SIZE), b''):
            total_bytes += len(block)
            for hasher in hashers.values():
                hasher.update(block)

    decoded_filename = decode_filename(filename)
    return [(alg, hasher.hexdigest(), decoded_filename, total_bytes) for alg, hasher in hashers.items()]

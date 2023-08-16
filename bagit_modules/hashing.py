import hashlib
import os

from bagit import _
from bagit_modules.constants import HASH_BLOCK_SIZE
from bagit_modules.string_ops import force_unicode
from bagit_modules.errors import BagValidationError
from bagit_modules.logging import LOGGER


def calc_hashes(args):
    base_path, rel_path, hashes, algorithms = args
    full_path = os.path.join(base_path, rel_path)

    # Create a clone of the default empty hash objects using set operations:
    valid_algorithms = set(hashes).intersection(algorithms)
    f_hashers = {alg: hashlib.new(alg) for alg in valid_algorithms}

    try:
        f_hashes = _calculate_file_hashes(full_path, f_hashers)
    except BagValidationError as e:
        f_hashes = {alg: force_unicode(e) for alg in f_hashers}

    return rel_path, f_hashes, hashes


def get_hashers(algorithms):
    """
    Given a list of algorithm names, return a dictionary of hasher instances

    This avoids redundant code between the creation and validation code where in
    both cases we want to avoid reading the same file more than once. The
    intended use is a simple for loop:

        for block in file:
            for hasher in hashers.values():
                hasher.update(block)
    """

    hashers = {}

    for alg in algorithms:
        try:
            hasher = hashlib.new(alg)
        except ValueError:
            LOGGER.warning(
                _("Disabling requested hash algorithm %s: hashlib does not support it"),
                alg,
            )
            continue

        hashers[alg] = hasher

    if not hashers:
        raise ValueError(
            _(
                "Unable to continue: hashlib does not support any of the requested algorithms!"
            )
        )

    return hashers


def _calculate_file_hashes(full_path, f_hashers):
    """
    Returns a dictionary of (algorithm, hexdigest) values for the provided
    filename
    """
    LOGGER.info(_("Verifying checksum for file %s"), full_path)

    hashers = list(f_hashers.values())  # Get hashers once before the loop

    try:
        with open(full_path, "rb") as f:
            for block in iter(lambda: f.read(HASH_BLOCK_SIZE), b''):
                for hasher in hashers:
                    hasher.update(block)
    except (OSError, IOError) as e:
        raise BagValidationError(
            _("Could not read %(filename)s: %(error)s")
            % {"filename": full_path, "error": force_unicode(e)}
        )

    return {alg: hasher.hexdigest() for alg, hasher in f_hashers.items()}

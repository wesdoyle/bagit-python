from pkg_resources import get_distribution, DistributionNotFound

from bagit_modules.module import MODULE_NAME


def get_version():
    try:
        return get_distribution(MODULE_NAME).version
    except DistributionNotFound:
        return "0.0.dev0"


from pkg_resources import get_distribution, DistributionNotFound


def get_version():
    try:
        return get_distribution(MODULE_NAME).version
    except DistributionNotFound:
        return "0.0.dev0"


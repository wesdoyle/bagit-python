import signal


def posix_multiprocessing_worker_initializer():
    """Ignore SIGINT in multiprocessing workers on POSIX systems"""
    signal.signal(signal.SIGINT, signal.SIG_IGN)

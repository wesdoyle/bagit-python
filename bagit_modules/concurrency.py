from __future__ import division, absolute_import, print_function, unicode_literals

import signal


def posix_multiprocessing_worker_initializer():
    """Ignore SIGINT in multiprocessing workers on POSIX systems"""
    signal.signal(signal.SIGINT, signal.SIG_IGN)

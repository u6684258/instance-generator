import contextlib
import os
import sys
import time

import psutil


class Timer:
    def __init__(self):
        self.start_time = time.time()
        self.start_clock = self._clock()

    def _clock(self):
        times = os.times()
        return times[0] + times[1]

    def __str__(self):
        return "[{:.3f}s CPU, {:.3f}s wall-clock]".format(
            self._clock() - self.start_clock,
            time.time() - self.start_time)


class MemoryMeasurement:
    def __init__(self):
        self.rss_before, self.vms_before, self.shared_before = get_process_memory()

    def __str__(self):
        rss_after, vms_after, shared_after = get_process_memory()
        return "[{} RSS, {} VMS, {} shared]".format(
                    format_bytes_to_mb(rss_after - self.rss_before),
                    format_bytes_to_mb(vms_after - self.vms_before),
                    format_bytes_to_mb(shared_after - self.shared_before))


# memory profiling based on
# https://stackoverflow.com/a/53301648
def get_process_memory():
    process = psutil.Process(os.getpid())
    mi = process.memory_info()
    return mi.rss, mi.vms, mi.shared


def format_bytes(bytes):
    if abs(bytes) < 1000:
        return str(bytes)+"B"
    elif abs(bytes) < 1e6:
        return str(round(bytes/1e3,2)) + "kB"
    elif abs(bytes) < 1e9:
        return str(round(bytes / 1e6, 2)) + "MB"
    else:
        return str(round(bytes / 1e9, 2)) + "GB"


def format_bytes_to_mb(bytes):
    return str(round(bytes / 1e6, 2)) + "MB"


@contextlib.contextmanager
def timing(text, block=False):
    timer = Timer()
    if block:
        print(f"{text}...")
    else:
        print(f"{text}...", end=' ')
    sys.stdout.flush()
    yield
    if block:
        print(f"{text}: {timer}")
    else:
        print(timer)
    sys.stdout.flush()


@contextlib.contextmanager
def measuring_memory(text, block=False):
    mem = MemoryMeasurement()
    if block:
        print(f"{text}...")
    else:
        print(f"{text}...", end=' ')
    sys.stdout.flush()
    yield
    if block:
        print(f"{text}: {mem}")
    else:
        print(mem)
    sys.stdout.flush()


@contextlib.contextmanager
def profiling(text, block=False):
    # measures both time and memory
    timer = Timer()
    mem = MemoryMeasurement()
    if block:
        print(f"{text}...")
    else:
        print(f"{text}...", end=' ')
    sys.stdout.flush()
    yield
    if block:
        print(f"{text}: {timer}, {mem}")
    else:
        print(f"{timer}, {mem}")
    sys.stdout.flush()


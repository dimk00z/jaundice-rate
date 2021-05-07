from time import monotonic
from contextlib import contextmanager


class Timer:
    def __init__(self, start) -> None:
        self.start = start
        self.end = None

    @property
    def timer_result(self):
        if self.end is not None:
            return self.end - self.start


@contextmanager
def timer():
    processing_start_time = monotonic()
    process_timer = Timer(processing_start_time)
    try:
        yield process_timer
    finally:
        process_timer.end = monotonic()

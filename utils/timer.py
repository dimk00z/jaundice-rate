from time import monotonic
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass
class Timer:
    start: float
    end: float = 0

    @property
    def duration(self):
        if self.end:
            return self.end - self.start


@ contextmanager
def elapsed_timer():
    processing_start_time = monotonic()
    process_timer = Timer(processing_start_time)
    try:
        yield process_timer
    finally:
        process_timer.end = monotonic()

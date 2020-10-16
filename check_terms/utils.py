import logging

from collections import defaultdict
import time


class ProgressTracker:
    def __init__(self, *fields):
        self.fields = fields[::]
        self.counters = defaultdict(int)
        self.prev_counters = {}
        self.start = time.time()
        self.next_time = 0.0
        self.message(force=True)

    def increment(self, field_name, value=1):
        assert field_name in self.fields
        self.counters[field_name] += value

    def end(self):
        self.message(force=True)

    def message(self, force=False):
        if (force and self.prev_counters != self.counters) or (time.time() >= self.next_time):
            now = time.time()
            self.next_time = now + 1.0
            seconds = now - self.start
            stats = []
            for field_name in self.fields:
                total_val = self.counters.get(field_name, 0)
                prev_val = self.prev_counters.get(field_name, 0)
                ave_val = total_val / seconds
                delta_val = total_val - prev_val
                stats.append(f"{field_name} - total: {total_val:6} ave/second: {ave_val:6.1f} delta: {delta_val:4}")

            msg = f"Secs: {seconds:6.1f} - {'; '.join(stats)}"
            logging.info(msg)
            self.prev_counters = self.counters.copy()


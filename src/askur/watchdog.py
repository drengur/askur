import psutil
import os
import threading
import time


class Watchdog:
    def __init__(self, threshold: int = 5, interval: int = 3):
        self.threshold: float = threshold * 0.01  # Convert percentage to fraction
        self.interval: int = interval
        self.thread: threading.Thread | None = None
        self._text_label: str = ""
        self.running: bool = True
        self.print_statusbar = False
        self.start()

    def monitor_system_memory(self):
        while self.running:
            mem = psutil.virtual_memory()
            available_percent = mem.available / mem.total

            if available_percent < self.threshold:
                print(
                    f"Available memory is below {self.threshold * 100}%. Exiting gracefully."
                )
                self.stop()
                os._exit(1)
            if self.print_statusbar:
                print(
                    f"{self.memory_status['label'] + (',' + self._text_label if self._text_label else '')}",
                    end="\r",
                )
            time.sleep(self.interval)

        self.thread = None  # Clean up the thread reference when stopping
        self.clear_label()  # Clear the label when stopping

    @property
    def memory_status(self) -> dict:
        mem = psutil.virtual_memory()

        total_length = 24  # Length of the label bar
        total_used = (int(mem.percent) * total_length) // 100
        total_available = total_length - total_used
        mem_total_gb = mem.total / (1024 * 1024 * 1024)
        label = f"{mem.percent}% [{'*' * (total_used)}{'_' * (total_available)}]{mem_total_gb:.2f}GB"

        return {
            "total": f"{mem.total / (1024 * 1024):.0f}MB",  # in MB
            "available": f"{mem.available / (1024 * 1024):.0f}MB",  # in MB
            "used": f"{mem.used / (1024 * 1024):.0f}MB",  # in MB
            "free": f"{mem.free / (1024 * 1024):.0f}MB",  # in MB
            "percent": f"{mem.percent}%",
            "label": label,
        }

    def print_label(self, label: str = "Memory Status", end: str = "\r") -> None:
        self._text_label = label

    def clear_label(self) -> None:
        self._text_label = ""
        print(" " * 100, end="\r")

    def start(self, statusbar=False):
        self.clear_label()
        self.print_statusbar = statusbar
        self.thread = threading.Thread(target=self.monitor_system_memory)
        self.thread.daemon = True
        self.running = True
        self.thread.start()

    def stop(self):
        self.running = False
        self.clear_label()


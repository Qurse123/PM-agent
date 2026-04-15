"""
Entrypoint for the arq worker.

arq 0.27.0 calls asyncio.get_event_loop() at Worker.__init__ time, which
raises RuntimeError on Python 3.12+ when no loop exists yet. Setting one
explicitly before arq imports resolve the issue.
"""
import asyncio
from typing import cast

asyncio.set_event_loop(asyncio.new_event_loop())

from arq import run_worker  # noqa: E402
from arq.typing import WorkerSettingsType  # noqa: E402
from app.core.worker import WorkerSettings  # noqa: E402

if __name__ == "__main__":
    run_worker(cast(WorkerSettingsType, WorkerSettings))

"""Arka plan işleri (export, önizleme) ve ilerleme takibi."""
from __future__ import annotations

import threading
import time
import traceback
import uuid


class Job:
    def __init__(self, kind: str, label: str):
        self.id = uuid.uuid4().hex[:10]
        self.kind = kind
        self.label = label
        self.progress = 0.0
        self.message = ""
        self.done = False
        self.error: str | None = None
        self.result = None
        self.cancel = threading.Event()
        self.started = time.time()

    def to_dict(self):
        return {"id": self.id, "kind": self.kind, "label": self.label, "progress": self.progress,
                "message": self.message, "done": self.done, "error": self.error,
                "result": self.result, "elapsed": round(time.time() - self.started, 1)}


class JobManager:
    def __init__(self):
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()

    def start(self, kind: str, label: str, fn) -> Job:
        """fn(job) arka planda çalışır; dönüş değeri job.result olur."""
        job = Job(kind, label)
        with self.lock:
            self.jobs[job.id] = job
            # eski bitmiş işleri temizle
            for jid in [j.id for j in self.jobs.values() if j.done and time.time() - j.started > 3600]:
                self.jobs.pop(jid, None)

        def run():
            try:
                job.result = fn(job)
                job.progress = 1.0
            except Exception as e:  # noqa: BLE001
                job.error = str(e) if job.cancel.is_set() else f"{e}\n{traceback.format_exc(limit=4)}"
            finally:
                job.done = True

        threading.Thread(target=run, daemon=True).start()
        return job

    def get(self, jid: str) -> Job | None:
        return self.jobs.get(jid)

    def active(self, kind: str | None = None) -> list[Job]:
        return [j for j in self.jobs.values() if not j.done and (kind is None or j.kind == kind)]

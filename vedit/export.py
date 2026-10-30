"""Export: kareleri paralel render edip FFmpeg ile kodlar. Önizleme videosu da buradan üretilir."""
from __future__ import annotations

import concurrent.futures as cf
import multiprocessing as mp
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from . import model
from .audio import collect_events, render_audio
from .render import Renderer
from .util import NO_WINDOW, ffmpeg_exe, run_ffmpeg

H264 = ["-c:v", "libx264", "-pix_fmt", "yuv420p"]

PROFILES: dict[str, dict] = {
    "default": {"label": "MP4 — proje ayarları", "ext": ".mp4",
                "video": H264 + ["-preset", "medium", "-crf", "18"],
                "audio": ["-c:a", "aac", "-b:a", "192k"]},
    "youtube": {"label": "YouTube 1080p (16:9)", "ext": ".mp4", "size": (1920, 1080),
                "video": H264 + ["-preset", "medium", "-crf", "17"],
                "audio": ["-c:a", "aac", "-b:a", "256k"]},
    "youtube_4k": {"label": "YouTube 4K (16:9)", "ext": ".mp4", "size": (3840, 2160),
                   "video": H264 + ["-preset", "medium", "-crf", "18"],
                   "audio": ["-c:a", "aac", "-b:a", "256k"]},
    "shorts": {"label": "Shorts / Reels / TikTok (9:16)", "ext": ".mp4", "size": (1080, 1920),
               "video": H264 + ["-preset", "medium", "-crf", "18"],
               "audio": ["-c:a", "aac", "-b:a", "192k"]},
    "square": {"label": "Kare (1:1)", "ext": ".mp4", "size": (1080, 1080),
               "video": H264 + ["-preset", "medium", "-crf", "18"],
               "audio": ["-c:a", "aac", "-b:a", "192k"]},
    "portrait": {"label": "Instagram dikey (4:5)", "ext": ".mp4", "size": (1080, 1350),
                 "video": H264 + ["-preset", "medium", "-crf", "18"],
                 "audio": ["-c:a", "aac", "-b:a", "192k"]},
    "draft": {"label": "Taslak (hızlı, yarım çözünürlük)", "ext": ".mp4", "scale": 0.5,
              "video": H264 + ["-preset", "ultrafast", "-crf", "28"],
              "audio": ["-c:a", "aac", "-b:a", "128k"]},
    "prores": {"label": "ProRes 422 HQ (.mov, kurgu için)", "ext": ".mov",
               "video": ["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le"],
               "audio": ["-c:a", "pcm_s16le"]},
    "webm": {"label": "WebM (VP9)", "ext": ".webm",
             "video": ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "32", "-row-mt", "1",
                       "-deadline", "good", "-cpu-used", "4", "-pix_fmt", "yuv420p"],
             "audio": ["-c:a", "libopus", "-b:a", "128k"]},
    "gif": {"label": "GIF (540px, 15fps)", "ext": ".gif", "width": 540, "fps": 15,
            "video": H264 + ["-preset", "veryfast", "-crf", "12"], "audio": None},
}

PREVIEW_VIDEO = H264 + ["-preset", "ultrafast", "-crf", "26", "-g", "15", "-bf", "0"]


# ---------------------------------------------------------------------- yardımcılar


def _even(v: float) -> int:
    return max(2, int(round(v / 2)) * 2)


def plan_output(project: dict, profile: dict, comp_id=None):
    """→ (render_scale, render_w, render_h, out_w, out_h, fps)"""
    comp = model.get_comp(project, comp_id)
    W, H = model.comp_size(project, comp)
    fps = float(profile.get("fps") or project.get("fps", 30))
    if profile.get("size"):
        ow, oh = profile["size"]
        k = min(ow / W, oh / H)
    elif profile.get("width"):
        k = profile["width"] / W
        ow, oh = _even(W * k), _even(H * k)
    else:
        k = float(profile.get("scale", 1.0))
        ow, oh = _even(W * k), _even(H * k)
    rw, rh = _even(W * k), _even(H * k)
    return k, rw, rh, _even(ow), _even(oh), fps


def _frame_times(t0: float, t1: float, fps: float) -> list[float]:
    n = max(1, int(round((t1 - t0) * fps)))
    return [t0 + i / fps for i in range(n)]


def _encode_frames(project, base_dir, comp_id, times, scale, size, out_w, out_h, fps, vargs,
                   out_path, progress=None, cancel=None) -> None:
    rw, rh = size
    vf = []
    if (out_w, out_h) != (rw, rh):
        vf = ["-vf", f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:black"]
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{rw}x{rh}", "-r", f"{fps}", "-i", "-",
           *vf, *vargs, "-an", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE,
                            creationflags=NO_WINDOW)
    r = Renderer(project, base_dir, scale=scale)
    try:
        for t in times:
            if cancel is not None and cancel.is_set():
                break
            frame = r.render_rgb(t, comp_id)
            if frame.shape[1] != rw or frame.shape[0] != rh:
                from PIL import Image

                frame = __import__("numpy").asarray(
                    Image.fromarray(frame).resize((rw, rh), Image.BILINEAR))
            proc.stdin.write(frame.tobytes())  # type: ignore[union-attr]
            if progress is not None:
                progress(1)
    except BrokenPipeError:
        pass
    finally:
        r.close()
        try:
            proc.stdin.close()  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            pass
        err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
        proc.wait()
    if proc.returncode != 0 and not (cancel is not None and cancel.is_set()):
        raise RuntimeError("FFmpeg kodlama hatası: " + err[-1500:])


def _chunk_worker(args):
    (project, base_dir, comp_id, times, scale, size, out_w, out_h, fps, vargs, out_path,
     queue, cancel) = args

    def prog(n):
        if queue is not None:
            queue.put(n)

    _encode_frames(project, base_dir, comp_id, times, scale, size, out_w, out_h, fps, vargs,
                   out_path, prog, cancel)
    return out_path


def _concat(parts: list[str], out_path: str) -> None:
    if len(parts) == 1:
        shutil.move(parts[0], out_path)
        return
    lst = Path(out_path).with_suffix(".txt")
    lst.write_text("".join(f"file '{Path(p).as_posix()}'\n" for p in parts), encoding="utf-8")
    try:
        run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", out_path])
    finally:
        lst.unlink(missing_ok=True)


def default_workers() -> int:
    return max(1, min(8, (os.cpu_count() or 2) - 1))


# ---------------------------------------------------------------------- export


def export(project: dict, out_path: str, base_dir=None, profile: str | dict = "default",
           comp_id=None, t0: float = 0.0, t1: float | None = None, workers: int | None = None,
           progress=None, cancel: threading.Event | None = None) -> str:
    """Projeyi video dosyasına yazar. progress(oran 0..1, mesaj) çağrılır."""
    project = model.normalize(model.clone(project))
    prof = PROFILES[profile] if isinstance(profile, str) else profile
    comp = model.get_comp(project, comp_id)
    if t1 is None:
        t1 = model.comp_duration(comp)
    if t1 <= t0:
        raise ValueError("Süre 0: kompozisyonda içerik yok")
    scale, rw, rh, ow, oh, fps = plan_output(project, prof, comp_id)
    times = _frame_times(t0, t1, fps)
    total = len(times)
    workers = workers or default_workers()
    out_path = str(Path(out_path).with_suffix(prof["ext"]) if not Path(out_path).suffix
                   else Path(out_path))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="vedit_")
    started = time.time()
    done = [0]

    def report(msg=""):
        if progress:
            progress(min(1.0, done[0] / total * 0.95), msg)

    try:
        ext = ".mov" if prof["ext"] == ".mov" else ".webm" if prof["ext"] == ".webm" else ".mp4"
        n_chunks = 1 if total < 90 or workers == 1 else min(workers, max(1, total // 45))
        parts = []
        bounds = [round(i * total / n_chunks) for i in range(n_chunks + 1)]
        if n_chunks == 1:
            part = os.path.join(tmp, "part0" + ext)

            def prog(n):
                done[0] += n
                report(f"Kare {done[0]}/{total}")

            _encode_frames(project, base_dir, comp_id, times, scale, (rw, rh), ow, oh, fps,
                           prof["video"], part, prog, cancel)
            parts.append(part)
        else:
            mgr = mp.Manager()
            queue = mgr.Queue()
            mcancel = mgr.Event()
            jobs = []
            for i in range(n_chunks):
                part = os.path.join(tmp, f"part{i}{ext}")
                parts.append(part)
                jobs.append((project, base_dir, comp_id, times[bounds[i]:bounds[i + 1]], scale,
                             (rw, rh), ow, oh, fps, prof["video"], part, queue, mcancel))
            with cf.ProcessPoolExecutor(max_workers=n_chunks) as ex:
                futs = [ex.submit(_chunk_worker, j) for j in jobs]
                while not all(f.done() for f in futs):
                    if cancel is not None and cancel.is_set():
                        mcancel.set()
                    try:
                        while True:
                            done[0] += queue.get(timeout=0.2)
                    except Exception:  # noqa: BLE001 — kuyruk boş
                        pass
                    report(f"Kare {done[0]}/{total} ({n_chunks} çekirdek)")
                for f in futs:
                    f.result()
            mgr.shutdown()
        if cancel is not None and cancel.is_set():
            raise RuntimeError("İptal edildi")

        if progress:
            progress(0.96, "Birleştiriliyor")
        video_only = os.path.join(tmp, "video" + ext)
        _concat(parts, video_only)

        if prof["ext"] == ".gif":
            run_ffmpeg(["-i", video_only, "-vf",
                        "split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
                        "-loop", "0", out_path])
        else:
            wav = os.path.join(tmp, "audio.wav")
            has_audio = prof.get("audio") and render_audio(project, base_dir, wav, t0, t1, comp_id)
            if has_audio:
                extra = ["-movflags", "+faststart"] if prof["ext"] == ".mp4" else []
                run_ffmpeg(["-i", video_only, "-i", wav, "-map", "0:v", "-map", "1:a",
                            "-c:v", "copy", *prof["audio"], "-shortest", *extra, out_path])
            else:
                if prof["ext"] == ".mp4":
                    run_ffmpeg(["-i", video_only, "-c", "copy", "-movflags", "+faststart",
                                out_path])
                else:
                    shutil.move(video_only, out_path)
        if progress:
            progress(1.0, f"Bitti ({time.time() - started:.1f} sn)")
        return out_path
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------- önizleme videosu

CHUNK_SEC = 2.0


def _media_stamp(project, base_dir) -> list:
    from .util import resolve_path

    stamps = []
    for c in project["comps"].values():
        for layer in c["layers"]:
            for key in ("src", "script"):
                p = resolve_path(layer.get(key), base_dir)
                if p and os.path.exists(p):
                    stamps.append((p, os.path.getmtime(p)))
    if project.get("brand"):
        p = resolve_path(project["brand"], base_dir)
        if p and os.path.exists(p):
            stamps.append((p, os.path.getmtime(p)))
    return sorted(stamps)


def preview_chunks(project: dict, base_dir, comp_id=None, scale=0.4) -> list[dict]:
    """Önizleme parçalarının listesi: [{index, t0, t1, key}]"""
    comp = model.get_comp(project, comp_id)
    dur = model.comp_duration(comp)
    fps = float(project.get("fps", 30))
    stamps = _media_stamp(project, base_dir)
    others = {cid: c for cid, c in project["comps"].items() if c is not comp}
    base = {k: project.get(k) for k in ("width", "height", "fps", "theme", "brand")}
    chunks = []
    n = max(1, int(-(-dur // CHUNK_SEC)))
    for i in range(n):
        t0 = i * CHUNK_SEC
        t1 = min(dur, t0 + CHUNK_SEC)
        layers = [l for l in comp["layers"] if l["start"] < t1 and l["start"] + l["duration"] > t0]
        key = model.content_hash([base, others, {k: v for k, v in comp.items() if k != "layers"},
                                  layers, stamps, scale, t0, t1, fps, 2])
        chunks.append({"index": i, "t0": t0, "t1": t1, "key": key})
    return chunks


class PreviewBuilder:
    """Parça cache'li önizleme videosu. Sadece değişen 2 saniyelik parçalar yeniden render edilir."""

    def __init__(self, cache_dir: str, workers: int | None = None):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.workers = workers or default_workers()
        self._pool: cf.ProcessPoolExecutor | None = None
        self.lock = threading.Lock()

    def pool(self):
        if self._pool is None:
            self._pool = cf.ProcessPoolExecutor(max_workers=self.workers)
        return self._pool

    def status(self, project, base_dir, comp_id=None, scale=0.4) -> list[dict]:
        out = []
        for c in preview_chunks(project, base_dir, comp_id, scale):
            c["ready"] = (self.cache_dir / f"c_{c['key']}.mp4").exists()
            out.append(c)
        return out

    def build(self, project, base_dir, comp_id=None, scale=0.4, progress=None, cancel=None) -> str:
        project = model.normalize(model.clone(project))
        comp = model.get_comp(project, comp_id)
        dur = model.comp_duration(comp)
        fps = float(project.get("fps", 30))
        W, H = model.comp_size(project, comp)
        rw, rh = _even(W * scale), _even(H * scale)
        chunks = preview_chunks(project, base_dir, comp_id, scale)
        events = collect_events(project, base_dir, comp_id)
        final_key = model.content_hash([[c["key"] for c in chunks], events, dur])
        final = self.cache_dir / f"p_{final_key}.mp4"
        if final.exists():
            if progress:
                progress(1.0, "hazır")
            return str(final)
        todo = [c for c in chunks if not (self.cache_dir / f"c_{c['key']}.mp4").exists()]
        total = len(todo)
        futs = {}
        for c in todo:
            times = _frame_times(c["t0"], c["t1"], fps)
            out = str(self.cache_dir / f"c_{c['key']}.tmp.mp4")
            args = (project, base_dir, comp_id, times, scale, (rw, rh), rw, rh, fps,
                    PREVIEW_VIDEO, out, None, None)
            futs[self.pool().submit(_chunk_worker, args)] = c
        done = 0
        for f in cf.as_completed(futs):
            c = futs[f]
            if cancel is not None and cancel.is_set():
                for g in futs:
                    g.cancel()
                raise RuntimeError("İptal edildi")
            tmp = f.result()
            os.replace(tmp, self.cache_dir / f"c_{c['key']}.mp4")
            done += 1
            if progress:
                progress(done / max(1, total) * 0.9, f"Parça {done}/{total}")
        parts = [str(self.cache_dir / f"c_{c['key']}.mp4") for c in chunks]
        video = str(self.cache_dir / f"v_{final_key}.mp4")
        lst = self.cache_dir / f"l_{final_key}.txt"
        lst.write_text("".join(f"file '{Path(p).as_posix()}'\n" for p in parts), encoding="utf-8")
        run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", video])
        lst.unlink(missing_ok=True)
        wav = str(self.cache_dir / f"a_{final_key}.wav")
        if render_audio(project, base_dir, wav, 0, dur, comp_id):
            run_ffmpeg(["-i", video, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart",
                        str(final)])
            os.remove(wav)
            os.remove(video)
        else:
            os.replace(video, final)
        self._gc()
        if progress:
            progress(1.0, "hazır")
        return str(final)

    def _gc(self, keep=400):
        files = sorted(self.cache_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
        for p in files[:-keep]:
            p.unlink(missing_ok=True)

    def shutdown(self):
        if self._pool:
            self._pool.shutdown(cancel_futures=True)
            self._pool = None

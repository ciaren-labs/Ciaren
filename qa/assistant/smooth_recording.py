"""Capture actual Chromium paint events. FFmpeg resamples them on a 16 fps timeline."""

import base64
import shutil
import subprocess
from contextlib import contextmanager

from walkthrough_checks import require


class Cursor:
    def __init__(self, page):
        self.page = page
        self.x, self.y = 110, 160

    def caption(self, text):
        self.page.evaluate("text => document.getElementById('demo-caption').textContent = text", text)

    def point(self, locator):
        box = locator.bounding_box()
        if not box:
            return
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        for i in range(1, 9):
            t = i / 8
            ease = t * t * (3 - 2 * t)
            self.page.mouse.move(self.x + (x - self.x) * ease, self.y + (y - self.y) * ease)
            self.page.wait_for_timeout(20)
        self.x, self.y = x, y


@contextmanager
def recording(page, gif, work):
    ffmpeg = shutil.which("ffmpeg")
    require(ffmpeg, "Recording requires FFmpeg on PATH.")
    folder = work / "frames"
    folder.mkdir()
    page.evaluate("""() => {
      const cursor = document.createElement('div');
      cursor.id = 'demo-cursor';
      cursor.style.cssText = `position:fixed; top:0; left:0; z-index:2147483647; pointer-events:none;
        width:16px; height:16px; border:2px solid white; border-radius:50%; background:#7446df;
        box-shadow:0 0 0 4px #7044dd42; transform:translate(-40px,-40px)`;
      const caption = document.createElement('div');
      caption.id = 'demo-caption';
      caption.style.cssText = `position:fixed; bottom:9px; left:12px; z-index:2147483646; pointer-events:none;
        padding:8px 16px; border-radius:8px; background:#251c40; color:white; font:600 16px system-ui;
        box-shadow:0 2px 8px #22183a33`;
      document.body.append(cursor, caption);
      document.addEventListener('mousemove', e => {
        cursor.style.transform = 'translate(' + (e.clientX-8) + 'px,' + (e.clientY-8) + 'px)';
      });
    }""")
    session = page.context.new_cdp_session(page)
    timestamps = []

    def frame(event):
        path = folder / f"frame{len(timestamps):05}.png"
        path.write_bytes(base64.b64decode(event["data"]))
        timestamps.append(event["metadata"]["timestamp"])
        session.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]})

    session.on("Page.screencastFrame", frame)
    session.send("Page.startScreencast", {"format": "png", "everyNthFrame": 1})
    try:
        yield Cursor(page)
    finally:
        session.send("Page.stopScreencast")
        session.detach()
    # Keep real motion and compress pauses with no visual changes during fitting.
    require(timestamps, "Chromium captured no frames.")
    intervals = [min(2.0, max(0.015, b - a)) for a, b in zip(timestamps, timestamps[1:])]
    intervals.append(2.3)
    scale = min(1.0, 24.0 / sum(intervals))
    lines = []
    for i, duration in enumerate(intervals):
        lines.append(f"file frame{i:05}.png")
        lines.append(f"duration {duration * scale:.4f}")
    lines.append(f"file frame{len(timestamps) - 1:05}.png")
    (folder / "timeline.txt").write_text("\n".join(lines) + "\n")
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "1",
            "-i",
            "timeline.txt",
            "-filter_complex_threads",
            "1",
            "-filter_complex",
            "fps=16,scale=1040:-2:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
            "-loop",
            "0",
            str(gif.resolve()),
        ],
        cwd=folder,
        check=True,
        timeout=180,
    )

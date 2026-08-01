"""Teste direto do pipeline sem HTTP."""
import sys, threading, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import Settings, ensure_dirs
from app.core.cuda import register_cuda_paths
from app.services.pipeline.orchestrator import PipelineRunner
from app.services.project import ProjectStore

register_cuda_paths()
ensure_dirs()
settings = Settings.load()
# override para teste rápido
settings.export_quality = "fast"
settings.face_detection = False
settings.max_clips = 3

pid = "p_7ca3efb40c76"
project = ProjectStore.require(pid)
print("antes:", project.status)

runner = PipelineRunner(settings)
cancel = threading.Event()
thread = threading.Thread(target=runner.run, args=(pid, cancel), daemon=True)
thread.start()

t0 = time.time()
last_print = ""
while thread.is_alive() and time.time() - t0 < 1800:
    p = ProjectStore.require(pid)
    step = next((s for s in p.steps if s.status in ("running", "error")), None)
    if step:
        line = f"[{time.time()-t0:.0f}s] {step.id}: {step.progress:.0%} {step.detail} {step.status}"
        if line != last_print:
            print(line)
            last_print = line
    if p.status in ("ready", "error") and thread.is_alive():
        time.sleep(2)
        p = ProjectStore.require(pid)
        if p.status in ("ready", "error"):
            step_running = any(s.status == "running" for s in p.steps)
            if not step_running:
                break
    time.sleep(2)

thread.join(timeout=5)
p = ProjectStore.require(pid)
print("FINAL:", p.status, "|", p.error)
if p.status == "ready":
    print("clips:", p.clip_count)

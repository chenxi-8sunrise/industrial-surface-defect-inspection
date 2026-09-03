import os
import time
from pathlib import Path

from huggingface_hub import snapshot_download


ROOT = Path(__file__).resolve().parents[1]
DOWNLOAD_DIR = ROOT / "data" / "raw" / "mvtec_ad"

# The public mirror contains several hundred small files. A longer timeout and
# a conservative worker count make interrupted downloads reliably resumable.
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")

for attempt in range(1, 11):
    try:
        snapshot_download(
            repo_id="foersben/mvtec-ad",
            repo_type="dataset",
            revision="c75b396",
            local_dir=DOWNLOAD_DIR,
            allow_patterns=[
                "bottle/**",
                "tile/**",
                "transistor/**",
            ],
            max_workers=8,
        )
        break
    except Exception:
        if attempt == 10:
            raise
        print(f"download interrupted; resuming ({attempt}/10)")
        time.sleep(2)
print(DOWNLOAD_DIR)

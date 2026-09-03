import os
import hashlib
from pathlib import Path

import requests


torch_home = Path(__file__).resolve().parents[1] / ".cache" / "torch"
os.environ.setdefault("TORCH_HOME", str(torch_home))

checkpoint = torch_home / "hub" / "checkpoints" / "resnet18-f37072fd.pth"
if not checkpoint.exists():
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(
        "https://download.pytorch.org/models/resnet18-f37072fd.pth",
        timeout=120,
        verify=False,
    )
    response.raise_for_status()
    if hashlib.sha256(response.content).hexdigest()[:8] != "f37072fd":
        raise ValueError("ResNet18 checkpoint hash verification failed")
    checkpoint.write_bytes(response.content)

from torchvision.models import ResNet18_Weights, resnet18


resnet18(weights=ResNet18_Weights.DEFAULT)
print("ResNet18 backbone is ready")

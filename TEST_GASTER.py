import subprocess
from pathlib import Path
from utils import PathConfig
from utils import PathConfig

gaster = cfg.base_dir / "ipwndfu-win32/gaster.exe"
result = subprocess.run([str(gaster)], capture_output=True, text=True, cwd=str(gaster.parent))
print(result.stdout)
print(result.stderr)
print(f"Return code: {result.returncode}")

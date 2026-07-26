import subprocess
from pathlib import Path
from utils import PathConfig
from utils import PathConfig

ipwnder = cfg.base_dir / "ipwndfu-win32/ipwnder.exe"
result = subprocess.run([str(ipwnder), "-p"], capture_output=True, text=True, cwd=str(ipwnder.parent))
print(result.stdout)
print(result.stderr)
print(f"Return code: {result.returncode}")

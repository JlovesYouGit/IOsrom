import subprocess
from pathlib import Path
from utils import PathConfig
from utils import PathConfig
chargfast = cfg.chargfast_dir
result = subprocess.run([str(chargfast / "idevicerestore.exe"), "--help"], capture_output=True, text=True, cwd=str(chargfast))
print(result.stdout)
print(result.stderr)

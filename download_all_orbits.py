import subprocess
import glob

paths = glob.glob("/mnt/slc_data/path_*")

for path_dir in paths:
    print(f"▶ Downloading orbits for: {path_dir}")
    subprocess.run([
        "eof",
        "--search-path", path_dir,
        "--save-dir", "/mnt/orbits",
        "--force-asf"
    ])

#!/usr/bin/env python3

"""
run_isce2_batch.py

Author:
Date:

Description:
    Executes ISCE2 topsApp.py for each XML file generated per interferometric pair.
    Each run is isolated in its own sub-directory under --run_dir.

Usage:
    python run_isce2_batch.py --xml_root ./isce2_xmls --run_dir ./isce2_runs
"""

import os
import subprocess
from pathlib import Path
import argparse
from logger import log_script_arguments
from datetime import datetime

def run_isce(xml_file, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    cmd = f"cd {out_dir} && topsApp.py {xml_file}"
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode, result.stdout.decode(), result.stderr.decode()

def main():
    parser = argparse.ArgumentParser(description="Run ISCE2 topsApp.py for all XML files.")
    parser.add_argument('--xml_root', required=True, help='Root folder where XMLs are stored per path')
    parser.add_argument('--run_dir', required=True, help='Where to create working directories for each pair')
    args = parser.parse_args()

    script_name = Path(__file__).name
    arg_desc = {
        'xml_root': 'Directory containing topsApp.xml files in path folders',
        'run_dir': 'Directory to run each interferogram processing job'
    }
    log_script_arguments(script_name, vars(args), arg_desc)

    xml_files = list(Path(args.xml_root).rglob("*.xml"))
    print(f"[✓] Found {len(xml_files)} topsApp.xml files")

    for xml_path in xml_files:
        pair_name = xml_path.stem.replace('_topsApp', '')
        path_folder = xml_path.parent.name
        run_path = Path(args.run_dir) / path_folder / pair_name
        retcode, out, err = run_isce(str(xml_path.resolve()), str(run_path))

        if retcode == 0:
            print(f"[✓] ISCE2 ran successfully: {pair_name}")
        else:
            print(f"[!] Error for {pair_name}:\n{err}")

if __name__ == "__main__":
    main()

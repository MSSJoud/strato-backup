import pandas as pd
import subprocess
import time
from pathlib import Path
import random

# --- Config ---
csv_path = Path("/home/ubuntu/work/isce2_xmls/valid_pairs.csv")
orbit_dir = "/mnt/orbits"
slc_root = Path("/mnt/slc_data")
topsout_dir = Path("/home/ubuntu/work/topsout/test")
topsout_dir.mkdir(parents=True, exist_ok=True)

topsApp_xml = topsout_dir / "topsApp.xml"
ref_xml = topsout_dir / "reference.xml"
sec_xml = topsout_dir / "secondary.xml"

# --- Load and sample 3 random pairs ---
df = pd.read_csv(csv_path)
sampled = df.sample(n=3, random_state=42)

# --- XML builders ---
def write_topsApp():
    topsApp_xml.write_text(f"""<topsApp>
  <component name="topsinsar">
    <property name="Sensor name">SENTINEL1</property>
    <component name="reference">
        <catalog>reference.xml</catalog>
    </component>
    <component name="secondary">
        <catalog>secondary.xml</catalog>
    </component>
    <property name="swaths">[2]</property>
    <property name="range looks">7</property>
    <property name="azimuth looks">3</property>
    <property name="do unwrap">True</property>
    <property name="unwrapper name">snaphu_mcf</property>
    <property name="do denseoffsets">True</property>
  </component>
</topsApp>""")

def write_reference(safe_path):
    ref_xml.write_text(f"""<component name="reference">
  <property name="orbit directory">{orbit_dir}</property>
  <property name="output directory">reference</property>
  <property name="safe">['{safe_path}']</property>
</component>""")

def write_secondary(safe_path):
    sec_xml.write_text(f"""<component name="secondary">
  <property name="orbit directory">{orbit_dir}</property>
  <property name="output directory">secondary</property>
  <property name="safe">['{safe_path}']</property>
</component>""")

# --- Run loop ---
for _, row in sampled.iterrows():
    master = row["master"]
    slave = row["slave"]
    path_nr = row["path"]
    bperp = row["Bperp"]
    delta = row["delta_days"]

    print(f"\n▶ Testing pair from path {path_nr}")
    print(f"  MASTER: {master}")
    print(f"  SLAVE : {slave}")
    print(f"  Bperp : {bperp} m | delta_days: {delta}")

    slc_path = slc_root / f"path_{path_nr}"
    master_zip = slc_path / f"{master}.zip"
    slave_zip = slc_path / f"{slave}.zip"

    # Write XMLs
    write_reference(master_zip)
    write_secondary(slave_zip)
    write_topsApp()

    # Run topsApp with timing
    start = time.time()
    result = subprocess.run(["topsApp.py", "topsApp.xml"], cwd=topsout_dir)
    end = time.time()

    # Report
    if result.returncode == 0:
        print(f"✅ SUCCESS in {end - start:.2f} seconds")
    else:
        print("❌ FAILURE")

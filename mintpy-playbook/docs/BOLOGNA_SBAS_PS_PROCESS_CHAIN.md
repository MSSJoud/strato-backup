# Bologna SBAS vs PS Process Chain (Docker + ISCE2 + MintPy)

This document captures the full processing chain we executed for the Bologna 2023 SBAS/PS test, including run/verification commands, known issues, and recommended directory practices.

Use this file as a technical reference and operations log. For exact execution order, use [BOLOGNA_COOKBOOK_RUNBOOK.md](BOLOGNA_COOKBOOK_RUNBOOK.md).

## 1) Directory Policy (Data vs Workflow)

To keep responsibilities clean:

- **Data only** under `/mnt/data/...`
  - SLC zips, generated interferograms, MintPy inputs, ERA5 files, final products.
- **Workflow/code/docs** under `/home/ubuntu/work/mintpy-playbook/...`
  - Docker compose setup, scripts, and process documentation.

Recommended split:

- Data root: `/mnt/data/sbas_vs_ps_test_bologna/`
- Workflow root: `/home/ubuntu/work/mintpy-playbook/`
- Docs root: `/home/ubuntu/work/mintpy-playbook/docs/`

---

## 2) What Was Completed So Far

- SBAS + PS pair configs were generated from valid SLC pairs:
  - SBAS: 114 `topsApp.xml`
  - PS: 345 `topsApp.xml`
- A **single SBAS test pair** was run successfully in Docker.
- ISCE2 processing completed with no fatal runtime error.
- Produced test interferogram artifacts:
  - `merged/filt_topophase.unw.geo`
  - `merged/filt_topophase.flat.geo`
  - `merged/topophase.flat.geo`

---

## 3) Critical Behavior Observed (Important)

### Output location behavior

Running:

```bash
cd /home/ubuntu/work/isce2-playbook
docker compose run --rm isce2-insar topsApp.py /path/to/topsApp.xml
```

writes outputs in the **container working directory bind mount** (`/home/ubuntu/work/isce2-playbook`) unless explicitly isolated.

That means test outputs landed in:

- `/home/ubuntu/work/isce2-playbook/merged`
- `/home/ubuntu/work/isce2-playbook/geom_reference`

instead of under each pair directory.

### Implication

For batch mode, if we do not isolate per pair, runs can overwrite each other.

---

## 4) End-to-End Chain (Commands)

## 4.1 Pre-checks

```bash
cd /home/ubuntu/work/isce2-playbook

# Docker compose availability
docker compose version

# Optional: check no stale containers
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

## 4.2 Run one test pair (validation)

```bash
cd /home/ubuntu/work/isce2-playbook

docker compose run --rm isce2-insar topsApp.py \
  /mnt/data/sbas_vs_ps_test_bologna/configs/sbas/2023-01-04_2023-01-16/topsApp.xml
```

## 4.3 Live monitoring commands

```bash
# Running containers
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'

# Optional resource view
docker stats --no-stream 2>/dev/null || echo "No containers running"

# Check for generated products in test pair folder
find /mnt/data/sbas_vs_ps_test_bologna/configs/sbas/2023-01-04_2023-01-16 -type f \
  \( -name 'filt_topophase.unw.geo' -o -name '*_unw_phase.tif' -o -name '*.unw' -o -name '*.int' \) | head -n 50

# Check products in playbook working directory (where test outputs landed)
find /home/ubuntu/work/isce2-playbook -type f | grep -E \
  'filt_topophase\.flat\.geo$|filt_topophase\.unw\.geo$|topophase\.flat\.geo$' | head -n 50
```

## 4.4 Verify completion

```bash
# No running processing container means the one-off run ended
docker ps --format 'table {{.Names}}\t{{.Status}}'

# Confirm key outputs exist
ls -lh /home/ubuntu/work/isce2-playbook/merged/filt_topophase.unw.geo \
       /home/ubuntu/work/isce2-playbook/merged/filt_topophase.flat.geo \
       /home/ubuntu/work/isce2-playbook/merged/topophase.flat.geo
```

---

## 5) DEM and Orbit Notes (Need / Not Need)

## 5.1 DEM

- A DEM is required for TOPS geocoding and topographic phase handling.
- In this run, ISCE2 used auto DEM handling and processed successfully.
- Log evidence included DEM reads like:
  - `demLat_N42_N45_Lon_E008_E012.dem.wgs84.vrt`

### Common DEM issues

- Missing DEM coverage for AOI extent.
- Wrong DEM path/permissions in container.
- DEM tiles downloaded but not visible from mounted path.

### Quick DEM checks

```bash
find /home/ubuntu/work/isce2-playbook -maxdepth 2 -type f | grep -E 'demLat_.*\.dem\.wgs84(\.vrt)?$'
```

## 5.2 Orbit

- Accurate orbit information is required for robust baseline/geometry quality.
- In our test logs, orbit information was extracted and baseline computation succeeded.
- Earlier project phase also flagged orbit handling as a key issue and then resolved.

### Common orbit issues

- Orbit download failure due network/auth.
- Date mismatch between SLC acquisition and available orbit files.
- Orbit file exists but container cannot read mounted location.

### Orbit checks

```bash
# Check for orbit-related files/log content (project specific paths may vary)
find /mnt/data/sbas_vs_ps_test_bologna -type f | grep -Ei 'orbit|aux|EOF' | head -n 50
```

---

## 6) Safe Batch Strategy (Avoid overwrite)

For production SBAS/PS batch, run each pair in an isolated work directory and then copy/move outputs to data storage per pair.

At minimum, do not reuse one shared `merged/` folder across parallel jobs.

Recommended pattern:

- one working folder per pair
- outputs copied to `/mnt/data/sbas_vs_ps_test_bologna/outputs/{sbas|ps}/{pair_id}/...`

---

## 7) MintPy Stage and Atmospheric Correction

Yes: atmospheric correction should be applied in MintPy stage.

Current configs already include ERA5 weather-model correction:

- `/mnt/data/sbas_vs_ps_test_bologna/mintpy_config_sbas.cfg`
- `/mnt/data/sbas_vs_ps_test_bologna/mintpy_config_ps.cfg`

Key parameters already set:

- `mintpy.troposphericDelay.method = weatherModel`
- `mintpy.weatherModel.name = ERA5`
- `mintpy.weatherModel.dir = /mnt/data/sbas_vs_ps_test_bologna/era5`

But before MintPy:

1. Generate interferograms for the selected network.
2. Organize `mintpy_input/{sbas|ps}`.
3. Download ERA5 NetCDF files into `/mnt/data/sbas_vs_ps_test_bologna/era5`.

---

## 8) Current Status Snapshot

As of 2026-03-06 (current run window):

- Single-pair ISCE2 validation: ✅ done
- SBAS full batch: 🔄 running
- PS full batch: ⏸ pending
- MintPy inputs populated: ⏸ pending
- ERA5 directory populated: ⏸ pending
- MintPy runs (SBAS/PS): ⏸ pending

### Active Batch Runtime Log

- Script: `/home/ubuntu/work/run_isce2_subset_batch.sh`
- Live log symlink: `/mnt/data/sbas_vs_ps_test_bologna/logs/sbas_latest.log`
- Current container check:

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.RunningFor}}'
```

- Live tail:

```bash
tail -f /mnt/data/sbas_vs_ps_test_bologna/logs/sbas_latest.log
```

### Monitoring Command Record (Reusable)

```bash
# Latest logs
ls -lt /mnt/data/sbas_vs_ps_test_bologna/logs | head -n 10

# Active containers
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.RunningFor}}'

# Run counters from latest log
python3 - << 'PY'
import re, pathlib
log = pathlib.Path('/mnt/data/sbas_vs_ps_test_bologna/logs/sbas_latest.log')
text = log.read_text(errors='ignore') if log.exists() else ''
print('START', len(re.findall(r'\] START ', text)))
print('DONE ', len(re.findall(r'\] DONE ', text)))
print('FAIL ', len(re.findall(r'\] FAIL ', text)))
print('SKIP ', len(re.findall(r'\] SKIP ', text)))
PY

# Last pair event
python3 - << 'PY'
import pathlib
log = pathlib.Path('/mnt/data/sbas_vs_ps_test_bologna/logs/sbas_latest.log')
for line in reversed(log.read_text(errors='ignore').splitlines()):
  if '] START ' in line or '] DONE ' in line or '] FAIL ' in line or '] SKIP ' in line:
    print(line)
    break
PY

# Produced outputs so far
find /mnt/data/sbas_vs_ps_test_bologna/configs/sbas -type f -name 'filt_topophase.unw.geo' | wc -l
find /mnt/data/sbas_vs_ps_test_bologna/configs/sbas -type f | grep -i dense | wc -l
```

### Scope + Pre-Estimation Table

Observed counts from current subset:

- SLC entries in subset safe/: 93 (symlinked ZIPs)
- Unique acquisition dates in pair network: 31
- SBAS pairs: 114
- PS pairs: 345

Runtime basis:

- Measured single-pair runtime from completed test: ~2.96 h
- Dense-offset + overhead planning factor: 1.25–1.5×
- Planned per-pair range: ~3.69–4.43 h

| Stack | Interferograms | SLC entries | Unique dates | Est. time @1 job | Est. time @2 jobs | Est. time @4 jobs |
|---|---:|---:|---:|---:|---:|---:|
| SBAS | 114 | 93 | 31 | 421–505 h | 211–253 h | 105–126 h |
| PS | 345 | 93 | 31 | 1275–1529 h | 637–765 h | 319–382 h |
| Total | 459 | 93 | 31 | 1696–2035 h | 848–1017 h | 424–509 h |

Storage planning (rule-of-thumb):

- If ~0.6 GB per pair output: SBAS ~68 GB, PS ~207 GB, total ~275 GB
- Dense-offset products can increase this footprint; budget extra headroom.

---

## 9) Next Actions

1. Keep SBAS running to completion and monitor failures/skips from `sbas_latest.log`.
2. Start PS batch after confirming SBAS output layout and disk growth behavior.
3. Prepare MintPy input tree from successful outputs.
4. Download ERA5 files.
5. Run MintPy SBAS and PS.
6. Compare SBAS vs PS deformation outputs.

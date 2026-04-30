# Bologna Subset Cookbook Runbook (Exact Repro Steps)

This is the execution-first runbook. Follow steps in order to reproduce the Bologna SBAS/PS workflow from subset SLCs to MintPy outputs.

## 0) Scope and Paths

- Data root: `/mnt/data/sbas_vs_ps_test_bologna`
- ISCE2 workflow root: `/home/ubuntu/work/isce2-playbook`
- MintPy workflow root: `/home/ubuntu/work/mintpy-playbook`
- Batch runner script: `/home/ubuntu/work/run_isce2_subset_batch.sh`

Assumption: Docker is installed and running.

---

## A) One-Command Launch Modes (Fresh vs Resume)

Use these shortcuts depending on whether you want a clean rerun or to resume from existing outputs.

### A1) Fresh start (clean logs, rerun all pairs, dense required)

```bash
# SBAS fresh run
REQUIRE_DENSE=1 /home/ubuntu/work/run_isce2_subset_batch.sh sbas

# PS fresh run (start after SBAS or in separate window)
REQUIRE_DENSE=1 /home/ubuntu/work/run_isce2_subset_batch.sh ps
```

### A2) Resume mode (recommended after interruptions)

`run_isce2_subset_batch.sh` already resumes by skipping completed pairs.

- If `REQUIRE_DENSE=1`, it skips only pairs that have unwrapped output **and** dense products.
- If a pair has `filt_topophase.unw.geo` but no dense outputs, it is rerun automatically.

```bash
# Resume SBAS from current state
REQUIRE_DENSE=1 /home/ubuntu/work/run_isce2_subset_batch.sh sbas

# Resume PS from current state
REQUIRE_DENSE=1 /home/ubuntu/work/run_isce2_subset_batch.sh ps
```

### A3) Quick pre-launch status check

```bash
ls -lt /mnt/data/sbas_vs_ps_test_bologna/logs | head -n 10
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.RunningFor}}'
```

### A4) Live watch after launch

```bash
tail -f /mnt/data/sbas_vs_ps_test_bologna/logs/sbas_latest.log
# or
tail -f /mnt/data/sbas_vs_ps_test_bologna/logs/ps_latest.log
```

---

## 1) Verify subset inputs

```bash
# SLC subset (symlinked zip entries)
ls -1 /mnt/data/sbas_vs_ps_test_bologna/data/safe | wc -l

# Pair lists
wc -l /mnt/data/sbas_vs_ps_test_bologna/configs/sbas/valid_pairs.csv
wc -l /mnt/data/sbas_vs_ps_test_bologna/configs/ps/valid_pairs.csv
```

Expected currently:
- ~93 SLC entries
- SBAS 114 pairs (+ header)
- PS 345 pairs (+ header)

---

## 2) Regenerate topsApp configs (dense offsets enabled)

```bash
python3 /home/ubuntu/work/generate_isce2_configs_from_csv.py \
  --csv /mnt/data/sbas_vs_ps_test_bologna/configs/sbas/valid_pairs.csv \
  --data_path /mnt/data/sbas_vs_ps_test_bologna/data/safe \
  --output_dir /mnt/data/sbas_vs_ps_test_bologna/configs/sbas

python3 /home/ubuntu/work/generate_isce2_configs_from_csv.py \
  --csv /mnt/data/sbas_vs_ps_test_bologna/configs/ps/valid_pairs.csv \
  --data_path /mnt/data/sbas_vs_ps_test_bologna/data/safe \
  --output_dir /mnt/data/sbas_vs_ps_test_bologna/configs/ps
```

Quick check:

```bash
grep -n "do dense offsets" /mnt/data/sbas_vs_ps_test_bologna/configs/sbas/2023-01-04_2023-01-16/topsApp.xml
```

---

## 3) Build ISCE2 container with dense-offset dependency

`gdal_translate` must exist inside `isce2-insar` for dense offset stage.

```bash
cd /home/ubuntu/work/isce2-playbook
docker compose build isce2-insar

docker compose run --rm isce2-insar bash -lc 'which gdal_translate && gdal_translate --version | head -n 1'
```

---

## 4) (Optional) single-pair validation

```bash
cd /home/ubuntu/work/isce2-playbook
docker compose run --rm \
  --workdir /mnt/data/sbas_vs_ps_test_bologna/configs/sbas/2023-01-04_2023-01-16 \
  isce2-insar topsApp.py /mnt/data/sbas_vs_ps_test_bologna/configs/sbas/2023-01-04_2023-01-16/topsApp.xml
```

Check outputs:

```bash
find /mnt/data/sbas_vs_ps_test_bologna/configs/sbas/2023-01-04_2023-01-16 -type f | \
  grep -E 'filt_topophase.unw.geo$|filt_topophase.flat.geo$|dense' | head -n 40
```

---

## 5) Run SBAS batch (all pairs)

```bash
REQUIRE_DENSE=1 /home/ubuntu/work/run_isce2_subset_batch.sh sbas
```

This writes logs to:
- `/mnt/data/sbas_vs_ps_test_bologna/logs/sbas_latest.log`

---

## 6) Monitor SBAS batch (copy/paste set)

```bash
# Live log
tail -f /mnt/data/sbas_vs_ps_test_bologna/logs/sbas_latest.log

# Active containers
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.RunningFor}}'

# Progress counters
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

# Produced outputs count
find /mnt/data/sbas_vs_ps_test_bologna/configs/sbas -type f -name 'filt_topophase.unw.geo' | wc -l
find /mnt/data/sbas_vs_ps_test_bologna/configs/sbas -type f | grep -i dense | wc -l
```

---

## 7) Run PS batch (after SBAS stabilization)

```bash
REQUIRE_DENSE=1 /home/ubuntu/work/run_isce2_subset_batch.sh ps
```

Monitor with the same commands using:
- `/mnt/data/sbas_vs_ps_test_bologna/logs/ps_latest.log` (if created by run)

---

## 8) Prepare MintPy stage inputs

After enough successful pairs:

1. Ensure ISCE2 outputs are organized under pair directories.
2. Populate:
   - `/mnt/data/sbas_vs_ps_test_bologna/mintpy_input/sbas`
   - `/mnt/data/sbas_vs_ps_test_bologna/mintpy_input/ps`
3. Ensure baseline/reference/geometry files are in expected MintPy paths.

---

## 9) Run MintPy (SBAS then PS)

```bash
cd /home/ubuntu/work/mintpy-playbook

# SBAS
docker compose run --rm \
  -e PROJECT_DIR=/mnt/data/sbas_vs_ps_test_bologna \
  -e STACK_TYPE=sbas \
  mintpy bash /workspace/scripts/02_run_pipeline.sh

# PS
docker compose run --rm \
  -e PROJECT_DIR=/mnt/data/sbas_vs_ps_test_bologna \
  -e STACK_TYPE=ps \
  mintpy bash /workspace/scripts/02_run_pipeline.sh
```

Optional post-analysis:

```bash
docker compose run --rm -e PROJECT_DIR=/mnt/data/sbas_vs_ps_test_bologna -e STACK_TYPE=sbas mintpy bash /workspace/scripts/03_post_analysis.sh
docker compose run --rm -e PROJECT_DIR=/mnt/data/sbas_vs_ps_test_bologna -e STACK_TYPE=ps mintpy bash /workspace/scripts/03_post_analysis.sh
```

---

## 10) Atmospheric correction checkpoint

MintPy configs already include ERA5 weather-model correction:
- `/mnt/data/sbas_vs_ps_test_bologna/mintpy_config_sbas.cfg`
- `/mnt/data/sbas_vs_ps_test_bologna/mintpy_config_ps.cfg`

Before final MintPy run, ensure ERA5 files exist under:
- `/mnt/data/sbas_vs_ps_test_bologna/era5`

---

## 11) Troubleshooting quick map

- Dense offset failure with `gdal_translate: not found`
  - Rebuild `isce2-insar` image (Step 3)
- Batch ends after first pair unexpectedly
  - Use `/home/ubuntu/work/run_isce2_subset_batch.sh` current version (stdin-safe)
- Interferogram exists but no dense outputs
  - Keep `REQUIRE_DENSE=1` and rerun pair/batch

- Repeated `Bad match at level 1` (or `e vector 1/2 error`) during dense offsets
  - This comes from the dense matching stage (Ampcor) when windows have weak correlation/texture.
  - It is often noisy but not immediately fatal by itself.
  - Check if run is still active:

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.RunningFor}}'
docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}'
grep -nEi 'Traceback|Exception|\] FAIL ' /mnt/data/sbas_vs_ps_test_bologna/logs/sbas_latest.log | tail -n 20
```

  - If your goal is MintPy time-series from unwrapped interferograms (not pixel-offset products), you can disable dense offsets for production pair generation.
  - If dense offsets are mandatory, continue and assess dense output quality per pair after completion.

---

## 12) Estimated runtime reference (current planning)

- Per pair with dense offsets: ~3.69–4.43 h
- SBAS (114):
  - 1 worker: ~421–505 h
  - 2 workers: ~211–253 h
  - 4 workers: ~105–126 h
- PS (345):
  - 1 worker: ~1275–1529 h
  - 2 workers: ~637–765 h
  - 4 workers: ~319–382 h

Use this runbook with the monitoring commands to track actual pace and revise estimates continuously.

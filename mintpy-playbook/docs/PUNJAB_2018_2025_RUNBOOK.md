# Punjab 2018-2025 LOS Time-Series Runbook

This is the practical runbook for generating a corrected Sentinel-1 LOS deformation
time series for Punjab using:

- `/home/ubuntu/work/isce2-playbook` for ISCE2 topsStack processing
- `/home/ubuntu/work/mintpy-playbook` for MintPy time-series inversion and corrections

## Scope

Target time span:

- start: `2018-01-01`
- end: `2025-12-31`

Important processing rule:

- process one Sentinel-1 stack per `direction + relative orbit + frame`
- do not mix ascending and descending scenes in the same ISCE2/MintPy stack
- do not try to run all of Punjab as one single `stackSentinel.py` project

## AOI Assumption

Local Punjab project artifacts currently expose two useful extents:

- current study bbox: `31.1222 31.7500 75.5972 76.8819`
- regional search bbox: `29.0 33.0 73.0 77.0`

The first is a small study subset already used in the local Punjab project.
The second is a coarse Punjab-region screening box from the local figure summary.

For Sentinel-1 scene discovery, use the regional search box first:

```text
S N W E = 29.0 33.0 73.0 77.0
```

For final reporting, clip or mosaic to your actual Punjab boundary polygon.

## 1. One-Time Setup

### 1.1 Data roots

Use these directories:

```bash
mkdir -p /mnt/data/punjab_2018_2025
mkdir -p /mnt/data/punjab_weather
mkdir -p /mnt/data/punjab_2018_2025/logs
```

### 1.2 Compose mounts

Both compose files now include:

- `/mnt/data/punjab_2018_2025:/mnt/data/punjab_2018_2025`
- `/mnt/data/punjab_weather:/mnt/data/punjab_weather`

Rebuild after changes:

```bash
cd /home/ubuntu/work/isce2-playbook
docker compose build isce2-insar stac-search

cd /home/ubuntu/work/mintpy-playbook
docker compose build
```

## 2. Organize the Sentinel-1 stacks

Create one project folder per track/frame/direction, for example:

```text
/mnt/data/punjab_2018_2025/
  desc_path070_frame1252/
  desc_path070_frame1253/
  asc_path143_frame0661/
```

Inside each stack:

```text
<stack_id>/
  SLC/
  Orbits/
  Aux/
  DEM/
```

## 3. Collect SLCs

The `stac-search` helper in `isce2-playbook` is currently demo-oriented and hardcoded
to a test bbox, so for Punjab you should assemble the scene list outside that helper
or adapt it first.

Selection rules:

- Sentinel-1 SLC only
- same direction per stack
- same relative orbit per stack
- same frame/swath footprint consistency per stack
- dates from `2018-01-01` through `2025-12-31`

Put the SLC ZIPs for each stack under:

```text
/mnt/data/punjab_2018_2025/<stack_id>/SLC/
```

## 4. Prepare DEM and auxiliary data

For each stack:

- place the DEM at `DEM/punjab.dem.wgs84`
- populate `Orbits/` with precise orbit files
- populate `Aux/` with required Sentinel-1 auxiliary data

Expected command-time DEM reference:

```text
./DEM/punjab.dem.wgs84
```

## 5. Generate the ISCE2 topsStack workflow

Enter the ISCE2 container:

```bash
cd /home/ubuntu/work/isce2-playbook
docker compose run --rm isce2-insar bash
```

Then, inside the container, go to one stack:

```bash
cd /mnt/data/punjab_2018_2025/<stack_id>
```

Generate the stack with an SBAS-style neighbor network:

```bash
stackSentinel.py \
  -s ./SLC \
  -o ./Orbits \
  -a ./Aux \
  -d ./DEM/punjab.dem.wgs84 \
  -b "29.0 33.0 73.0 77.0" \
  -C NESD \
  -c 2
```

Notes:

- `-c 2` is the right first pass for a long 2018-2025 stack
- if ESD overlap coherence is too strict, retry with `-e 0.7`

Example retry:

```bash
stackSentinel.py \
  -s ./SLC \
  -o ./Orbits \
  -a ./Aux \
  -d ./DEM/punjab.dem.wgs84 \
  -b "29.0 33.0 73.0 77.0" \
  -C NESD \
  -e 0.7 \
  -c 2
```

## 6. Execute the generated run files

`stackSentinel.py` only creates the workflow. It does not run the stack by itself.

Run the generated scripts in order:

```bash
cd run_files
chmod +x run_*
for f in run_*; do
  echo "RUNNING $f"
  ./$f
done 2>&1 | tee /mnt/data/punjab_2018_2025/logs/<stack_id>_topsStack.log
```

## 7. Verify MintPy-ready ISCE2 outputs

From the stack root:

```bash
ls reference/IW*.xml
ls baselines
ls merged/geom_reference/{hgt.rdr,lat.rdr,lon.rdr,los.rdr,shadowMask.rdr}
ls merged/interferograms/*/filt_*.unw | head
ls merged/interferograms/*/filt_*.cor | head
ls merged/interferograms/*/filt_*.unw.conncomp | head
```

If those products are missing, do not start MintPy yet.

## 8. Prepare the MintPy config

Template provided here:

- `/home/ubuntu/work/mintpy-playbook/configs/punjab_sbas_2018_2025.cfg`

Copy it into the stack root and replace `<stack_id>`:

```bash
cp /home/ubuntu/work/mintpy-playbook/configs/punjab_sbas_2018_2025.cfg \
  /mnt/data/punjab_2018_2025/<stack_id>/mintpy_config_sbas.cfg
```

Then edit:

- replace every `<stack_id>` with the actual stack folder name
- optionally set a manual `mintpy.reference.lalo` after a first QC run

## 9. Bootstrap MintPy through `correct_SET`

The local ERA5 helper reads acquisition dates from `timeseries_SET.h5`, so first run
MintPy through the `correct_SET` step.

```bash
cd /home/ubuntu/work/mintpy-playbook

docker compose run --rm mintpy bash -lc '
mkdir -p /mnt/data/punjab_2018_2025/<stack_id>/mintpy_work/sbas &&
cd /mnt/data/punjab_2018_2025/<stack_id>/mintpy_work/sbas &&
smallbaselineApp.py /mnt/data/punjab_2018_2025/<stack_id>/mintpy_config_sbas.cfg --dostep load_data &&
smallbaselineApp.py /mnt/data/punjab_2018_2025/<stack_id>/mintpy_config_sbas.cfg --dostep modify_network &&
smallbaselineApp.py /mnt/data/punjab_2018_2025/<stack_id>/mintpy_config_sbas.cfg --dostep reference_point &&
smallbaselineApp.py /mnt/data/punjab_2018_2025/<stack_id>/mintpy_config_sbas.cfg --dostep quick_overview &&
smallbaselineApp.py /mnt/data/punjab_2018_2025/<stack_id>/mintpy_config_sbas.cfg --dostep correct_unwrap_error &&
smallbaselineApp.py /mnt/data/punjab_2018_2025/<stack_id>/mintpy_config_sbas.cfg --dostep invert_network &&
smallbaselineApp.py /mnt/data/punjab_2018_2025/<stack_id>/mintpy_config_sbas.cfg --dostep correct_LOD &&
smallbaselineApp.py /mnt/data/punjab_2018_2025/<stack_id>/mintpy_config_sbas.cfg --dostep correct_SET
'
```

Expected output after this stage:

- `/mnt/data/punjab_2018_2025/<stack_id>/mintpy_work/sbas/timeseries_SET.h5`

## 10. Download ERA5 weather files for MintPy

Now run the helper:

```bash
cd /home/ubuntu/work/mintpy-playbook

python3 scripts/07_download_era5_for_mintpy.py \
  --timeseries /mnt/data/punjab_2018_2025/<stack_id>/mintpy_work/sbas/timeseries_SET.h5 \
  --weather-dir /mnt/data/punjab_weather \
  --hour 05 \
  --bbox 29,33,73,77
```

That is a dry run. Once the date list looks correct:

```bash
python3 scripts/07_download_era5_for_mintpy.py \
  --timeseries /mnt/data/punjab_2018_2025/<stack_id>/mintpy_work/sbas/timeseries_SET.h5 \
  --weather-dir /mnt/data/punjab_weather \
  --hour 05 \
  --bbox 29,33,73,77 \
  --download
```

This will populate:

- `/mnt/data/punjab_weather/ERA5/`

## 11. Run the full corrected MintPy pipeline

After ERA5 is present, run the standard pipeline wrapper:

```bash
cd /home/ubuntu/work/mintpy-playbook

docker compose run --rm \
  -e PROJECT_DIR=/mnt/data/punjab_2018_2025/<stack_id> \
  -e STACK_TYPE=sbas \
  -e TEMPLATE=/mnt/data/punjab_2018_2025/<stack_id>/mintpy_config_sbas.cfg \
  -e WORK_DIR=/mnt/data/punjab_2018_2025/<stack_id>/mintpy_work/sbas \
  mintpy bash /workspace/scripts/02_run_pipeline.sh
```

## 12. Run post-analysis products

```bash
docker compose run --rm \
  -e PROJECT_DIR=/mnt/data/punjab_2018_2025/<stack_id> \
  -e STACK_TYPE=sbas \
  -e WORK_DIR=/mnt/data/punjab_2018_2025/<stack_id>/mintpy_work/sbas \
  mintpy bash /workspace/scripts/03_post_analysis.sh
```

## 13. Key output files

Main working directory:

```text
/mnt/data/punjab_2018_2025/<stack_id>/mintpy_work/sbas/
```

Files to inspect first:

- `inputs/ifgramStack.h5`
- `inputs/geometryRadar.h5`
- `temporalCoherence.h5`
- `velocity.h5`
- `geo/`

Best corrected LOS time-series file will usually be one of:

- `timeseries_ERA5_ramp_demErr.h5`
- `timeseries_SET_ERA5_ramp_demErr.h5`

The exact filename depends on which correction stages were active in the run.

## 14. Repeat for all stacks

Repeat steps 2 through 12 for every:

- ascending stack needed for Punjab
- descending stack needed for Punjab
- separate frame/relative-orbit group

## 15. Mosaic and final delivery

After all stacks finish:

- mosaic geocoded LOS products by direction
- clip to the final Punjab polygon
- keep ascending and descending products separate unless you explicitly perform LOS decomposition

## 16. Practical first-pass recommendation

Start with one stack only, preferably:

- the densest descending stack over your main Punjab area of interest

Use it to validate:

- SLC compatibility
- DEM coverage
- run-file stability
- MintPy reference selection
- ERA5 correction behavior

Once that stack works end to end, clone the exact folder structure and repeat for the
remaining stacks.

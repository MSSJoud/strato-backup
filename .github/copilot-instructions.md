# InSAR Time-Series Analysis Workflow - AI Agent Guide

## Project Overview
This is an **InSAR (Interferometric Synthetic Aperture Radar) time-series analysis** workflow for ground deformation monitoring. The project processes Sentinel-1 SAR satellite data to detect surface displacement (subsidence, uplift, earthquakes, permafrost changes, etc.).

**Primary workflow**: Search → Download → Process → Analyze
- **Data sources**: ASF (Alaska Satellite Facility), NASA Earthdata (OPERA DISP-S1)
- **Processing tools**: HyP3 (on-demand InSAR), ISCE2 (topsStack), GMTSAR
- **Analysis**: MintPy (Miami INsar Time-series software in Python)

## Critical Architecture

### 1. Data Acquisition Pipeline
- **ASF Search** ([`ASFDataDownloader.py`](ASFDataDownloader.py), [`BulkDownloader.py`](BulkDownloader.py)): Query and download Sentinel-1 granules
- **Geographic tiling** ([`GeoTileMapper.py`](GeoTileMapper.py), [`area_tiler.py`](area_tiler.py)): Divide large AOIs into manageable tiles based on percentage of total area
- **Database management**: Both SQLite ([`granule_database.py`](granule_database.py)) and PostgreSQL ([`granule_psql_database.py`](granule_psql_database.py), [`select_s1_pairs_from_postgres.py`](select_s1_pairs_from_postgres.py))

### 2. InSAR Processing Workflows

**Three processing pathways**:
1. **HyP3 + MintPy** (most common - see [`hyp3_insar_stack_for_ts_analysis*.ipynb`](hyp3_insar_stack_for_ts_analysis.ipynb))
   - Request on-demand InSAR products from ASF HyP3 API
   - Download interferograms (unwrapped phase, coherence, DEMs)
   - Clip to common overlap using GDAL
   - Run MintPy SBAS time-series analysis

2. **ISCE2 stack processing** ([`insar_processing.ipynb`](insar_processing.ipynb), [`generate_topsApp_batch.py`](generate_topsApp_batch.py))
   - Generate XML config files for ISCE2's `topsStack` processor
   - Batch processing of SLC pairs from PostgreSQL database

3. **OPERA DISP-S1** ([`project_po/scripts/OPERA-DISP-S1_Landslides.ipynb`](project_po/scripts/OPERA-DISP-S1_Landslides.ipynb))
   - Direct download of NASA's processed displacement products via `opera-utils`
   - Uses "ministack" architecture (15 acquisitions per stack with fixed reference date)
   - **Critical**: Files must be opened with `engine='h5netcdf'` (NOT default `netcdf4`)
   - Spatial and temporal referencing required for proper analysis
   - Active development notebook - fully working workflow

### 3. Database Schema Pattern
When querying PostgreSQL databases for interferometric pairs:
- **Key fields**: `acquisition_date`, `path_number`, `orbit`, `granule_name`
- **Pair selection criteria**: max perpendicular baseline (`Bperp` ≤ 200m typically), max temporal baseline (`ΔT` ≤ 300 days)
- **Convention**: Database names like `aoi_3_slcs`, table name `slc_data`

## Essential Workflows

### Authentication
Always authenticate before downloads:
```python
from credentials import ASFUsr, ASFPwd  # Never commit credentials.py
session = asf.ASFSession().auth_with_creds(ASFUsr, ASFPwd)
```
Priority: Token → .netrc → credentials.py

### Running MintPy Time-Series Analysis
1. Prepare data with common overlap clipping (GDAL)
2. Create MintPy config ([`smallbaselineApp.cfg`](smallbaselineApp.cfg)):
   - Set `mintpy.load.processor = hyp3`
   - Define file patterns for `unwFile`, `corFile`, `demFile`, etc.
3. Run: `smallbaselineApp.py --dir <work_dir> <config_file>`
4. Key outputs: `timeseries.h5`, velocity maps, displacement time series

### Directory Organization Pattern
Downloaded data follows strict hierarchy:
```
output_dir/
├── tile_1/
│   ├── 2020/
│   │   ├── ascending/
│   │   │   ├── path_35/
│   │   │   │   ├── <granule>.zip
│   │   ├── descending/
│   │   │   ├── path_225/
```

## Code Conventions

### Conda Environments
- **`asf_env.yml`**: ASF search and downloads
- **`insar_env_full.yml`**: Full InSAR stack (includes MintPy, GDAL, HyP3 SDK)
- **`isce2_env*.yml`**: ISCE2 processing
- Activate before running: `conda activate <env_name>`

### Configuration Files
- [`config.py`](config.py): Central configuration (AOI, dates, credentials, paths)
  - Defines `postfix` for project naming (e.g., 'AOI-1-Togo-1')
  - Uses `Path` objects for all file paths
  - Creates directory structure automatically
- Never hardcode credentials - use [`credentials.py`](credentials.py) (gitignored)

### AOI Definition
- GeoJSON files: [`AOI-1.geojson`](AOI-1.geojson), [`AOI-2.geojson`](AOI-2.geojson)
- Converted to JSON: [`AOI-1.json`](AOI-1.json)
- Used in scripts as WKT strings for ASF search API

### Common Script Patterns
1. **Argparse for CLI**: All scripts use argparse with `--help` documentation
2. **Pandas for CSVs**: ASF search results always loaded as DataFrames
3. **Path objects**: Use `pathlib.Path`, not string paths
4. **Database queries**: Use parameterized queries (psycopg2), never string concatenation
5. **Error handling**: Scripts print errors but continue processing remaining items

## Key Integration Points

### HyP3 SDK → MintPy
```python
import hyp3_sdk as sdk
# Download products
products = hyp3.watch(batch)  # Polls until complete
products.download_files(download_dir)
# Extract and prepare
sdk.util.extract_zipped_product(zip_file)
# Clip to common overlap
overlap = get_common_overlap(dem_files)
clip_hyp3_products_to_common_overlap(data_dir, overlap)
```

### PostgreSQL → ISCE2 Batch
1. [`select_s1_pairs_from_postgres.py`](select_s1_pairs_from_postgres.py): Query pairs with baseline constraints
2. [`generate_topsApp_batch.py`](generate_topsApp_batch.py): Generate ISCE2 XML configs
3. Output: `topsApp.xml` files for each interferometric pair

### GDAL Processing
Files for MintPy must be clipped to common overlap:
```python
# Pattern: *_unw_phase.tif, *_corr.tif, *_dem.tif, *_lv_theta.tif, *_lv_phi.tif
gdal.Warp(output_file, input_file, 
          outputBounds=[ulx, lry, lrx, uly],
          dstNodata=0)
```

### OPERA DISP-S1 → Time Series Analysis
```python
from opera_utils.disp import _download
from disp_xr import product, stack as disp_stack

# Download cropped products
run_download(output_dir=Path(SUBSET_DIR), wkt=BBOX, frame_id=FRAME_ID, 
             start_datetime=start_dt, end_datetime=end_dt, num_workers=4)

# Load ministack structure
disp_df = product.get_disp_info(SUBSET_DIR)

# Combine ministacks into continuous time series (MUST use h5netcdf)
stack_prod = disp_stack.combine_disp_product(disp_df)

# Open individual files
ds = xr.open_dataset(file_path, engine='h5netcdf')  # Critical!
```

**OPERA-specific patterns**:
- Each ministack has a fixed reference date (first date in time coordinate)
- Displacement is cumulative from reference date
- Spatial referencing required: select stable point, subtract from all pixels
- Layers: `displacement`, `temporal_coherence`, `recommended_mask`, `connected_component_labels`
- Files organized by frame ID: `subset-ncs_F{FRAME_ID}/`

## Project-Specific Notes

### Active Areas of Investigation
- **Bologna subsidence study**: [`aoi_bologna/`](aoi_bologna/), [`aoi_3_02_Bologna/`](aoi_3_02_Bologna/) - Urban subsidence monitoring
- **Permafrost analysis**: [`MintPy_sbas_permafrost_Alaska.ipynb`](MintPy_sbas_permafrost_Alaska.ipynb) - Alaska permafrost deformation
- **Landslide monitoring**: [`project_po/scripts/`](project_po/scripts/) - OPERA DISP-S1 for slow-moving landslides (Boulder Creek, CA)
- **Groundwater-deformation coupling**: SWIN3D inversion research (ongoing)

### File Organization
- **Multiple AOIs**: Projects follow naming `AOI-[1-3]` with associated config files
- **Backup convention**: Files ending `_bkup*.ipynb` are notebook checkpoints - check most recent version without `_bkup` suffix
- **Test datasets**: Folders like [`slc_test_*_subset/`](slc_test_subset/) contain small test data for development
- **project_po/**: Active project directory with OPERA DISP-S1 and ISCE2 topsStack experiments

## Troubleshooting Patterns

1. **"No data in common overlap"**: Check if interferograms cover same geographic area
2. **PostgreSQL connection errors**: Verify `user='postgres', host='localhost'` in connection strings
3. **MintPy loading errors**: Ensure file patterns in config match actual filenames (wildcards)
4. **ASF download failures**: Session expires - re-authenticate with fresh token
5. **Memory issues**: MintPy config has `mintpy.compute.maxMemory = auto` and `numWorker = 64` - adjust for your system

## Common Commands

```bash
# Download granules from CSV
python ASFDataDownloader.py --input_csv granules.csv --output_dir ./data --tile_percentage 10

# Select interferometric pairs
python select_s1_pairs_from_postgres.py --db_name aoi_3_slcs --bmax 200 --tmax 300

# Process interferograms with date filter
python process_interferograms.py --db_name AOI_3_interferograms --start_date 20200101 --end_date 20201231

# Run MintPy time-series analysis
python ts_analysis_mintpy.py --data_dir ./interferograms --work_dir ./output --config_file mintpy_config.txt
```

## Advanced: SWIN3D Inversion for Groundwater Prediction

**Current Research Goal**: Invert InSAR land deformation to predict groundwater storage changes

### Architecture
- **Model**: Swin3D transformer network ([`swin_model_test_modified_2.ipynb`](swin_model_test_modified_2.ipynb))
- **Inputs**: 4-channel time series (InSAR displacement, Sd, Sg, S0) over T timesteps [B, C=4, T, H, W]
- **Output**: Predicted groundwater storage (Ŝg) for k future steps
- **Training data**: W3RA hydrological model outputs as ground truth

### Data Pipeline
1. **InSAR Time Series**: Load from MintPy HDF5 (`timeseries_ERA5_ramp_demErr.h5`)
   - Format: [time, y, x] → convert to [B, 1, T, H, W]
2. **W3RA Data**: Groundwater storage layers from NetCDF files
   - Variables: `uz_load_cm`, `uz_poro_cm`, `uz_total_cm`, etc.
   - Spatially aligned with InSAR grid
3. **Preprocessing** ([`ts_inspect_bkup_3.ipynb`](ts_inspect_bkup_3.ipynb)):
   - Load InSAR timeseries as xarray
   - Load W3RA NetCDF layers
   - Spatial/temporal alignment
   - Normalization and batching

### Key Integration Pattern
```python
# Load MintPy output
with h5py.File("timeseries_ERA5_ramp_demErr.h5", "r") as f:
    ts = f["timeseries"][:]  # [T, H, W]
    dates = f["date"][:]

# Load W3RA groundwater
ds = xr.open_dataset("W3RA_2010_2024.nc")
sg = ds['uz_total_cm']  # groundwater storage

# Prepare for SWIN3D
x_input = torch.stack([insar, sd, sg, s0], dim=1)  # [B, 4, T, H, W]
```

### Environment
- **Conda env**: `swin_env.yaml` - includes PyTorch, xarray, h5py
- **GPU required**: Model uses CUDA for training/inference

## When in Doubt
- **OPERA workflow**: Use [`OPERA-DISP-S1_Landslides.ipynb`](project_po/scripts/OPERA-DISP-S1_Landslides.ipynb) as reference - it's the most recent working notebook
- **Time series analysis**: Follow HyP3 → MintPy path for new AOIs (most straightforward)
- **Groundwater inversion**: Check [`ts_inspect_bkup_3.ipynb`](ts_inspect_bkup_3.ipynb) for data loading patterns
- Always test with small date ranges or subsets before full processing
- Reference [`config.py`](config.py) for expected directory structure and naming conventions

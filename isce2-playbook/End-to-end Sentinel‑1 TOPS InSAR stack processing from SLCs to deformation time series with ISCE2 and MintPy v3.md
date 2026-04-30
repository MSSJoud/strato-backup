# Where you choose PS vs SBAS in a Sentinel‑1 TOPS SLC → deformation → time‑series pipeline using ISCE2 topsStack and MintPy

## Executive summary

PS (Permanent Scatterers / PSI) and SBAS (Small Baseline Subset) are **not single “modes” you flip once** in an ISCE2→MintPy time‑series workflow. Instead, you choose PS vs SBAS (or a hybrid) at **multiple decision points**, mainly: **(a) interferogram network design**, **(b) pixel selection/masking**, **(c) inversion weighting + regularization**, and **(d) reference definition**. The rest of the pipeline—Sentinel‑1 TOPS burst handling, NESD/ESD coregistration, interferogram formation, unwrapping with connected components—must be done correctly for either approach. citeturn2view0turn7view1turn14view0turn9view0turn20view0turn5view0turn17view0turn16view0

In this ISCE2+MintPy context:

- **ISCE2 topsStack** is where you (i) run **TOPS‑correct coregistration** (geometry + NESD/ESD), and (ii) decide the *initial* interferogram pairing density via `stackSentinel.py -c` (nearest-neighbor vs “all pairs”). citeturn2view0turn7view1  
- **MintPy** is where you most explicitly implement **SBAS vs PS-like** behavior through:  
  - `mintpy.network.*` (baseline caps / neighbor caps / coherence‑based pruning + MST safeguards),  
  - `mintpy.network.maskFile` + custom masks (where PS-like pixel selection is practically implemented),  
  - `mintpy.networkInversion.*` (WLS weighting, min‑norm option, temporal coherence threshold), and  
  - `mintpy.reference.*` (reference pixel/date). citeturn9view0turn19view0turn18view0turn5view0turn16view0

Because AOI, number of dates, and landcover are **unspecified**, all suggested parameter values are **starting points**; you should tune them using coherence matrices/network QC.

## Pipeline stages and exactly where PS vs SBAS decisions happen

The table below lists the end‑to‑end stages commonly used with **ISCE2 topsStack/stackSentinel** + **MintPy smallbaselineApp**, and explicitly marks PS vs SBAS decision points.

### Decision map table

| Stage (chronological) | Tool | What happens | PS vs SBAS decision here? | How to implement SBAS here | How to implement PS/PS‑like here |
|---|---:|---|---|---|---|
| Input assembly | Outside tools | Collect SLCs, orbits, DEM, AOI, (optional) GNSS & tropo data | Indirect (method feasibility) | Favor dense acquisition cadence; SBAS needs many coherent short‑baseline pairs citeturn17view0turn16view0 | Favor scenes with strong point scatterers; PS relies on selecting coherent pixels by amplitude/phase stability citeturn5view0turn14view0 |
| Run‑file generation | ISCE2 | `stackSentinel.py` generates `configs/` and `run_files/` | No (workflow plumbing) | Use `-c` for limited connections; see below citeturn7view1 | Use `-c` denser (or “all”) only if compute allows; PS-like tends to tolerate longer baselines on PS pixels citeturn14view0turn16view0 |
| TOPS coregistration choice | ISCE2 | Choose `-C geometry` vs `-C NESD` and tune `-e`/`-O` | No (required for both) | Use default `-C NESD`; relax `-e` if overlap coherence is low citeturn2view0turn7view1 | Same as SBAS; TOPS coreg must be accurate regardless of PS/SBAS citeturn2view0turn7view1 |
| Interferometric pairing (initial network) | ISCE2 | `-c 2` nearest neighbors vs `-c all` all possible interferograms | **Yes (network philosophy)** | `-c` small (e.g., 2–5) approximates SBAS “short time” network developed by nearest neighbors citeturn7view1turn16view0turn17view0 | For PS‑like, you may keep more pairs (larger `-c` or `all`) to preserve star‑like or redundant networks, but be mindful of compute and unwrap robustness citeturn7view1turn14view0turn16view0 |
| Multilook & filtering before unwrap | ISCE2 | topsStack interferogram workflow multilooks/filters/unwrapps merged IFGs | **Yes (PS tends to preserve resolution)** | More multilooking improves SNR/coherence for distributed scatterers (SBAS typical) citeturn13search19turn17view0 | PS-like usually keeps fewer looks to preserve point targets; you can still multilook lightly for unwrapping stability (AOI unspecified) citeturn14view0turn5view0 |
| Unwrapping + connected components | ISCE2 + SNAPHU | Unwrap IFGs; generate conncomp masks | Method‑dependent in practice (PS can be less reliant on 2D unwrap in other toolchains) but **in this ISCE2→MintPy pipeline: required** | Use SNAPHU deformation mode (`-d`) and ensure conncomp output exists; MintPy expects conncomp for unwrap-error correction citeturn20view0turn9view0 | Same requirement for MintPy input; PS-like masking later will downweight pixels where unwrap is unreliable citeturn9view0turn18view0 |
| Export / file conventions | ISCE2 → MintPy | Ensure outputs are in ISCE2 topsStack directory structure MintPy expects | No (compatibility) | Same | Same |
| Load into MintPy | MintPy | `load_data` builds `ifgramStack.h5`, `geometryRadar.h5` | No (preparation) | Same | Same |
| Network refinement / pruning | MintPy | `modify_network` applies baseline thresholds, coherence thresholds, MST retention, mask/AOI | **Yes (core SBAS lever)** | Use `mintpy.network.tempBaseMax`, `perpBaseMax`, `connNumMax`, `coherenceBased=yes`, `minCoherence`, keep MST citeturn9view0turn19view0turn16view0 | Use PS mask to compute coherence only on PS candidates; possibly relax baseline caps; optionally use star network via reference file list citeturn9view0turn19view0turn16view0 |
| Reference in space/time | MintPy | Set `mintpy.reference.*` (common pixel; optional date) | **Yes (interpretation + stability)** | Choose stable area (non-deforming if possible) with good coherence; optionally use waterMask to exclude bad areas citeturn9view0turn11search15 | Choose a known PS pixel (from dispersion mask) and set reference selection mask accordingly citeturn5view0turn9view0turn11search15 |
| Time-series inversion (math + regularization) | MintPy | WLS inversion, min‑norm option, masking via temporal coherence | **Yes (inversion style)** | SBAS commonly corresponds to min‑norm solution and uniform weights; MintPy explicitly notes “SBAS = minNormVelocity yes + weightFunc no” citeturn9view0turn6view0turn17view0 | PS-like: prefer stronger weighting (`var` or `coh`) and apply a stricter temporal coherence mask to keep only stable pixels citeturn9view0turn5view0turn14view0 |
| Corrections (tropo, deramp, DEM residual) | MintPy | Apply troposphere correction, deramp, DEM error correction | Mostly shared (values differ) | Use `pyaps`/`height_correlation`/`gacos`; deramp suitable for localized deformation; DEM residual correction recommended in general citeturn9view0turn3search0turn19view0 | Same steps, but estimate ramps using PS mask to avoid DS noise; PS-like mask usually leads to cleaner ramp fitting citeturn9view0turn18view0turn11search14 |
| PS selection metric calculation | External + MintPy | Compute amplitude dispersion from SLC amplitude stack; use temporal coherence from MintPy | **Yes (this is PS definition)** | Not used (or used weakly) | Amplitude dispersion index \(D=\sigma_A/\mu_A\) and thresholding (typical ~0.25 in Ferretti 2001); then refine using MintPy temporal coherence threshold (e.g., ≥0.9) citeturn5view0turn9view0 |
| GNSS validation / tie-in | Post-processing | Compare time series at GNSS points; optionally align offset/trend | Method-agnostic | SBAS: validate velocities/time series at GNSS points | PS: same; PS points often coincide with GNSS monuments in urban areas if coherent (AOI/GNSS density unspecified) |

## Implementing PS vs SBAS decision points in ISCE2 topsStack

### What ISCE2 controls that affects PS vs SBAS

In topsStack, the start-to-finish interferogram workflow is created by `stackSentinel.py`, which generates `configs/` and `run_files/` (no processing until you execute the run scripts). citeturn2view0turn8view3

ISCE2’s **PS vs SBAS knobs are mostly about interferogram network density and output resolutions**, not about PS point identification itself (which typically happens later via masks/metrics). The key user-facing options you asked about are:

- `-c` determines how many interferometric connections are built. It explicitly supports “up to *k* nearest neighbor connections” (e.g., `-c 2`) and also `-c all` for all possible interferograms. citeturn7view1  
- `-C` controls TOPS coregistration: geometry-only vs geometry+NESD. NESD is default and recommended. citeturn2view0turn7view1  
- `-e` controls the ESD coherence threshold within NESD (default mentioned as 0.85; example relaxing to 0.7). citeturn7view1turn2view0  
- The **run_files** stage order and descriptions are documented (burst overlaps extraction, pair misregistration, time-series misreg, geo2rdr resampling, merging). citeturn8view3  

### ISCE2 “SBAS-style” vs “PS-like” pairing choices with `-c`

ISCE2 topsStack’s README gives two framing examples:

- **Sparse nearest-neighbor network**: “up to 2 nearest neighbor connections” via `-c 2`. This naturally biases toward **small temporal separations**, which aligns with the SBAS philosophy of using small-baseline interferograms to limit decorrelation. citeturn7view1turn17view0turn16view0  
- **All possible interferograms**: `-c all`. This yields a very dense network (compute-heavy), which may support redundancy but is often impractical for large stacks and can worsen unwrap failure rates if coherence is low. citeturn7view1turn9view0  

Command-level template (AOI unspecified):

```bash
# SBAS-leaning initial network (nearest neighbors)
stackSentinel.py -s ./SLC -o ./Orbits -a ./Aux -d ./DEM/dem.wgs84 \
  -b "<S N W E>" -C NESD -c 2
```

```bash
# PS-like / dense network (compute-heavy)
stackSentinel.py -s ./SLC -o ./Orbits -a ./Aux -d ./DEM/dem.wgs84 \
  -b "<S N W E>" -C NESD -c all
```

Both of these patterns are explicitly described in the topsStack README. citeturn7view1turn2view0

### TOPS coregistration (`-C`, `-e`) is not a PS vs SBAS choice

The README is explicit that coregistration can be “geometry only” or “geometry plus refined azimuth offsets through NESD,” and that NESD parameters include ESD coherence threshold (`-e`) and number of overlap interferograms (`-O`). This is necessary for TOPS time series and is method-agnostic (PS and SBAS both need correct TOPS coreg). citeturn2view0

Practical command-level knob (example from README):

```bash
# Relax ESD coherence threshold (if overlap ESD fails due to low coherence)
stackSentinel.py ... -W slc -C NESD -e 0.7
```

The example and default (0.85) are documented. citeturn7view1turn2view0

### Run-files matter for both PS and SBAS because they define the TOPS-correct stack

The core run stages that determine whether your interferograms are usable (burst overlap handling, NESD time-series misregistration, precise resampling, merge) are laid out in the README, including:

- `run_03_extract_burst_overlaps`  
- `run_05_pairs_misreg`  
- `run_06_timeseries_misreg` (least squares misregistration time series)  
- `run_07_geo2rdr_resample` (precise burst coregistration using geometry + misreg TS)  
- `run_09_merge` (merge bursts and merge geometry rasters) citeturn8view3turn7view1  

These are not PS vs SBAS switches, but without them TOPS interferograms will often fail later steps.

## Implementing SBAS vs PS-like behavior in MintPy

MintPy is where your workflow actually becomes “SBAS-like” or “PS-like,” mainly through:

1) **Network selection (pairs)**: baseline caps / neighbor caps / data-driven pruning + MST retention  
2) **Pixel selection**: coherence masks (SBAS) vs amplitude-dispersion + high temporal coherence masks (PS-like)  
3) **Inversion style**: weights (`weightFunc`) and regularization (`minNormVelocity`)  
4) **Reference choices**: reference pixel (space), reference date (time), and masking of reference selection

All of the keys below are defined and explained in MintPy’s default `smallbaselineApp.cfg`. citeturn9view0

### Network selection and pruning: where SBAS “really” happens in MintPy

MintPy supports baseline-domain thresholds and data-driven pruning:

- Baseline-domain caps:  
  - `mintpy.network.tempBaseMax` (max temporal baseline in days)  
  - `mintpy.network.perpBaseMax` (max perpendicular baseline in meters)  
  - `mintpy.network.connNumMax` (max neighbors per acquisition) citeturn9view0turn19view0  

- Data-driven pruning (coherence-based):  
  - `mintpy.network.coherenceBased = yes/no`  
  - `mintpy.network.minCoherence` (default 0.7)  
  - `mintpy.network.keepMinSpanTree` (default yes) citeturn9view0turn19view0  

- Mask + AOI for coherence calculation:  
  - `mintpy.network.maskFile` (defaults to `waterMask.h5` if present)  
  - `mintpy.network.aoiYX` / `mintpy.network.aoiLALO` citeturn9view0turn19view0  

The CLI equivalent (`modify_network.py`) exposes the same parameters, including `--max-tbase`, `--max-pbase`, `--max-conn-num`, `--coherence-based`, `--min-coherence`, `--mask`, and `--no-mst` overrides. citeturn19view0

### PS-like “star network” and how to do it in MintPy

A classical PS/PSI framing often uses a **single-master (“supermaster”)** stack and then identifies PS pixels from amplitude/phase stability. citeturn14view0turn5view0

MintPy can mimic the **star/single-reference acquisition** concept at the network stage via:

- `mintpy.network.referenceFile`, whose allowed values include `date12_list.txt` (a list of interferometric pairs). citeturn9view0turn19view0  
- MintPy’s supplemental documentation explicitly calls this the “star-like method” and notes it selects **N−1 interferograms with a single common reference acquisition**, citing Ferretti 2001. citeturn16view0turn5view0  

Practical recipe:

1) Create `date12_list.txt` containing only pairs `<refDate>_<otherDate>` (format depends on your stack naming; AOI unspecified).  
2) Set:

```cfg
mintpy.network.referenceFile = date12_list.txt
```

and/or apply it with:

```bash
modify_network.py inputs/ifgramStack.h5 -r date12_list.txt
```

The manpage documents that `--reference` accepts `date12_list.txt`. citeturn19view0turn9view0

### Pixel selection: coherence (SBAS) vs amplitude dispersion + temporal coherence (PS-like)

#### SBAS pixel selection in MintPy (distributed scatterers)

There are two common SBAS-style masks you’ll use:

- **Interferogram-level masking before inversion** via:  
  - `mintpy.networkInversion.maskDataset = coherence`  
  - `mintpy.networkInversion.maskThreshold` (default 0.4) citeturn9view0  
- **Temporal coherence mask after inversion** via:  
  - `mintpy.networkInversion.minTempCoh` (default 0.7) citeturn9view0  

MintPy also supports coherence-based network pruning itself (drop poor interferograms but keep MST). citeturn9view0turn19view0

#### PS-like pixel selection: amplitude dispersion preselection + high temporal coherence refinement

Ferretti et al. define the **amplitude dispersion index** as \(D=\sigma_A/\mu_A\) (standard deviation over mean of amplitude time series) and note PS candidates (PSC) can be selected by thresholding \(D\), with a **typical threshold ~0.25**. citeturn5view0

MintPy then provides the post-inversion “PS refinement” mechanism: **temporal coherence** thresholding (higher thresholds keep only very stable pixels). The default is 0.7, but PS-like filtering typically uses ≥0.9 as a starting point (AOI/landcover unspecified). The existence and role of `minTempCoh` are documented, including its reference to temporal coherence literature. citeturn9view0turn16view0

### Inversion and regularization: SBAS vs PS-like controls

MintPy’s `invert_network` step is documented in the default config:

- Weighting: `mintpy.networkInversion.weightFunc = var / fim / coh / no`  
- Min-norm option: `mintpy.networkInversion.minNormVelocity = yes/no`  
- Temporal coherence threshold: `mintpy.networkInversion.minTempCoh` citeturn9view0  

Crucially, MintPy states explicitly in its template:

> “SBAS (Berardino et al., 2002) = minNormVelocity (yes) + weightFunc (no)” citeturn9view0turn6view0turn17view0

That gives you an exact, command-level lever to implement SBAS-like inversion behavior in MintPy.

### Corrections: same steps, but different masking strategy for PS-like

MintPy includes (among others) the keys you requested:

- Troposphere correction: `mintpy.troposphericDelay.*` (methods include `height_correlation`, `pyaps`, `gacos`, `no`) citeturn9view0  
- Deramping: `mintpy.deramp.*` including `mintpy.deramp.maskFile` (auto uses `maskTempCoh.h5`) citeturn3search0turn9view0  
- DEM residual correction: `mintpy.topographicResidual.*` citeturn3search0turn9view0  

PS-like difference: you should produce and use a **PS candidate mask** (from amplitude dispersion) as:
- `mintpy.network.maskFile` (so coherence averaging for pruning is computed on PS-like pixels), and/or  
- `mintpy.reference.maskFile` (so reference selection avoids decorrelated pixels), and/or  
- `mintpy.deramp.maskFile` (so ramps are estimated from stable PS pixels). citeturn9view0turn19view0

## Exact example MintPy configs and PS-mask implementation

This section provides the “copy/paste” config snippets you asked for: one SBAS template and one PS-like template, plus where/how to compute amplitude dispersion and feed the mask into MintPy.

### SBAS MintPy config snippet (baseline caps + coherence pruning + SBAS inversion)

```cfg
########## 2. modify_network (SBAS)
mintpy.network.tempBaseMax       = 96          # days (AOI/landcover unspecified)
mintpy.network.perpBaseMax       = 150         # meters
mintpy.network.connNumMax        = 10

mintpy.network.coherenceBased    = yes
mintpy.network.minCoherence      = 0.70
mintpy.network.keepMinSpanTree   = yes
mintpy.network.maskFile          = waterMask.h5     # or "no" if none (optional)

########## 3. reference_point
mintpy.reference.lalo            = auto             # highly recommended to set manually
mintpy.reference.minCoherence    = 0.85

########## 5. invert_network (SBAS-style)
mintpy.networkInversion.minNormVelocity = yes
mintpy.networkInversion.weightFunc      = no        # MintPy explicitly maps this to SBAS (Berardino 2002)

mintpy.networkInversion.maskDataset     = coherence
mintpy.networkInversion.maskThreshold   = 0.40
mintpy.networkInversion.minTempCoh      = 0.70

########## 8/9/10. corrections (typical)
mintpy.troposphericDelay.method         = pyaps
mintpy.troposphericDelay.weatherModel   = ERA5       # if configured in your environment (unspecified)
mintpy.deramp                           = linear
mintpy.topographicResidual              = yes
```

All keys and meanings are defined in the default MintPy template; the SBAS mapping is stated verbatim. citeturn9view0

### PS-like MintPy config snippet (star network + PS mask + high temporal coherence)

This is *not* a full PSI implementation; it is the **PS-like** approach requested: **amplitude dispersion mask + high temporal coherence**, optionally with a **star network**.

```cfg
########## 2. modify_network (PS-like network)
mintpy.network.referenceFile      = date12_list.txt   # star network (optional)
mintpy.network.tempBaseMax        = no                # allow longer baselines (PS candidates may remain coherent)
mintpy.network.perpBaseMax        = no
mintpy.network.connNumMax         = no

mintpy.network.coherenceBased     = yes
mintpy.network.minCoherence       = 0.60              # start slightly lower if using PS mask for coherence averaging
mintpy.network.keepMinSpanTree    = yes
mintpy.network.maskFile           = psMask.h5         # <- your amplitude-dispersion PS mask

########## 3. reference_point (force reference among PS candidates)
mintpy.reference.lalo             = auto
mintpy.reference.maskFile         = psMask.h5
mintpy.reference.minCoherence     = 0.85

########## 5. invert_network (PS-like weighting)
mintpy.networkInversion.minNormVelocity = yes
mintpy.networkInversion.weightFunc      = var         # inverse covariance (recommended in template)
mintpy.networkInversion.minTempCoh      = 0.90        # stricter PS-like reliability mask

########## deramp and DEM correction estimated using PS pixels
mintpy.deramp                     = linear
mintpy.deramp.maskFile            = psMask.h5
mintpy.topographicResidual        = yes
```

Evidence for “star-like method” being PS-like is stated in MintPy supplemental documentation and Ferretti 2001, and MintPy supports star networks via a `date12_list.txt` reference list. citeturn16view0turn19view0turn5view0turn9view0

### How to compute amplitude dispersion (PS metric) and create `psMask.h5`

Ferretti et al. define amplitude dispersion \(D=\sigma_A/\mu_A\) on the amplitude time series per pixel and note that PS candidates can be selected by thresholding \(D\) with a typical threshold about 0.25. citeturn5view0

**Where to compute it in this pipeline**

Compute amplitude dispersion from the **coregistered SLC stack** produced by ISCE2 (topsStack produces a merged folder containing a `SLC` subdirectory with coregistered SLCs). citeturn7view1turn8view3

**Minimal practical procedure (conceptual)**

1) Read each coregistered complex SLC \(z_k(x,y)\) and compute amplitude \(A_k(x,y)=|z_k(x,y)|\).  
2) Compute per-pixel mean and standard deviation across time:  
   \[
   \mu_A(x,y)=\mathrm{mean}_k(A_k), \quad \sigma_A(x,y)=\mathrm{std}_k(A_k)
   \]  
3) Dispersion map: \(D(x,y)=\sigma_A/\mu_A\). citeturn5view0  
4) Define PS-candidate mask: `psMask = (D < 0.25)` (starting value; AOI/landcover unspecified). citeturn5view0  

**How to feed the mask into MintPy**

MintPy supports mask files at multiple stages (`mintpy.network.maskFile`, `mintpy.reference.maskFile`, etc.). citeturn9view0turn19view0  
Additionally, MintPy provides a universal masking utility:

```bash
mask.py velocity.h5 -m psMask.h5
mask.py timeseries.h5 -m psMask.h5
```

The manpage documents `mask.py -m MASK_FILE` and includes examples masking velocity and time series. citeturn18view0

**Mask file requirements (practical)**
- The MintPy maintainer guidance notes the mask and data must have the same size and masks are typically 2D boolean with 0 for masked pixels. citeturn11search14

## Command checklists to produce MintPy-ready outputs with ISCE2 for SBAS and PS-like paths

AOI bounds, number of SLCs, and compute resources are **unspecified**, so these checklists assume you will adjust `-b` and concurrency outside this minimal set.

### ISCE2 checklist for SBAS-style outputs (sparse neighbor network)

1) Generate run files for a small-neighbor network:

```bash
stackSentinel.py -s ./SLC -o ./Orbits -a ./Aux -d ./DEM/dem.wgs84 \
  -b "<S N W E>" -C NESD -c 2
```

ISCE2 documents this as “up to 2 nearest neighbor connections.” citeturn7view1

2) Execute run files in order (example pattern):

```bash
cd run_files
chmod +x run_*
./run_01_unpack_slc_topo_reference
./run_02_average_baseline
...
./run_09_merge
...
```

The workflow layout and `chmod +x` guidance are documented. citeturn2view0turn8view3

3) Verify MintPy-ready outputs exist:
- `merged/interferograms/*/filt_fine.unw`  
- `merged/interferograms/*/filt_fine.cor`  
- `merged/interferograms/*/filt_fine.unw.conncomp`  
- `merged/geom_reference/*` geometry rasters  
These paths are the canonical ISCE2 outputs MintPy expects for topsStack ingestion (through configuration templates). citeturn9view0turn19view0

### ISCE2 checklist for PS-like outputs (denser pairing + PS mask preparation)

1) Generate run files with more pairs (compute-heavy; use cautiously):

```bash
stackSentinel.py -s ./SLC -o ./Orbits -a ./Aux -d ./DEM/dem.wgs84 \
  -b "<S N W E>" -C NESD -c all
```

ISCE2 documents `-c all` as generating all possible interferograms. citeturn7view1

2) Run the stack (same as SBAS).

3) Compute amplitude dispersion from coregistered SLCs in the merged `SLC` directory and create `psMask.h5`.
- Dispersion definition and typical threshold are from Ferretti 2001. citeturn5view0  
- ISCE2 documents that merged outputs include a `SLC` directory with coregistered SLCs. citeturn7view1  

4) Use `psMask.h5` in MintPy network pruning / reference selection / deramp estimation as shown above. citeturn9view0

### If you need to run SNAPHU manually (deformation mode + conncomp + tiling)

If ISCE2 did not produce `*.unw.conncomp` for some reason, SNAPHU supports:

- deformation mode: `-d`  
- connected components mask output: `-g maskfile`  
- tile mode: `--tile ntilerow ntilecol rowovrlp colovrlp`  
- parallel tile unwrap: `--nproc n`  
- optional single-tile re-optimization: `-S` citeturn20view0

A command pattern (line length, file formats, and masks are **unspecified** and must match your raster):

```bash
snaphu -d wrapped.int <linelen> -c coherence.cor -o unwrapped.unw \
  -g unwrapped.unw.conncomp \
  --tile 3 4 30 30 --nproc 8 -S
```

SNAPHU’s manpage documents each of these options and also notes that for deformation interferograms, topography and flat-earth contributions should be removed before unwrapping. citeturn20view0

## Where PS vs SBAS choices are made and recommended starting parameters

### Summary table: where PS vs SBAS choices are made

| Decision point | SBAS choice | PS/PS-like choice | Where implemented |
|---|---|---|---|
| Interferogram network density | Small-baseline, multi-master network with short time/space baselines citeturn17view0turn16view0 | Single-master (star) or denser network tolerated on PS pixels citeturn14view0turn16view0turn5view0 | ISCE2 `-c` (coarse), MintPy `modify_network` / `referenceFile` (fine) citeturn7view1turn19view0turn9view0 |
| Pixel selection | DS pixels via coherence/temporal coherence masks citeturn14view0turn9view0 | PS candidates via amplitude dispersion threshold + high temporal coherence citeturn5view0turn9view0 | MintPy masks (`network.maskFile`, `reference.maskFile`, `mask.py`) citeturn9view0turn18view0 |
| Inversion weighting | Often min‑norm; uniform weights in classic SBAS framing citeturn9view0turn6view0 | Strong weighting (`var`/`coh`) + strict temporal coherence to focus on stable pixels citeturn9view0turn5view0 | MintPy `networkInversion.*` citeturn9view0 |
| Multilooking strategy | More looks to stabilize DS coherence and unwrapping citeturn13search19turn17view0 | Fewer looks to preserve point targets; still needs unwrap stability (AOI unspecified) citeturn14view0turn5view0 | ISCE2 run configs + MintPy `multilook.*` (if used) citeturn9view0turn7view1 |
| Reference pixel/date | Stable area (DS) with high coherence; often manual selection recommended citeturn9view0turn11search15 | Reference constrained to PS candidates (via mask), possibly near stable monument citeturn9view0turn5view0 | MintPy `mintpy.reference.*` citeturn9view0turn11search15 |

### Default starting parameter values for SBAS and PS-like

All values below are **starting points** because AOI/landcover/stack length are **unspecified**. When possible, they are anchored to published configurations or MintPy documentation.

#### SBAS starting values (network + inversion)

- `mintpy.network.tempBaseMax`: **50–120 days** (common SBAS thresholds)  
  - Example: 50 days and 150 m used in a Sentinel-1 time-series workflow description with SNAPHU unwrapping. citeturn13search19  
  - MintPy supplemental figure describes “small baseline” thresholds **120 days and 200 m** as an example. citeturn16view0  
- `mintpy.network.perpBaseMax`: **100–200 m** (start)  
  - Example: 100 days / 150 m used in an SBAS Sentinel‑1 application. citeturn13search12  
- `mintpy.network.connNumMax`: **5–10** to avoid over-dense networks (depends on stack length; unspecified) citeturn9view0turn19view0  
- `mintpy.network.coherenceBased`: `yes` and `mintpy.network.minCoherence`: **0.7** (MintPy default) citeturn9view0turn19view0  
- SBAS inversion mapping in MintPy:  
  - `mintpy.networkInversion.minNormVelocity = yes`  
  - `mintpy.networkInversion.weightFunc = no` citeturn9view0turn6view0  

Landcover sensitivity (heuristic, tied to sources):
- Vegetated areas decorrelate faster; MintPy supplemental examples include **hierarchical** small-baseline thresholds like `[6 days, 300 m; 12 days, 200 m; 48 days, 100 m; 96 days, 50 m]` as a structured way to densify the network while respecting decorrelation. citeturn16view0  

#### PS / PS-like starting values (masking + inversion)

- Amplitude dispersion PS candidate threshold: **\(D < 0.25\)** (typical threshold stated in Ferretti 2001) citeturn5view0  
- Temporal coherence refinement threshold: **`mintpy.networkInversion.minTempCoh = 0.90`** (starting point for PS-like strictness; MintPy default is 0.7) citeturn9view0  
- Coherence-based pruning threshold when using PS mask: `mintpy.network.minCoherence = 0.60–0.70` (start slightly lower if coherence averaging is computed only on PS candidates; AOI unspecified) citeturn9view0turn19view0  
- Weighting: `mintpy.networkInversion.weightFunc = var` (inverse covariance is labeled recommended in config) citeturn9view0  
- Network style: star-like network supported conceptually (MintPy supplement) and operationally (`date12_list.txt` reference file). citeturn16view0turn19view0  

Landcover sensitivity:
- In non-urban areas, coherent pixels are often distributed scatterers rather than PS; the PS vs DS conceptual separation and its implications are summarized in a Sentinel‑1 time‑series overview paper (PS in urban areas; DS in non-urban). citeturn14view0  
- For ice/fast-changing surfaces, shorter revisit improves coherence; Sentinel‑1 two-satellite repeat can be 6 days (mission description). citeturn12search13  

## Mermaid diagrams for SBAS flow, PS-like flow, and method choice

### SBAS flow (short-baseline network + DS coherence masking)

```mermaid
flowchart TD
  A[SLCs + Orbits + DEM + AOI (unspecified)] --> B[ISCE2 stackSentinel: -C NESD -c 2..5]
  B --> C[Coregister TOPS bursts (NESD/ESD)]
  C --> D[Generate IFGs (short neighbors), merge, multilook/filter]
  D --> E[SNAPHU unwrap + conncomp]
  E --> F[MintPy load_data]
  F --> G[MintPy modify_network: tempBaseMax/perpBaseMax + coherenceBased + MST]
  G --> H[MintPy invert_network: minNormVelocity=yes, weightFunc=no]
  H --> I[Corrections: troposphere/deramp/DEM residual]
  I --> J[Velocity + time series + DS masks]
```

### PS-like flow (amplitude dispersion mask + star/denser network + strict temporal coherence)

```mermaid
flowchart TD
  A[SLCs + Orbits + DEM + AOI (unspecified)] --> B[ISCE2 stackSentinel: -C NESD -c all or high -c]
  B --> C[Coregister TOPS bursts (NESD/ESD)]
  C --> D[Generate IFGs, unwrap + conncomp]
  D --> E[Compute amplitude dispersion D = std(A)/mean(A)\nfrom coregistered SLC amplitudes]
  E --> F[Create psMask: D < 0.25]
  F --> G[MintPy load_data]
  G --> H[MintPy modify_network with psMask + optional date12_list star network]
  H --> I[MintPy invert_network with weightFunc=var and minTempCoh≈0.9]
  I --> J[Corrections using psMask for ramp estimation]
  J --> K[PS-like time series & velocity (masked)]
```

### Decision flowchart: choosing SBAS vs PS-like (AOI unspecified)

```mermaid
flowchart LR
  A{Do you have dense, stable point scatterers?\n(urban/infrastructure/rocky)\nAOI unspecified} -->|Yes| B{Enough acquisitions?\n(>~20 recommended; unspecified)}
  A -->|No / mostly vegetation| C[Prefer SBAS/DS\n(short baselines + multilook)]
  B -->|Yes| D[PS-like (dispersion mask + high temp coherence)\noptionally star network]
  B -->|No| E[SBAS-like with conservative thresholds\nvalidate stability carefully]
  C --> F[Use baseline caps 50–120d, 100–200m\ncoherenceBased + MST]
  D --> G[Compute dispersion D; threshold ~0.25\nminTempCoh ~0.9]
```

## Primary sources used for this PS vs SBAS decision analysis

- ISCE2 topsStack README (stackSentinel options `-c`, `-C`, `-e`; run_files sequencing; nearest-neighbor vs all pairs). citeturn2view0turn7view1turn8view3  
- MintPy default `smallbaselineApp.cfg` (all requested keys; explicit mapping SBAS = minNormVelocity yes + weightFunc no; maskFile hooks; unwrap-error correction requiring conncomp). citeturn9view0  
- MintPy `modify_network` manpage (CLI options, `date12_list.txt` reference file support, coherence-based pruning defaults). citeturn19view0  
- MintPy `mask.py` manpage and maintainer guidance on mask requirements (how to apply PS masks to outputs). citeturn18view0turn11search14  
- Ferretti et al. (2001) PS paper: amplitude dispersion definition \(D=\sigma_A/\mu_A\) and typical PSC threshold ~0.25. citeturn5view0  
- Berardino et al. (2002) SBAS paper (accessible excerpt): SBAS based on combining differential interferograms from pairs with small orbital separation; uses SVD to link datasets and leverage spatiotemporal info to filter atmosphere. citeturn6view0  
- Lanari et al. (2004) SBAS extension paper: explicit statement that SBAS selects small-baseline pairs to limit spatial decorrelation and discusses full-resolution vs multilook datasets. citeturn17view0  
- MintPy supplemental (Yunjun 2019): illustrations of multiple pair-selection strategies (small baseline thresholds 120d/200m; star-like PS method; hierarchical baseline lists). citeturn16view0  
- SNAPHU manpage (deformation mode `-d`, conncomp `-g`, tiling `--tile`, parallel `--nproc`, `-S` re-optimization; notes about removing flat-earth/topography for deformation). citeturn20view0
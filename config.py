# /work/ISCE2/config.py

from pathlib import Path

# Configuration settings for procMdPairs.py

# General Settings
postfix = 'AOI-1-Togo-1'  # Wuhan, China
startYear = 201401  # start year filter
endYear = 201706  # end year filter
startFrame = None  # start frame filter
endFrame = None  # end frame filter

# Reference point and date for SBAS results
reference_yx = '723, 689'
reference_date = 'auto'

# ASF Data Center account details
ASFUsr = 'mehdi_joud'
ASFPwd = 'Eternity+1hapiness'

# Directory paths setup
cfgRoot = Path(__file__).parent  # Directory of config.py
auxRoot = cfgRoot / postfix  # Directory for auxiliary files
workplace = cfgRoot.parent / f'workplace_{postfix}'  # Main workplace directory

# Create directories if they do not exist
auxRoot.mkdir(exist_ok=True)
workplace.mkdir(exist_ok=True)

# File paths for initial and final pairs
fnInitPairs = cfgRoot / f'{postfix}_Init_pairs.csv'
fnFinalPairs = auxRoot / f'{postfix}_final_pairs.csv'
figPairs = auxRoot / f'{postfix}_final_pairs.png'

# Job name for ASF API, ensure it's less than 20 characters
jobName = f'SBAS_{postfix}'
if len(jobName) > 20:
    print('\033[1;31;40mError: length of jobName must be less than 20! \033[0m')
    exit(1)

# Paths for data management
savePath = cfgRoot.parent / 'S1AAdata' / postfix  # Downloaded data
unzipPath = workplace / 'S1AAunzip'  # Unzipped data (use SSD if possible)
clipPath = workplace / 'S1AAclip'  # Clipped data
mpyPath = workplace / 'Mintpy'  # Mintpy workplace

# Config files for Mintpy SBAS
cfgData = auxRoot / f"{jobName}_data.cfg"  # Data loading config file
cfgProc = auxRoot / f"{jobName}_proc.cfg"  # Data processing config file
shpFile = auxRoot / "AOI.shp"  # Shapefile for subarea cutting

# Create directories if they do not exist
savePath.mkdir(exist_ok=True)
unzipPath.mkdir(exist_ok=True)
clipPath.mkdir(exist_ok=True)
mpyPath.mkdir(exist_ok=True)

# AOI JSON file path (renamed to AOI-1.json)
aoi_json = cfgRoot / 'AOI-1.json'

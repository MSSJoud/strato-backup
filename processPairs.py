import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import matplotlib.dates as mdt
from datetime import date
import argparse
import json
from pathlib import Path
import importlib

# Function to get initial pairs
def getInitPairs(fileList, masterList, slaveList):
    pairs = set()
    for i in range(masterList.shape[0]):
        firstPair = np.where(fileList == masterList[i])[0]
        secondPair = np.where(fileList == slaveList[i])[0]
        if (firstPair.size != 0) and (secondPair.size != 0):
            tempPair = (firstPair[0], secondPair[0]) if firstPair[0] < secondPair[0] else (secondPair[0], firstPair[0])
            pairs.add(tempPair)
    return pairs

# Filter the image list according to the acquire year: [minyear, maxyear)
def yearFilter(fileList, minYear, maxYear):
    if not (isinstance(minYear, int) & (isinstance(maxYear, int))):
        print('yearFilter is skipped because the input range is not INT.')
        return fileList
    
    len1, len2 = len(str(minYear)), len(str(maxYear))
    if len1 != len2:
        print('yearFilter is skipped because len(minYear) != len(maxYear)')
        return fileList    
    
    accquireTime = np.array([int(x[17:(17+len1)]) for x in fileList])
    index = (minYear <= accquireTime) & (accquireTime < maxYear)
    return fileList[index]

# get frame ID for SIA images based on the ASF api: https://api.daac.asf.alaska.edu/services/search/param
def getFrame(inputList):       
    result = []    
    tempList = []
    metadata = asf.search(granule_list=inputList.tolist(),processingLevel='SLC')    
    print(len(metadata))
    for x in metadata:        
        tempList.append(x.properties['sceneName'])
        result.append(x.properties['frameNumber'])
    return np.array(tempList),np.array(result)

# Filter the image list according to the frame: [minFrame, maxFrame)
def frameFilter(inputList, minFrame, maxFrame):
    if isinstance(minFrame, int) & (isinstance(maxFrame, int)):
        newList,imgFrame = getFrame(inputList)
        index = (minFrame <= imgFrame) & (imgFrame < maxFrame)
        return newList[index]
    else:
        print('frameFilter is skipped because the input range is not INT.')
        return inputList

# Function to get plot X and Y
def getPlotXY(fileList, data):
    masterList = data[:,0]
    value = data[:,4]
    
    dates = np.zeros(fileList.shape, dtype=int)
    baseline = np.zeros(fileList.shape, dtype=int)

    for i, currFile in enumerate(fileList):
        tempDate = date(int(currFile[17:21]), int(currFile[21:23]), int(currFile[23:25]))
        dates[i] = mdt.date2num(tempDate)
        tempIdx = np.where(masterList == currFile)[0]
        if tempIdx.size != 0:
            baseline[i] = value[tempIdx[0]]

    return dates, baseline

# Parsing arguments
parser = argparse.ArgumentParser(description='Acquire some parameters for fusion restore')
parser.add_argument('-c', '--config', required=True, type=str, help='Configuration file in json format')
args = parser.parse_args()

# Importing configuration module
config_path = Path(args.config)
if not config_path.exists():
    print(f"Error: Configuration file {args.config} does not exist!")
    sys.exit(1)

spec = importlib.util.spec_from_file_location("config", config_path)
config = importlib.util.module_from_spec(spec)
sys.modules["config"] = config
spec.loader.exec_module(config)

# Path to the initial pairs CSV file
fnInitPairs = Path(config.CSVFILE)
if not fnInitPairs.exists():
    print('Error: csvFile does not exist!')
    sys.exit(1)

# Load initial pairs from CSV file
fileID = open(fnInitPairs, encoding='utf-8')
data = np.loadtxt(fileID, str, delimiter=',', skiprows=1)

masterList, slaveList = data[:,0], data[:,2]
fileList = np.unique(np.concatenate((masterList, slaveList)))

# Filter files
fileList = yearFilter(fileList, config.MINYEAR, config.MAXYEAR)
fileList = frameFilter(fileList, config.MINFRAME, config.MAXFRAME)

# Get initial pairs and plot
pairs = getInitPairs(fileList, masterList, slaveList)
plotDates, baseline = getPlotXY(fileList, data)

# Plotting the results
plt.figure(figsize=(12, 6))
plt.scatter(plotDates, baseline, color='blue')
for pair in pairs:
    plt.plot(plotDates[list(pair)], baseline[list(pair)], color='red')
plt.xlabel('Acquisition Date')
plt.ylabel('Baseline (m)')
plt.title('Initial Pairs')
plt.grid()
plt.show()

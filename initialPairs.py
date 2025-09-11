import json
import importlib.util
import asf_search as asf
import numpy as np
import pandas as pd
from pathlib import Path
import os

# Function to load AOI from JSON file
def load_aoi(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

# Function to perform ASF search based on AOI
def search_asf(aoi):
    results = asf.geo_search(
        intersectsWith=aoi['intersectsWith'],
        platform=asf.PLATFORM.SENTINEL1,
        start=aoi['start'],
        end=aoi['end']
    )
    return results

# Filter the image list according to the acquire year: [minyear, maxyear)
def yearFilter(fileList, minYear, maxYear):
    if not (isinstance(minYear, int) & (isinstance(maxYear, int))):
        print('yearFilter is skipped because the input range is not INT.')
        return fileList
    
    len1, len2 = len(str(minYear)), len(str(maxYear))
    if len1 != len2:
        print('yearFilter is skipped because len(minYear) != len(maxYear)')
        return fileList    
    
    accquireTime = np.array([int(x.properties['startTime'][:4]) for x in fileList])
    index = (minYear <= accquireTime) & (accquireTime < maxYear)
    return np.array(fileList)[index]

# get frame ID for SIA images based on the ASF api: https://api.daac.asf.alaska.edu/services/search/param
def getFrame(inputList):       
    result = []    
    tempList = []
    metadata = asf.search(granule_list=[x.properties['sceneName'] for x in inputList], processingLevel='SLC')    
    for x in metadata:        
        tempList.append(x.properties['sceneName'])
        result.append(x.properties['frameNumber'])
    return np.array(tempList), np.array(result)

# Filter the image list according to the frame: [minFrame, maxFrame)
def frameFilter(inputList, minFrame, maxFrame):
    if isinstance(minFrame, int) & (isinstance(maxFrame, int)):
        newList, imgFrame = getFrame(inputList)
        index = (minFrame <= imgFrame) & (imgFrame < maxFrame)
        return newList[index]
    else:
        print('frameFilter is skipped because the input range is not INT.')
        return inputList

# Function to get initial pairs
def getInitPairs(fileList, temporalBaselineMax=48):
    pairs = []
    for i in range(len(fileList)):
        for j in range(i + 1, len(fileList)):
            time_diff = (fileList[j].properties['startTime'] - fileList[i].properties['startTime']).days
            if abs(time_diff) <= temporalBaselineMax:
                pairs.append((fileList[i].properties['sceneName'], fileList[j].properties['sceneName']))
    return pairs

# Load AOI configurations
aoi_1 = load_aoi('/work/ISCE2/NileBasins/AOI-1.json')
aoi_2 = load_aoi('/work/ISCE2/NileBasins/AOI-2.json')

# Search ASF for both AOIs
results_aoi_1 = search_asf(aoi_1)
results_aoi_2 = search_asf(aoi_2)

# Print the results
print("Results for AOI-1:")
print(results_aoi_1)

print("Results for AOI-2:")
print(results_aoi_2)

# Applying Filters (example values for years and frames)
filtered_results_aoi_1 = yearFilter(results_aoi_

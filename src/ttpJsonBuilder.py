#!/usr/bin/env python
# coding: utf-8

# In[1]:

import sys
import pandas as pd
import json
import pathlib
from utils import stringToSeconds, secondsToString

if __name__=="__main__":
    if len(sys.argv) <= 1:
        raise RuntimeError("An excel input file must be specified in command line argument.")

    excelFileName = sys.argv[1]
    dataPath = pathlib.Path("../data/")
    inputExcelFilePath = dataPath / excelFileName
    xlSheetDfMap = pd.read_excel(inputExcelFilePath, sheet_name=None, engine='openpyxl')

    lineNodesDf = xlSheetDfMap["Stations"]
    station_df = lineNodesDf.query("Type=='station'")

    lineInfoDf = xlSheetDfMap["lineInfo"].set_index('Name')

    # In[7]:

    json_data = {}
    json_data["lineId"] = int(lineInfoDf.loc['lineId'].Value)
    json_data["lineName"] = str(lineInfoDf.loc['lineName'].Value)
    json_data["dayBeginTime"]  = str(lineInfoDf.loc['dayBeginTime'].Value)
    json_data["dayEndTime"]  = str(lineInfoDf.loc['dayEndTime'].Value)

    # In[8]:

    dayBeginTimeSeconds = stringToSeconds(json_data["dayBeginTime"])
    dayEndTimeSeconds = stringToSeconds(json_data["dayEndTime"])

    # In[9]:

    modelDemandObj = {}
    for timeSlot in range(dayBeginTimeSeconds+600, dayEndTimeSeconds, 600):
        timeSlotString = secondsToString(timeSlot)
        modelDemandObj[timeSlotString] = 0

    # In[11]:

    lineNodes = {}

    # In[12]:

    stationDemandDf = xlSheetDfMap["Demand"]

    # In[13]:

    stationDemandObjs = {}
    for stationId in stationDemandDf['StationId'].unique():
        stationDemandObjs[stationId] = modelDemandObj.copy()
        df = stationDemandDf.query("StationId == @stationId").copy()
        for index, row in df.iterrows():
            timeSlotString = str(row['Time'])
            stationDemandObjs[stationId][timeSlotString] = int(row['Demand'])

    # In[14]:

    stationDf = xlSheetDfMap["Stations"].query("Type == 'station'")

    # In[15]:

    stationObjs = []
    for index, row in stationDf.iterrows():
        stationObj = {}
        stationObj['id'] = int(row['StationId'])
        stationObj['name'] = row['StationName']
        stationObj['minDwellDuration'] = str(row['minDwellDuration'])
        stationObj['maxDwellDuration'] = str(row['maxDwellDuration'])
        if int(row['StationId']) in stationDemandObjs:
            demandObj = stationDemandObjs[int(row['StationId'])]
        else:
            demandObj = modelDemandObj.copy()
        stationObj['passengerDemand'] = demandObj
        stationObjs.append(stationObj)

    # In[16]:

    lineNodes['stations'] = stationObjs

    # In[17]:

    depotsDf = xlSheetDfMap["Depots"]

    # In[18]:

    routeSequenceDf = xlSheetDfMap["routeSequence"]
    depotRoutingSequenceObj = {}
    routingSequenceObj = {}
    for depotId in routeSequenceDf['DepotId'].unique():
        routeSequenceArray = []
        routeSeqPerDepotDf = routeSequenceDf.query('DepotId == @depotId').copy()
        routeSeqPerDepotDf.sort_values(['Sequence'], ascending=True, inplace=True)
        for index, row in routeSeqPerDepotDf.iterrows():
            routeSequenceArray.append(row['RouteId'])
        depotRoutingSequenceObj[depotId] = routeSequenceArray

    # In[19]:

    depotHeadwayObj = {}
    headwaySheetDf = xlSheetDfMap["headways"]
    for depotId in headwaySheetDf['DepotId'].unique():
        headwaysDf = headwaySheetDf.query('DepotId == @depotId')
        headwaySequenceArraysPerDepot = []
        timePeriodMinSizeSequenceArraysPerDepot = []
        timePeriodMaxSizeSequenceArraysPerDepot = []
        for depotConfigurationId in headwaysDf['DepotConfigurationId'].unique():
            headwaySequenceArray = []
            timePeriodMinSizeSequenceArray = []
            timePeriodMaxSizeSequenceArray = []
            headwaySeqPerDepotDf = headwaysDf.query('DepotConfigurationId == @depotConfigurationId').copy()
            headwaySeqPerDepotDf.sort_values(['Sequence'], ascending=True, inplace=True)
            for index, row in headwaySeqPerDepotDf.iterrows():
                headwaySequenceArray.append(str(row['Headway']))
                timePeriodMinSizeSequenceArray.append(str(row['timePeriodMinSize']))
                timePeriodMaxSizeSequenceArray.append(str(row['timePeriodMaxSize']))
            headwaySequenceArraysPerDepot.append(headwaySequenceArray)
            timePeriodMinSizeSequenceArraysPerDepot.append(timePeriodMinSizeSequenceArray)
            timePeriodMaxSizeSequenceArraysPerDepot.append(timePeriodMaxSizeSequenceArray)
        depotHeadwayObj[depotId] = {'headwaySequence' : headwaySequenceArraysPerDepot,
                                    'timePeriodMinSizes' : timePeriodMinSizeSequenceArraysPerDepot,
                                    'timePeriodMaxSizes' : timePeriodMaxSizeSequenceArraysPerDepot}

    if "timePeriods" in xlSheetDfMap:
        depotTimePeriodsObj = {}
        timePeriodSheetDf = xlSheetDfMap["timePeriods"]
        timePeriodSheetDf = timePeriodSheetDf[timePeriodSheetDf.filter(regex='^(?!Unnamed)').columns]
        for depotId in timePeriodSheetDf['DepotId'].unique():
            timePeriodsDf = timePeriodSheetDf.query('DepotId == @depotId')
            timePeriodSequenceArraysPerDepot = []
            plusOrMinusWindowArraysPerDepot = []
            for depotConfigurationId in timePeriodsDf['DepotConfigurationId'].unique():
                timePeriodSequenceArray = []
                plusOrMinusWindowArray = []
                timePeriodSeqPerDepotDf = timePeriodsDf.query('DepotConfigurationId == @depotConfigurationId').copy()
                timePeriodSeqPerDepotDf.sort_values(['Sequence'], ascending=True, inplace=True)
                for index, row in timePeriodSeqPerDepotDf.iterrows():
                    timePeriodSequenceArray.append(str(row['time']))
                    plusOrMinusWindowArray.append(str(row['PlusOrMinusWindow']))
                timePeriodSequenceArraysPerDepot.append(timePeriodSequenceArray)
                plusOrMinusWindowArraysPerDepot.append(plusOrMinusWindowArray)
            depotTimePeriodsObj[depotId] = {'timePeriodSequence' : timePeriodSequenceArraysPerDepot,
                                            'plusOrMinusWindows' : plusOrMinusWindowArraysPerDepot}

    # In[20]:

    depotObjs = []
    for index, row in depotsDf.iterrows():
        depotObj = {}
        depotObj['id'] = int(row['id'])
        depotObj['name'] = str(row['name'])
        depotObj['type'] = str(row['type']).lower()
        depotObj['stationedTrains'] = [int(x) for x in row['stationedTrains'].split(",")]
        depotObj['firstLaunchTime'] = str(row['firstLaunchTime'])
        depotObj['routingIdSequence'] = depotRoutingSequenceObj[depotObj['id']]
        depotObj['headwayConfigurations'] = depotHeadwayObj[depotObj['id']]
        depotObj['timePeriodConfigurations'] = depotTimePeriodsObj[depotObj['id']]
        depotObjs.append(depotObj)

    # In[21]:

    lineNodes['depots'] = depotObjs

    # In[22]:

    json_data["lineNodes"] = lineNodes

    # In[23]:

    lineSchemaDf = xlSheetDfMap["TravelTime"]

    # In[24]:

    objs = []
    for index, row in lineSchemaDf.iterrows():
        obj = {}
        obj['fromNode'] = int(row['From'])
        obj['toNode'] = int(row['To'])
        obj['travelDuration'] = str(row['TravelDuration'])
        objs.append(obj)

    # In[25]:

    json_data['lineScheme'] = objs
    # In[26]:

    routeInfoDf = xlSheetDfMap["routeInfo"]
    routesDf = xlSheetDfMap["routes"]

    # In[27]:

    routesArray = []
    for index, row in routeInfoDf.iterrows():
        routeObj = {}
        routeObj['id'] = int(row['RouteId'])
        routeId = routeObj['id']
        routeObj['name'] = str(row['RouteName'])
        routeObj['launchDepot'] = int(row['LaunchDepotId'])
        routeObj['circulatingDepot'] = int(row['CirculatingDepotId'])

        routeDf = routesDf.query('RouteId == @routeId').copy()
        routeDf.sort_values(['Sequence'], ascending=True, inplace=True)
        routeObj['nodeIdSequence'] = []
        routeObj['routeEndTurnAroundTime'] =  str(row['RouteEndTurnAroundTime'])
        for idx, routeRow in routeDf.iterrows():
            routeObj['nodeIdSequence'].append(int(routeRow['StationId']))
        routesArray.append(routeObj.copy())

    json_data['routes'] = routesArray


    # In[29]:

    # import SchemaBuilder from genson
    # builder = SchemaBuilder()
    # builder.add_object(json_data)
    # builder.to_schema()
    # generatedJsonSchema = builder.to_json(indent=2)

    # with open("TTPSchema.json", "w") as file:
    #     file.write(generatedJsonSchema)


    # In[30]:


    jsonOutputFileName = f"Line{json_data['lineId']}Problem.json"
    jsonOutputFilePath = dataPath / jsonOutputFileName

    # In[31]:

    with open(jsonOutputFilePath, "w") as file:
        file.write(json.dumps(json_data, indent=2))

    print(f"Output written to {jsonOutputFileName}.")


    # In[ ]:





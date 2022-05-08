from utils import secondsToString, stringToSeconds, atof, natural_keys, timeit, getFeasibleTimePeriods, argmin
from subway.simulation.utils import debugPrint
from subway.world import SubwayProblem
from subway.functions import getHeadwayFunction, smooth
import itertools
import json
from scipy.interpolate import interp1d
from itertools import accumulate
import copy


def getDepotClassFromType(depotType, subwayProblem):
    depotLikeClasses = [subwayProblem.Depot] + subwayProblem.Depot.__subclasses__()
    for depotClass in depotLikeClasses:
        debugPrint(depotClass.__name__)
        if depotType.lower() == depotClass.__name__.lower():
            return depotClass
    raise ProblemLoadingRuntimeError(f"Unknown Depot Type {depotType} in Json file.")


def getDepotLikeObj(objId, subwayProblem):
    depotLikeClasses = [subwayProblem.Depot] + subwayProblem.Depot.__subclasses__()
    depotObj = None
    for DepotClass in depotLikeClasses:
        try:
            depotObj = DepotClass[objId]
            debugPrint(f"{objId} is a {depotObj.__class__.__name__} object.")
            return depotObj
        except KeyError:
            continue
    if depotObj is None:
        raise ProblemLoadingRuntimeError("Given Object is Not OneOf <Depot, LaunchAndForgetDepot>")


def getDepotJsonObject(obj_id, jsonProblemObject):
    depotJsonObj = None
    for depot in jsonProblemObject['lineNodes']['depots']:
        if depot['id'] == obj_id:
            depotJsonObj = depot
            break
    if depotJsonObj == None:
        raise KeyError(f"Depot id {obj_id} not found in JSON Problem file.")
    return depotJsonObj


def loadTravelTimes(problemObj, subwayProblem):
    # Populate travelTime global dictionary
    travelTimes = {}
    for scheme in problemObj['lineScheme']:
        travelTimes[(scheme['fromNode'], scheme['toNode'])] = stringToSeconds(scheme['travelDuration'])
    subwayProblem.setTravelTimes((travelTimes))


def loadDepots(problemObj, subwayProblem):
    for depot in problemObj['lineNodes']['depots']:
        name = str(depot['name'])
        firstLaunchTimeSeconds = stringToSeconds(depot['firstLaunchTime'])
        assert firstLaunchTimeSeconds >= 0, \
            f"Depot {name}: First launch can't be before dayBeginTime." \
            f"dayBegin:{secondsToString(subwayProblem.dayBeginTimeSeconds)}; " \
            f"firstLaunch{depot['firstLaunchTime']} "
        depotId = int(depot['id'])
        depotType = str(depot['type'])
        debugPrint(f"Adding {depotType} id:{depotId}")
        # headwayMinutesSequence = depot['headwayConfigurationsInMinutes']
        # headwaySecondsSequence = tuple(int(x*60) for x in headwayMinutesSequence)

        # userHeadwayFunction = getHeadwayFunction(timePeriodSequence, headwaySecondsSequence, smooth(step=60))
        # print(f"Depot: {depot['id']} headways: {userHeadwayFunction.headways}")

        depotClass = getDepotClassFromType(depotType, subwayProblem)
        debugPrint(depotClass.__name__)
        depotClass(name,
                    firstLaunchTimeSeconds,
                    _id=depotId)


def loadHeadways(problemConfig, subwayProblem, timePeriodConfig):
    headwayConfig = problemConfig['headwayConfig']
    # timePeriodConfig = problemConfig['timePeriodConfig']
    headwayFunctions = {}
    for depotId, headwaySecondsSequence in headwayConfig.items():
        timePeriodSequence = timePeriodConfig[depotId]
        headwayFunction = getHeadwayFunction(timePeriodSequence,
                                             headwaySecondsSequence,
                                             smooth(step=60))
        headwayFunctions[depotId] = headwayFunction
        getDepotLikeObj(depotId, subwayProblem).setHeadwayFunction(headwayFunction)
        # print(f"Depot: {depotId} headways: {headwayFunction.headways}")
    return headwayFunctions


def loadStations(problemObj, subwayProblem):
    # Creating Station Objects
    # We form an cumDemand function and pass it to Station Object
    for station in problemObj['lineNodes']['stations']:
        timeSlots = list(map(stringToSeconds, station['passengerDemand'].keys()))
        cumDemands = list(accumulate(map(int, station['passengerDemand'].values())))
        timeSlots = [0] + timeSlots + [subwayProblem.dayEndTimeSeconds]
        cumDemands = [0] + cumDemands + [cumDemands[-1]]
        arrivalsFunction = interp1d(timeSlots, cumDemands)
        """
        # testing
        for timeSlot, cumDemand in zip(timeSlots, cumDemands):
            assert abs(arrivalsFunction(timeSlot) - cumDemand) <= 1e-3, f"timeSlot: {timeSlot}, \
                                        cumDemandFromInterp: {arrivalsFunction(timeSlot)}, \
                                        realCumDemand: {cumDemand}"
        """

        name = str(station['name'])
        minDwellSeconds = stringToSeconds(station['minDwellDuration'])
        stationId = int(station['id'])

        subwayProblem.Station(name,
                              arrivalsFunction,
                              minDwellSeconds,
                              _id=stationId)


def loadLineInfo(problemObj, subwayProblem):
    subwayProblem.lineId = int(problemObj['lineId'])
    subwayProblem.lineName = str(problemObj['lineName'])
    dayBeginTimeString = str(problemObj['dayBeginTime'])
    dayEndTimeString = str(problemObj['dayEndTime'])
    subwayProblem.dayBeginTimeSeconds = stringToSeconds(dayBeginTimeString)
    subwayProblem.dayEndTimeSeconds = stringToSeconds(dayEndTimeString)


def loadEnvironment(env, subwayProblem):
    depotClasses = [subwayProblem.Depot] + subwayProblem.Depot.__subclasses__()
    allSimulationClasses = depotClasses + [subwayProblem.Station,
                                           subwayProblem.Train]  # only the classes that can be bound with env
    for SimulationClass in allSimulationClasses:
        debugPrint(f"Binding {SimulationClass.__name__} instances with Simulation Environment.")
        for simulationClass_id, simulationClass in SimulationClass:
            simulationClass.setSimulationEnvironment(env)


def loadRouteSequences(problemObj, subwayProblem):
    # Create and add Train objects to all Depots
    # Set Routing Sequence to all Depots
    depotClasses = [subwayProblem.Depot] + subwayProblem.Depot.__subclasses__()
    for depotClass in depotClasses:
        for obj_id, obj in depotClass:
            depotObj = obj
            depotJsonObj = getDepotJsonObject(obj_id, problemObj)
            for trainId in depotJsonObj['stationedTrains']:
                subwayProblem.Train(f"Train #{trainId}", _id=trainId, depot=depotObj)
            routingObjectSequence = []
            for routeId in depotJsonObj['routingIdSequence']:
                routingObjectSequence.append(subwayProblem.Route[routeId])
            depotObj.setRouteSequence(routingObjectSequence)
    return depotClasses


def loadRoutes(problemObj, subwayProblem):
    # Create Route objects
    for route in problemObj['routes']:
        routeId = int(route['id'])
        routeName = str(route['name'])
        launchDepotId = int(route['launchDepot'])
        circulatingDepot = int(route['circulatingDepot'])
        nodeIdSequence = route['nodeIdSequence']
        turnAroundTime = stringToSeconds(route['routeEndTurnAroundTime'])

        launchDepotObj = getDepotLikeObj(launchDepotId, subwayProblem)
        circulatingDepotObj = getDepotLikeObj(circulatingDepot, subwayProblem)

        stationObjSequence = [subwayProblem.Station[nodeId] for nodeId in nodeIdSequence]
        subwayProblem.Route(routeName, stationObjSequence, launchDepotObj,
                            circulatingDepotObj, turnAroundTime, _id=routeId)


def headwayConfigGenerator(problemObj, subwayProblem):
    headwayConfigurations = {}
    depotClasses = [subwayProblem.Depot] + subwayProblem.Depot.__subclasses__()
    for depotClass in depotClasses:
        for obj_id, obj in depotClass:
            depotObj = obj
            depotJsonObj = getDepotJsonObject(obj_id, problemObj)
            headwayMinutesSequenceArray = depotJsonObj['headwayConfigurations']['headwaySequence']
            timePeriodMinSizesArray = depotJsonObj['headwayConfigurations']['timePeriodMinSizes']
            timePeriodMaxSizesArray = depotJsonObj['headwayConfigurations']['timePeriodMaxSizes']
            headwaySecondsSequenceArray = []
            timePeriodMinSizesSecondsArray = []
            timePeriodMaxSizesSecondsArray = []
            for headwaySequence, minSizes, maxSizes \
                    in zip(headwayMinutesSequenceArray,timePeriodMinSizesArray, timePeriodMaxSizesArray):
                headwaySecondsSequenceArray.append(tuple(map(stringToSeconds, headwaySequence)))
                timePeriodMinSizesSecondsArray.append(tuple(map(stringToSeconds, minSizes)))
                timePeriodMaxSizesSecondsArray.append(tuple(map(stringToSeconds, maxSizes)))
            debugPrint(depotObj, headwaySecondsSequenceArray)
            headwayConfigurations[obj_id] = {'headwaySequences':tuple(headwaySecondsSequenceArray),
                                             'timePeriodMinSizes':tuple(timePeriodMinSizesSecondsArray),
                                             'timePeriodMaxSizes':tuple(timePeriodMaxSizesSecondsArray)}
    depotIds = headwayConfigurations.keys()
    headConfigsPerDepot = headwayConfigurations

    # Just changing the structure so that we'll have
    # a config per Problem (ie, configs for all depots, as opposed to all configs for a depot)

    headwayConfigsPerProblem = makeInsideOutDict(headConfigsPerDepot)

    # further we need structure with one config per problem

    allHeadwayConfigs = itertools.product(*headwayConfigsPerProblem['headwaySequences'].values())
    alltimePeriodMinSizeConfigs = itertools.product(*headwayConfigsPerProblem['timePeriodMinSizes'].values())
    alltimePeriodMaxSizeConfigs = itertools.product(*headwayConfigsPerProblem['timePeriodMaxSizes'].values())

    problemConfigs = []

    for headwayConfig, periodMinSizes, periodMaxSizes \
            in zip(allHeadwayConfigs, alltimePeriodMinSizeConfigs, alltimePeriodMaxSizeConfigs):
        headwayConfigDict = dict(zip(depotIds, headwayConfig))
        periodMinSizesDict = dict(zip(depotIds, periodMinSizes))
        periodMaxSizesDict = dict(zip(depotIds, periodMaxSizes))
        problemConfigs.append({
            'headwayConfig': headwayConfigDict,
            'periodMinSizes': periodMinSizesDict,
            'periodMaxSizes': periodMaxSizesDict
        })

    for problemConfig in problemConfigs:
        yield problemConfig


def makeInsideOutDict(dictObj):
    """
    converts a given dict of
    structure {key : {key1:val1}} to {key1 : {key1 : {key:val1}}
    """
    reversedDict = {}
    for key, innerDictObj in dictObj.items():
        for innerKey, val in innerDictObj.items():
            if innerKey not in reversedDict:
                reversedDict[innerKey] = {}
            reversedDict[innerKey][key] = val
    return reversedDict


def timePeriodConfigGenerator(problemObj, subwayProblem):
    timePeriodConfigurations = {}
    depotClasses = [subwayProblem.Depot] + subwayProblem.Depot.__subclasses__()
    for depotClass in depotClasses:
        for obj_id, obj in depotClass:
            depotObj = obj
            depotJsonObj = getDepotJsonObject(obj_id, problemObj)
            timePeriodSequenceArray = depotJsonObj['timePeriodConfigurations']['timePeriodSequence']
            plusOrMinusWindowsArray = depotJsonObj['timePeriodConfigurations']['plusOrMinusWindows']
            timePeriodSecondsSequenceArray = []
            plusOrMinusWindowsSecondsArray = []
            for timePeriodSequence, plusOrMinusWindows in zip(timePeriodSequenceArray, plusOrMinusWindowsArray):
                timePeriodSequence = tuple(map(stringToSeconds, timePeriodSequence))
                plusOrMinusWindowsSeconds = tuple(map(stringToSeconds, plusOrMinusWindows))
                # timeIntervals = tuple(zip(timePeriodSequence[:-1], timePeriodSequence[1:]))
                timePeriodSecondsSequenceArray.append(timePeriodSequence)
                plusOrMinusWindowsSecondsArray.append(plusOrMinusWindowsSeconds)
            timePeriodConfigurations[obj_id] = {'timePeriodSequences' : timePeriodSecondsSequenceArray,
                                                'plusOrMinusWindows'  : plusOrMinusWindowsSecondsArray}
    depotIds = timePeriodConfigurations.keys()
    headwayConfigsPerProblem = makeInsideOutDict(timePeriodConfigurations)

    # further we need structure with one config per problem

    allTimePeriodConfigs = itertools.product(*headwayConfigsPerProblem['timePeriodSequences'].values())
    allPlusOrMinusWindows = itertools.product(*headwayConfigsPerProblem['plusOrMinusWindows'].values())

    # prettifier = lambda x: [list(map(secondsToString, y)) for y in x]

    problemConfigs = []

    for timePeriodConfig, plusOrMinusWindows in zip(allTimePeriodConfigs, allPlusOrMinusWindows):
        timePeriodConfigDict = dict(zip(depotIds, timePeriodConfig))
        plusOrMinusWindowsDict = dict(zip(depotIds, plusOrMinusWindows))
        problemConfigs.append({
            'timePeriodConfig': timePeriodConfigDict,
            'plusOrMinusWindows': plusOrMinusWindowsDict
        })

    for config in problemConfigs:
        yield config


def problemConfigGenerator(problemObj, subwayProblem):
    timePeriodConfigs = timePeriodConfigGenerator(problemObj, subwayProblem)
    headwayConfigs = headwayConfigGenerator(problemObj, subwayProblem)

    nestedGenerator =  itertools.product(timePeriodConfigs, headwayConfigs)

    for gen in nestedGenerator:
        timePeriodConfig, headwayConfig = gen
        problemConfig = headwayConfig.copy()
        problemConfig.update(timePeriodConfig)
        yield problemConfig


class ProblemLoadingRuntimeError(RuntimeError):
    """An error class to invoke when something goes wrong
        while loading objects into SubwayProblem
    """
    pass


class ProblemConfig(object):
    def __init__(self, problemConfigDict):
        self.timePeriodConfig = problemConfigDict['timePeriodConfig']
        self.plusOrMinusWindows = problemConfigDict['plusOrMinusWindows']
        self.headwayConfig = problemConfigDict['headwayConfig']
        self.periodMinSizes = problemConfigDict['periodMinSizes']
        self.periodMaxSizes = problemConfigDict['periodMaxSizes']
    def __str__(self):
        timePeriodString = "timePeriodConfig"
        for depotId, timePeriods in self.timePeriodConfig.items():
            timePeriodString += "\n"
            timePeriodString += f"    {depotId}: {list(map(secondsToString, timePeriods))}"
        return timePeriodString


def createSubwayProblemFromJson(problemObj):
    subwayProblem = SubwayProblem()

    debugPrint(problemObj.keys())

    loadLineInfo(problemObj, subwayProblem)
    loadStations(problemObj, subwayProblem)
    loadDepots(problemObj, subwayProblem)

    loadTravelTimes(problemObj, subwayProblem)
    loadRoutes(problemObj, subwayProblem)
    loadRouteSequences(problemObj, subwayProblem)

    return subwayProblem


def getJsonProblem(jsonPath):
    with open(jsonPath, "rb") as jsonFile:
        jsonFileString = jsonFile.read()
    problemObj = json.loads(jsonFileString)
    return problemObj


def fastCopySubwayProblem(old, problemObj, memo={}, excludeItems=set(['Depot', 'LaunchAndForgetDepot'])):
    result = SubwayProblem()
    memo[id(old)] = result
    for k, v in old.__dict__.items():
        if k not in excludeItems:
            setattr(result, k, copy.deepcopy(v, memo))
    loadDepots(problemObj, result)
    loadRoutes(problemObj, result)
    loadRouteSequences(problemObj, result)
    return result


import re
import copy
from functools import wraps, lru_cache
from time import time

class ClassFactory(type):
    def __new__(cls, name, bases, dct):
        dct['_instances'] = {}
        return super().__new__(cls, name, bases, dct)

    def __call__(cls, *args, **kwargs):
        instance = super().__call__(*args, **kwargs)
        cls._instances[kwargs["_id"]] = instance
        return instance

    def __iter__(cls):
        # return iter(cls._instances)
        return (iter(cls._instances.items()))

    def __getitem__(cls, _id):
        return cls._instances[_id]

    def __len__(cls):
        return len(cls._instances)

    def __copy__(self):
        cls = self.__class__
        result = cls.__new__(cls)
        result.__dict__.update(self.__dict__)
        return result

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            setattr(result, k, copy.deepcopy(v, memo))
        return result

def timeit(f):
    @wraps(f)
    def wrap(*args, **kw):
        ts = time()
        result = f(*args, **kw)
        te = time()
        print(f'func:{f.__name__} took: {te-ts:.4f} sec')
        return result
    return wrap

def stringToSeconds(hhmmssString):
    timeSplit = hhmmssString.split(":")
    timeSplit = map(int, timeSplit)
    multipliers = (3600, 60, 1)
    seconds = 0
    for timePart, multiplier in zip(timeSplit, multipliers):
        seconds += timePart * multiplier
    return int(seconds)

def secondsToString(seconds):
    hour = seconds // 3600
    minute = seconds % 3600 // 60
    second = seconds % 60
    hhmmString = f"{hour:02}:{minute:02}:{second:02}"
    return hhmmString

def getVariableBounds(problemConfig):
    depotIds = problemConfig['headwayConfig'].keys()
    variableBounds = {}
    intervalBounds = {}
    sorter = lambda x: tuple(sorted(x.values()))
    for depotId in depotIds:
        intervalSizeLowerBoundsInSeconds = tuple(problemConfig['periodMinSizes'][depotId])
        intervalSizeUpperBoundsInSeconds = tuple(problemConfig['periodMaxSizes'][depotId])
        intervalBoundsInSeconds = tuple(list(zip(intervalSizeLowerBoundsInSeconds, intervalSizeUpperBoundsInSeconds)))
        intervalBounds[depotId] = intervalBoundsInSeconds
        initialTimePeriodsInSeconds = tuple(problemConfig['timePeriodConfig'][depotId])
        plusWindows = tuple(problemConfig['plusOrMinusWindows'][depotId])
        minusWindows =  tuple(problemConfig['plusOrMinusWindows'][depotId])
        variableLowerBoundsInSeconds = tuple([t - delta for t, delta in zip(initialTimePeriodsInSeconds,  minusWindows)])
        variableUpperBoundsInSeconds = tuple([t + delta for t, delta in zip(initialTimePeriodsInSeconds,  plusWindows)])
        variableBoundsInSeconds = tuple(list(zip(variableLowerBoundsInSeconds, variableUpperBoundsInSeconds)))
        variableBounds[depotId] = variableBoundsInSeconds
    return {'variableBounds':variableBounds, 'intervalBounds':intervalBounds}

def getFeasibleTimePeriods(subwayProblem, problemConfig, timeUnitsInMinutes=40):
    dayBeginSeconds = subwayProblem.dayBeginTimeSeconds
    dayEndSeconds = subwayProblem.dayEndTimeSeconds
    timeUnitsInSeconds = timeUnitsInMinutes * 60
    depotIds = problemConfig['headwayConfig'].keys()
    answerSets = {}
    sorter = lambda x: tuple(sorted(x.values()))
    for depotId in depotIds:
        intervalSizeLowerBoundsInSeconds = tuple(problemConfig['periodMinSizes'][depotId])
        intervalSizeUpperBoundsInSeconds = tuple(problemConfig['periodMaxSizes'][depotId])
        initialTimePeriodsInSeconds = tuple(problemConfig['timePeriodConfig'][depotId])
        plusWindows = tuple(problemConfig['plusOrMinusWindows'][depotId])
        minusWindows =  tuple(problemConfig['plusOrMinusWindows'][depotId])
        variableLowerBoundsInSeconds = tuple([t - delta for t, delta in zip(initialTimePeriodsInSeconds,  minusWindows)])
        variableUpperBoundsInSeconds = tuple([t + delta for t, delta in zip(initialTimePeriodsInSeconds,  plusWindows)])

        numHeadways = len(problemConfig['headwayConfig'][depotId])
        numTimeVariables = numHeadways + 1
        assert len(intervalSizeUpperBoundsInSeconds) \
               == len(intervalSizeLowerBoundsInSeconds) \
               == numHeadways \
               == len(initialTimePeriodsInSeconds) - 1

        variableDomains = tuple([range(begin, end+1, timeUnitsInSeconds) for begin, end in zip(variableLowerBoundsInSeconds, variableUpperBoundsInSeconds)])

        cspSolution = modelAndSolveCsp(variableDomains,
                                                intervalSizeLowerBoundsInSeconds,
                                                intervalSizeUpperBoundsInSeconds)

        cspSolution = tuple(map(sorter, cspSolution))
        answerSets[depotId] = cspSolution
    return answerSets
    """
    dict_sorter = lambda x: dict(sorted(x.items()))
    to_mins = lambda x: int(seconds_since_midnight(x) / 60)
    value_extractor = lambda x: list(map(to_mins, x.values()))
    sorted_sols = list(map(dict_sorter, sols))
    feasible_set = list(map(value_extractor, sorted_sols))

    # print([[int(seconds_since_midnight(dict[key])/60) for key in varStore] for dict in sols][0])
    """


# For sorting text strings using numbers inside them
def atof(text):
    try:
        retval = float(text)
    except ValueError:
        retval = text
    return retval

def natural_keys(text):
    return [ atof(c) for c in re.split(r'[+-]?([0-9]+(?:[.][0-9]*)?|[.][0-9]+)', text) ]

def argmin(a):
    return min(range(len(a)), key=lambda x: a[x])
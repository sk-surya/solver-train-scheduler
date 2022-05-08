from .simulation.errors import SimulationError

def timeToTravel(_departFrom, _arriveTo, travelTime, Error=RuntimeError):
    """
    The time to travel between nodes in the subway
    :param _departFrom: a Station like object or object Id
    :param _arriveTo: a Station like object or object Id
    :return: travel duration
    """
    # if isinstance(_departFrom, int):
    #     departFrom, arriveTo = _departFrom, _arriveTo
    # else:
    departFrom, arriveTo = _departFrom._id, _arriveTo._id

    if (departFrom, arriveTo) in travelTime:
        return travelTime[(departFrom, arriveTo)]
    else:
        raise Error(f"No travel time info for {(departFrom, arriveTo)}")


def clamp(old, new, step):
    """
    a function to help smooth transition of headway
    :param old:
    :param new:
    :param step:
    :return:
    """
    if not old: return new
    if not new: return old
    if old >= new: return max(old - step, new)
    if old  < new: return min(old + step, new)
    raise RuntimeError("Unexpected clamp behavior")


def smooth(step = 60):
    # The user might want to specify transition size.
    # smooth is a decorator that takes user argument and
    # returns a decorator 'inner_smooth' which wraps
    # 'headwayFunction'
    def inner_smooth(headwayFunction, step = step):
        # We want a gradual transition for headway times.
        # Hence this decorator produces exactly that.
        def wrapper(timepoint):
            newHeadway = headwayFunction(timepoint)
            wrapper.lastHeadway = clamp(wrapper.lastHeadway, newHeadway, step)
            return wrapper.lastHeadway
        wrapper.lastHeadway = None
        # We have a statefull function. We might want to be able
        # to reset it.
        def reset():
            wrapper.lastHeadway = None
        wrapper.reset = reset
        return wrapper
    return inner_smooth

def getHeadwayFunction(timePeriodSequence, headways, decorate = lambda x: x):
    """ Returns a Headway Function.
        timePeriods: an array of pairs (tB, tE), where
            tB is the time period begins, and tE - time
            it ends
        headwaySequence: an array of acceptable headways corresponding
            to each time period.
    """
    timePeriods = tuple((begin, end) for begin, end in zip(timePeriodSequence[:-1], timePeriodSequence[1:]))
    assert len(timePeriods) == len(headways), "Time periods and headwaySequence must have the same number of elements"

    @decorate
    def headwayFunction(x):
        for (period, (tBegin, tEnd)) in enumerate(timePeriods):
            if x >= tBegin and x < tEnd:
                return headwayFunction.headways[period]
        raise SimulationError(f"No headway is defined for time {x}")
    headwayFunction.headways = headways
    headwayFunction.timePeriods = timePeriods
    #headwayFunction.__repr__ = lambda: "asdas"
    return headwayFunction



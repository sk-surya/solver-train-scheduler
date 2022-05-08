
from .simulation.errors import SimulationError, SimulationInitializationError
from .simulation.utils import log
from .functions import timeToTravel as timeToTravelFunc
from utils import ClassFactory, secondsToString
from simpy.util import start_delayed
import copy
import itertools

class ProblemInitializationError(RuntimeError):
    """An error class to invoke when something goes wrong
        while initializing nested classes of SubwayProblem
    """
    pass



class SubwayProblem(object):
    #class SubwayClassFactory(ClassFactory):
    #    pass

    #print(type(ClassFactory))
    #assert type(SubwayClassFactory) == type(Meta)
    timeToTravel = None
    # SubwayClassFactory = Meta()


    def __init__(self):
        def createClassFactory():
            return copy.deepcopy(ClassFactory)
        self.ClassFactory = createClassFactory()
        class Depot(metaclass=self.ClassFactory):
            """ Represents a depot adjointed to a station.

                Implementation Note:
                    While it follows the interface for a station, is not a
                    descendant of a station.
            """

            def __init__(self, name, firstLaunchAt, _id):
                """ headwayFunction: Numeric t -> Numeric
                        Returns the time before the next train departure
                        from this depot, if the last train left at time t.
                    firstLaunchAt: Time delta seconds from SimulationBegin
                """
                self._id = _id
                self.env = None
                self.name = name
                self.headwayFunction = None
                self.routeSequence = None
                self.stationed = []
                self.initialTrainCount = 0
                self.firstLaunchAt = firstLaunchAt
                self.departureTimes = []
                self.action = None
                self.trainsLaunchedCounter = 0

            def __str__(self):
                return self.name

            def addTrain(self, train):
                self.stationed.insert(0, train)

            def setHeadwayFunction(self, headwayFunction):
                self.headwayFunction = headwayFunction

            def setRouteSequence(self, routeSequence):
                self.routeSequence = routeSequence

            def setSimulationEnvironment(self, env):
                self.env = env
                self.action = start_delayed(self.env, self.serve(), self.firstLaunchAt)

            def serve(self):
                # Depot process loop:
                # 1) Send out a train
                # 2) Wait for headway
                # We additionally need to check that there are trains
                # present at the depot. If there are non, it means
                # that we can not follow this headway/dwell schedule.
                if not self.env:
                    raise SimulationInitializationError("Depot must be bound with a simulation environment.")
                self.initialTrainCount = len(self.stationed)
                if self.routeSequence == None:
                    raise SimulationInitializationError(
                        f"Depot {self.name} must be set with a routing sequence to serve.")
                if self.headwayFunction == None:
                    raise SimulationInitializationError(
                        f"Depot {self.name} must be set with a headway function to serve.")
                for route in itertools.cycle(self.routeSequence):
                    # 1) Send out a train
                    if len(self.stationed) == 0:
                        raise SimulationError(f"{self} has ran out of trains.")

                    # Get a train that we are going to send out and remove it
                    # from the train pool
                    train, self.stationed = self.stationed[-1], self.stationed[:-1]
                    log(self.env, f"Sending out {train} from {self}")
                    train.currentTripNumber = TripCounter.newTrip()  # just so we get it in eventLog
                    train.route = route  # just so we get it in eventLog
                    train.addEventLog(self, "departure")
                    self.departureTimes.append(self.env.now)

                    # For all trains launched from depot, we add travelTime
                    # We assume this happens only when the train is Depot-OUTed the first time
                    if self.trainsLaunchedCounter < self.initialTrainCount:
                        log(self.env, f"Depot-Out operation {train} from {self}")
                        yield self.env.timeout(route.depotToFirstStationTime)

                    self.env.process(train.launch(route))
                    # 2) Wait for headway
                    timeForNextLaunch = self.headwayFunction(self.env.now)
                    log(self.env, f"Next train will depart from {self} in {timeForNextLaunch} seconds")
                    yield self.env.timeout(timeForNextLaunch)
                    self.trainsLaunchedCounter += 1

        class Train(metaclass=self.ClassFactory):
            def __init__(self, name, _id, depot=None):
                """ env:   SimPy Environment
                    name:  a (preferrably unique) identifier for a train
                    depot: a depot this train initialized in
                """
                if not depot:
                    raise ProblemInitializationError("Train must be initialized in a depot")
                self.name = name
                self._id = _id
                self.env = None
                self.depot = depot
                self.depot.addTrain(self)
                self.action = None
                self.route = None
                self.turnAroundTime = None
                self.depotToFirstStationTime = None
                self.timeToDummyDepot = None
                self.eventsLog = {}
                self.currentTripNumber = None

            def setSimulationEnvironment(self, env):
                self.env = env

            def launch(self, route):
                if not self.env:
                    raise SimulationInitializationError(
                        "Train must be bound with a simulation environment before launch.")

                self.route = route
                yield self.env.process(self.proceed())

            def __str__(self):
                return self.name

            def addEventLog(self, node, action):
                payload = {
                    'time': secondsToString(self.env.now),
                    'node': str(node),
                    'action': action
                }
                tripNumberKey = f'Trip #{self.currentTripNumber}'
                if tripNumberKey in self.eventsLog:
                    self.eventsLog[tripNumberKey]['events'].append(payload)
                else:
                    self.eventsLog[tripNumberKey] = {}
                    self.eventsLog[tripNumberKey]['route'] = str(self.route)
                    self.eventsLog[tripNumberKey]['events'] = [payload]

            def proceed(self):
                # Train process loop:
                # 1) Dwell at the current station
                # 2) Depart from the current station
                # 3) Arrive to the next station
                while True:
                    if not self.route:
                        log(self.env, f"{self} is idle at {self.depot}.")
                        self.addEventLog(self.depot, "idle")
                        return

                    # we assume we are able to begin the trip from the first station
                    self.route.stations[0].arrive(self)
                    for fromStation, toStation in zip(self.route.stations[:-1], self.route.stations[1:]):
                        dwellTime = fromStation.getDwellTime()
                        log(self.env, f"{self} is dwelling at {fromStation} for {dwellTime} seconds.")
                        yield self.env.timeout(dwellTime)
                        # 2) Depart from the current station
                        log(self.env, f"{self} is departing from {fromStation}")
                        timeToArrive = SubwayProblem.timeToTravel(fromStation, toStation)
                        # Notify the station that the train has departed
                        fromStation.depart(toStation, self)
                        log(self.env, f"{self} will arrive to {toStation} in {timeToArrive} seconds")
                        yield self.env.timeout(timeToArrive)
                        # 3) Arrive to the next station
                        # Notify the station that the train has arrived
                        toStation.arrive(self)

                    dwellTime = toStation.getDwellTime()
                    log(self.env, f"{self} is dwelling at {toStation} for {dwellTime} seconds.")
                    yield self.env.timeout(dwellTime)
                    log(self.env, f"{self} is departing from {toStation}")
                    toStation.depart(self.route.depot, self)  # we send the train to dummy Depot
                    # but it is logged as sending to Real Depot

                    self.turnAroundTime = self.route.turnAroundTime
                    self.timeToDummyDepot = max(self.turnAroundTime, self.route.lastStationToDepotTime)

                    yield self.env.timeout(self.timeToDummyDepot)
                    self.addEventLog(self.route.depot,
                                     "soft-arrival")  # It could either go to real depot or continue loop
                    self.route.depot.addTrain(self)
                    self.route = None

        class Route(object, metaclass=self.ClassFactory):
            def __init__(self, name, stations, launchDepot, circulatingDepot, turnAroundTime, _id):
                self._id = _id
                self.name = name
                self.stations = copy.copy(stations)
                self.launchDepot = launchDepot
                self.circulatingDepot = circulatingDepot
                self.depot = self.circulatingDepot
                self.timeToTravel = SubwayProblem.timeToTravel
                self.depotToFirstStationTime = self.timeToTravel(self.launchDepot, self.stations[0])
                self.lastStationToDepotTime = self.timeToTravel(self.stations[-1], self.circulatingDepot)
                self.turnAroundTime = turnAroundTime

            def __str__(self):
                return f"{self.name}"

            def __iter__(self):
                return self.stations.__iter__()

            def __getitem__(self, item):
                return self.stations[item]

            def appendStation(self, station):
                self.stations.append(station)

        class Station(metaclass=self.ClassFactory):
            """ Represents a Station on the route.

                TODO: Promote this to SimPy Resource.
            """

            def __init__(self, name, arrivalsFunction, minDwellDuration, _id):
                """ env:  SimPy Environment
                    name: a (preferrably unique) identifier for a station
                    arrivalsFunction: Numeric t -> Numeric
                        a function of one numerical argument which returns
                        the total number of passengers whe entered the
                        station by time t
                    departuresFunction: Numeric t -> Numeric
                        a function of one numerical argument which returns
                        the total number of passengers who left the the
                        station by time t
                """
                self._id = _id
                self.name = name
                self.env = None
                self.arrivalsFunction = arrivalsFunction
                # self.departuresFunction = departuresFunction

                self.setDwellTime(minDwellDuration)
                self.onArrivalAction = None
                self.accumulatedWaiting = 0
                self.lastDepartureTime = 0
                self.departureTimes = []

            def __str__(self):
                return self.name

            def setSimulationEnvironment(self, env):
                self.env = env

            def setDwellTime(self, dwellTime):
                """ Sets the dwell time for this station to a constant
                    value of dwellTime
                    dwellTime: a Numeric argument
                """
                self.dwellFunction = lambda t: dwellTime

            def setDwellFunction(self, dwellFunction):
                """ Sets the dwell time for this station to a function
                    of current time.
                    dwellFunction: Numeric t -> Numeric
                        a function of one numerical argument which
                        returns the dwell time for a train arriving to
                        at the station at time t
                """
                self.dwellFunction = dwellFunction

            def getDwellTime(self):
                return self.dwellFunction(self.env.now)

            def trackWaitingTime(self):
                # We assume an uniform arrival rate between two close-enough
                # time points.
                timeDelta = self.env.now - self.lastDepartureTime
                passDelta = self.arrivalsFunction(self.env.now) - self.arrivalsFunction(self.lastDepartureTime)
                self.accumulatedWaiting += timeDelta * passDelta / 2.0

            def arrive(self, train):
                """ An on-arrival notification.
                    A self.onArrivalAction hook is called if it was injected
                    to extend the functionality.
                """
                if not self.env:
                    raise SimulationInitializationError("Station must be bound with a simulation environment.")
                log(self.env, f"{self} is observing {train} arrival")
                train.addEventLog(self, "arrival")
                if self.onArrivalAction: self.onArrivalAction(self, train)

            def setOnArrivalAction(self, action):
                """ Injects an on-arrival hook.
                    action: Station s, Train t -> void
                        Allows user (usually a Depot-like-class) to extend
                        the on-arrival logic of the station. For example,
                        to move the train to the depot's stationed trains
                        list.
                """
                self.onArrivalAction = action

            def depart(self, nextStation, train):
                """ An on-departure notification.
                """
                if not self.env:
                    raise SimulationInitializationError("Station must be bound with a simulation environment.")
                log(self.env, f"{self} is observing {train} departure to {nextStation}")
                train.addEventLog(self, "departure")
                # Update the accumulated waiting time.
                self.trackWaitingTime()
                # We need to keep track of stations we sent trains to.
                self.departureTimes.append(self.env.now)
                self.lastDepartureTime = self.env.now

        class TripCounter:
            totalTrips = 0

            @classmethod
            def newTrip(cls):
                cls.totalTrips += 1
                return cls.totalTrips

            @classmethod
            def lastTripNumber(cls):
                return cls.totalTrips

        class LaunchAndForgetDepot(Depot):
            """ Represents a depot that just launches trains to specified
                routes and forgets.

                Implementation Note:
                    Descendant of depot. The only difference is depot cyclically
                    sends out trains to routes and expects those trains to come back,
                    if depot runs out of trains, simulation error is raised. But here,
                    we just launch the trains and forget.
            """

            def serve(self):
                # Depot process loop:
                # 0) Wait for First launch time
                # 1) Send out a train
                # 2) Wait for headway

                if not self.env:
                    raise SimulationInitializationError(
                        "LaunchAndForgetDepot must be bound with a simulation environment.")
                if self.routeSequence == None:
                    raise SimulationInitializationError(
                        f"Depot {self.name} must be set with a routing sequence to serve.")
                if self.headwayFunction == None:
                    raise SimulationInitializationError(
                        f"Depot {self.name} must be set with a headway function to serve.")
                self.initialTrainCount = len(self.stationed)
                routeSequencer = itertools.cycle(self.routeSequence)
                while self.stationed:
                    # Get a train that we are going to send out and remove it
                    # from the train pool
                    route = routeSequencer.__next__()
                    train, self.stationed = self.stationed[-1], self.stationed[:-1]

                    log(self.env, f"Sending out {train} from {self}")
                    train.currentTripNumber = TripCounter.newTrip()  # just so we get it in eventLog
                    train.route = route  # just so we get it in eventLog
                    train.addEventLog(self, "departure")
                    self.departureTimes.append(self.env.now)
                    log(self.env, f"Depot-Out operation {train} from {self}")
                    yield self.env.timeout(route.depotToFirstStationTime)

                    self.env.process(train.launch(route))
                    # 2) Wait for headway
                    timeForNextLaunch = self.headwayFunction(self.env.now)
                    log(self.env, f"Next train will depart from {self} in {timeForNextLaunch} seconds")
                    yield self.env.timeout(timeForNextLaunch)
                    self.trainsLaunchedCounter += 1
        self.lineId = None
        self.lineName = None
        self.dayBeginTimeSeconds = None
        self.dayEndTimeSeconds = None
        self.travelTimes = None
        self.timeToTravel = None
        self.Depot = Depot
        self.Station = Station
        self.LaunchAndForgetDepot = LaunchAndForgetDepot
        self.Train = Train
        self.Route = Route
    def setLineInfo(self, lineId, lineName, dayBeginTimeSeconds, dayEndTimeSeconds):
        self.lineId = lineId
        self.lineName = lineName
        self.dayBeginTimeSeconds = dayBeginTimeSeconds
        self.dayEndTimeSeconds = dayEndTimeSeconds
    def setTravelTimes(self, travelTimes):
        self.travelTimes = travelTimes
        self.setTimeToTravelFunction()
    def setTimeToTravelFunction(self):
        if self.travelTimes is None:
            raise ProblemInitializationError("Travel Times must be loaded into the problem.")
        SubwayProblem.timeToTravel = lambda i, j : timeToTravelFunc(i, j, self.travelTimes, SimulationError)
    def getTimeToTravel(self):
        return SubwayProblem.timeToTravel





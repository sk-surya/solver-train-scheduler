from jmetal.core.problem import Problem
from jmetal.core.operator import Mutation
from jmetal.core.solution import Solution
from abc import ABC, abstractmethod
import random
from utils import secondsToString

class TimePeriodSolution(object):
    """ Class representing TimePeriod solutions
        Has Time Partition of a day for each depot
    """
    def __init__(self, feasibleSolution, variableBoundsDict, intervalBoundsDict):
        self.number_of_depots = len(feasibleSolution.keys())
        self.objectives = [None]
        self.variables = {}
        self.constraints = []
        for key, val in feasibleSolution.items():
            self.variables[key] = list(val)
        self.variableBounds = variableBoundsDict
        self.intervalBounds = intervalBoundsDict
        self.headwayFunctions = None

    def __str__(self):
        printDict = self.getSolutionDict()
        return f'TimePeriodSolution({printDict})'

    def getSolutionDict(self):
        printDict = {}
        for key, val in self.variables.items():
            printDict[key] = list(map(secondsToString, self.variables[key]))
        return printDict

    def __copy__(self):
        new_solution = TimePeriodSolution(self.variables, self.variableBounds, self.intervalBounds)
        new_solution.objectives = self.objectives
        new_solution.headwayFunctions = self.headwayFunctions

class RandomGenerator(object):
    def new(self, problem: Problem, solution):
        return problem.create_solution(solution)

class RandomMutationSingle(Mutation[TimePeriodSolution]):
    def __init__(self, probability=0.5):
        super().__init__(probability=probability)

    def execute(self, solution:TimePeriodSolution):
        timeUnitInSeconds = 600
        validMoveDirections = ('left', 'right')
        directionMultipliers = {'left': -1, 'right': 1}
        variables = solution.variables
        for depotId, timePeriods in variables.items():
            variableBounds = solution.variableBounds[depotId]
            intervalBounds = solution.intervalBounds[depotId]
            timeSlot = random.choice(range(1, len(timePeriods) - 1))
            moveDirection = random.choice(validMoveDirections)
            intervalSizes = [t2 - t1 for t1, t2 in zip(timePeriods[:-1], timePeriods[1:])]

            leftInterval = timeSlot - 1
            rightInterval = timeSlot
            if moveDirection == 'left':
                # left interval will shrink & right will grow
                # this should be within bounds
                leftIntervalSize = intervalSizes[leftInterval]
                leftIntervalLowerBound = intervalBounds[leftInterval][0]
                maxStepSizeByLeftInterval = leftIntervalSize - leftIntervalLowerBound

                rightIntervalSize = intervalSizes[rightInterval]
                rightIntervalUpperBound = intervalBounds[rightInterval][1]
                maxStepSizeByRightInterval = rightIntervalUpperBound - rightIntervalSize

                maxStepSizeByIntervals = min(maxStepSizeByLeftInterval, maxStepSizeByRightInterval)

                variableValue = timePeriods[timeSlot]
                variableValueLowerBound = variableBounds[timeSlot][0]
                maxStepSizeByVariable = variableValue - variableValueLowerBound

                maxStepSize = min(maxStepSizeByIntervals, maxStepSizeByVariable)
            else:
                # right interval shrinks, left grows
                leftIntervalSize = intervalSizes[leftInterval]
                leftIntervalUpperBound = intervalBounds[leftInterval][1]
                maxStepSizeByLeftInterval = leftIntervalUpperBound - leftIntervalSize

                rightIntervalSize = intervalSizes[rightInterval]
                rightIntervalLowerBound = intervalBounds[rightInterval][0]
                maxStepSizeByRightInterval = rightIntervalSize - rightIntervalLowerBound

                maxStepSizeByIntervals = min(maxStepSizeByLeftInterval, maxStepSizeByRightInterval)

                variableValue = timePeriods[timeSlot]
                variableValueUpperBound = variableBounds[timeSlot][1]
                maxStepSizeByVariable = variableValueUpperBound - variableValue

                maxStepSize = min(maxStepSizeByIntervals, maxStepSizeByVariable)

            stepSize = random.random() * maxStepSize
            stepSize -= stepSize % timeUnitInSeconds
            stepSize = int(stepSize)
            delta = directionMultipliers[moveDirection] * stepSize
            timePeriods[timeSlot] += delta
        return solution

    def get_name(self) -> str:
        return 'RandomMutation'

class RandomMutationAll(Mutation[TimePeriodSolution]):
    def __init__(self, probability=0.5):
        super().__init__(probability=probability)

    def execute(self, solution:TimePeriodSolution):
        timeUnitInSeconds = 600
        validMoveDirections = ('left', 'right')
        directionMultipliers = {'left': -1, 'right': 1}
        variables = solution.variables
        for depotId, timePeriods in variables.items():
            variableBounds = solution.variableBounds[depotId]
            intervalBounds = solution.intervalBounds[depotId]
            for timeSlot in range(1, len(timePeriods) - 1):
                if random.random() < self.probability:
                    moveDirection = random.choice(validMoveDirections)
                    intervalSizes = [t2 - t1 for t1, t2 in zip(timePeriods[:-1], timePeriods[1:])]

                    leftInterval = timeSlot - 1
                    rightInterval = timeSlot
                    if moveDirection == 'left':
                        # left interval will shrink & right will grow
                        # this should be within bounds
                        leftIntervalSize = intervalSizes[leftInterval]
                        leftIntervalLowerBound = intervalBounds[leftInterval][0]
                        maxStepSizeByLeftInterval = leftIntervalSize - leftIntervalLowerBound

                        rightIntervalSize = intervalSizes[rightInterval]
                        rightIntervalUpperBound = intervalBounds[rightInterval][1]
                        maxStepSizeByRightInterval = rightIntervalUpperBound - rightIntervalSize

                        maxStepSizeByIntervals = min(maxStepSizeByLeftInterval, maxStepSizeByRightInterval)

                        variableValue = timePeriods[timeSlot]
                        variableValueLowerBound = variableBounds[timeSlot][0]
                        maxStepSizeByVariable = variableValue - variableValueLowerBound

                        maxStepSize = min(maxStepSizeByIntervals, maxStepSizeByVariable)
                    else:
                        # right interval shrinks, left grows
                        leftIntervalSize = intervalSizes[leftInterval]
                        leftIntervalUpperBound = intervalBounds[leftInterval][1]
                        maxStepSizeByLeftInterval = leftIntervalUpperBound - leftIntervalSize

                        rightIntervalSize = intervalSizes[rightInterval]
                        rightIntervalLowerBound = intervalBounds[rightInterval][0]
                        maxStepSizeByRightInterval = rightIntervalSize - rightIntervalLowerBound

                        maxStepSizeByIntervals = min(maxStepSizeByLeftInterval, maxStepSizeByRightInterval)

                        variableValue = timePeriods[timeSlot]
                        variableValueUpperBound = variableBounds[timeSlot][1]
                        maxStepSizeByVariable = variableValueUpperBound - variableValue

                        maxStepSize = min(maxStepSizeByIntervals, maxStepSizeByVariable)

                    stepSize = random.random() * maxStepSize
                    stepSize -= stepSize % timeUnitInSeconds
                    stepSize = int(stepSize)
                    delta = directionMultipliers[moveDirection] * stepSize
                    timePeriods[timeSlot] += delta
        return solution

    def get_name(self) -> str:
        return 'RandomMutation'

class TimePeriodsProblemBase(object):
    """ Class representing integer problems. """

    def __init__(self, feasibleSolution):

        self.feasibleSolution = feasibleSolution
        self.number_of_objectives = 1
        self.MINIMIZE = -1
        # self.number_of_variables = len(list(feasibleSolution.values())[0])
        self.obj_directions = [self.MINIMIZE]
        self.obj_labels = ['TotalWaitingTime']

    @abstractmethod
    def evaluate(self, feasibleSolution):
        pass

    def create_solution(self, solution: TimePeriodSolution) -> TimePeriodSolution:
        new_solution = TimePeriodSolution(self.feasibleSolution.variables,
                                          self.feasibleSolution.variableBounds,
                                          self.feasibleSolution.intervalBounds)
        return RandomMutationSingle().execute(solution=new_solution)

    def get_name(self) -> str:
        return 'TimePeriodsProblem'
#!/usr/bin/env python
# coding: utf-8

# In[1]:
import sys

import logging
import subway.simulation.utils as u
import simpy
import pathlib
from joblib import Parallel, delayed
import multiprocessing as mp
import time
import problemLoader
from utils import secondsToString, natural_keys, timeit, getVariableBounds, argmin
from subway.simulation.errors import SimulationError
from optimization import TimePeriodsProblemBase, TimePeriodSolution, \
     RandomMutationAll, RandomGenerator
from jmetal.algorithm.singleobjective.simulated_annealing import SimulatedAnnealing
from jmetal.util.termination_criterion import StoppingByEvaluations, StoppingByTime
from jmetal.util.observer import PrintObjectivesObserver
import os
print(os.getcwd())
import json
import argparse

# In[2]:

LOGGER = logging.getLogger('jmetal')

def runSimulation(env, newSubwayProblem):
    try:
        env.run(until=newSubwayProblem.dayEndTimeSeconds)
        totalWaiting = sum(station.accumulatedWaiting for _id, station in newSubwayProblem.Station)
    except SimulationError:
        totalWaiting = INF
        # print("Current solution not feasible for simulation.")
    except Exception:
        totalWaiting = INF
        # print("Unknown error during simulation for current simulation.")
    return totalWaiting

def print_variables_to_file(solutions, filename: str):
    LOGGER.info('Output file (variables): ' + filename)

    try:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
    except FileNotFoundError:
        pass

    if type(solutions) is not list:
        solutions = [solutions]

    with open(filename, 'w') as of:
        for solution in solutions:
            of.write(str(solution) + " ")
            of.write("\n")

INF = 2 ** 31
u.ENABLE_LOG = False
u.ENABLE_DEBUG_PRINT = False

def main(jsonInputFilePath, max_seconds):
    jsonPath = jsonInputFilePath
    problemObj = problemLoader.getJsonProblem(jsonPath)
    subwayProblem = problemLoader.createSubwayProblemFromJson(problemObj)

    problemConfigs = problemLoader.problemConfigGenerator(problemObj, subwayProblem)
    problemConfig = list(problemConfigs)[0]

    class TimePeriodsProblem(TimePeriodsProblemBase):
        def __init__(self, feasibleSolution):
            super().__init__(feasibleSolution)

        def evaluate(self, feasibleSolution, problemObj=problemObj):
            subwayProblem = problemLoader.createSubwayProblemFromJson(problemObj)

            headwayFunctions = problemLoader.loadHeadways(problemConfig, subwayProblem, feasibleSolution.variables)
            env = simpy.Environment()
            problemLoader.loadEnvironment(env, subwayProblem)
            # print(feasibleSolution)
            waiting = runSimulation(env, subwayProblem)
            # print(waiting)
            feasibleSolution.objectives[0] = waiting
            feasibleSolution.headwayFunctions = headwayFunctions
            return feasibleSolution

        def printJsonSolution(self, problemObj, outputPath):
            subwayProblem = problemLoader.createSubwayProblemFromJson(problemObj)

            headwayFunctions = problemLoader.loadHeadways(
                problemConfig,
                subwayProblem,
                self.feasibleSolution.variables
            )
            env = simpy.Environment()
            problemLoader.loadEnvironment(env, subwayProblem)
            # print(feasibleSolution)
            waiting = runSimulation(env, subwayProblem)
            trainsLog = {}
            for _id, train in subwayProblem.Train:
                trainsLog[str(train)] = train.eventsLog

            tripsLog = {}
            for trainNumber in trainsLog.keys():
                for tripNumber, tripLog in trainsLog[trainNumber].items():
                    if not tripNumber in tripsLog:
                        tripsLog[tripNumber] = {}
                    tripsLog[tripNumber]['train'] = trainNumber
                    tripsLog[tripNumber]['route'] = tripLog['route']
                    tripsLog[tripNumber]['events'] = tripLog['events']
            tripsLog = {key: tripsLog[key] for key in sorted(tripsLog.keys(), key=natural_keys)}

            depotDepartures = {}
            depotIdList = [depot['id'] for depot in problemObj['lineNodes']['depots']]
            for _id in depotIdList:
                depotObj = problemLoader.getDepotLikeObj(_id, subwayProblem)
                depotDepartures[f'{str(depotObj)}'] = list(map(secondsToString, depotObj.departureTimes))

            stationDepartures = {}
            for _id, station in subwayProblem.Station:
                stationDepartures[f'{str(station)}'] = list(map(secondsToString, station.departureTimes))

            with open(outputPath / 'TrainLog.json', "w") as f:
                f.write(json.dumps(trainsLog, indent=2))

            with open(outputPath / 'TripsLog.json', "w") as f:
                f.write(json.dumps(tripsLog, indent=2))

            with open(outputPath / 'DepotDeparturesLog.json', "w") as f:
                f.write(json.dumps(depotDepartures, indent=2))

            with open(outputPath / 'StationDeparturesLog.json', "w") as f:
                f.write(json.dumps(stationDepartures, indent=2))

    bounds = getVariableBounds(problemConfig)
    variableBounds = bounds['variableBounds']
    intervalBounds = bounds['intervalBounds']

    t1 = time.time()

    initialSolution = problemConfig['timePeriodConfig']

    initialSolution = TimePeriodSolution(initialSolution, variableBounds, intervalBounds)
    problem = TimePeriodsProblem(initialSolution)
    print(f"Inital : {initialSolution}")

    def createAlgorithm(probability=0.5):
        class MySimulatedAnnealing(SimulatedAnnealing):
            def __init__(self, problem, mutation, termination_criterion, initial_solution):
                super().__init__(problem, mutation, termination_criterion)
                self.solution_generator = RandomGenerator()
                self.solution = initial_solution

            def create_initial_solutions(self):
                return [self.solution_generator.new(self.problem, self.solution)]

            def get_name(self):
                return 'SimulatedAnnealing'

            def get_solution(self):
                return self.solution

        return MySimulatedAnnealing(
                    problem=problem,
                    mutation=RandomMutationAll(probability),
                    termination_criterion=StoppingByTime(max_seconds=max_seconds),
                    initial_solution=initialSolution
                )

    def optimize(p):
        algorithm = createAlgorithm(p)

        class PrintObjectivesMyObserver(PrintObjectivesObserver):

            def __init__(self, frequency: float = 1.0) -> None:
                super().__init__()

            def update(self, *args, **kwargs):
                evaluations = kwargs['EVALUATIONS']
                solutions = kwargs['SOLUTIONS']

                if (evaluations % self.display_frequency) == 0 and solutions:
                    if type(solutions) == list:
                        fitness = solutions[0].objectives
                    else:
                        fitness = solutions.objectives

                    LOGGER.info(
                        'Evaluations: {}. fitness: {}, solution: {}'.format(
                            evaluations, fitness, solutions
                        )
                    )
        progress_bar = PrintObjectivesMyObserver()
        algorithm.observable.register(progress_bar)
        algorithm.run()
        result = algorithm.get_result()
        cTime = algorithm.total_computing_time
        return result, cTime

    numCores = mp.cpu_count() - 2

    toDecimal = lambda x: x / 100
    probabilityList = list(map(toDecimal, range(10, 100 + 1, int((1 / numCores) * 100))))
    algorithms = Parallel(n_jobs=numCores)(delayed(optimize)(p) for p in probabilityList)
    # Save results to file
    objectives = []
    cTimes = []
    for algorithm in algorithms:
        objectives.append(algorithm[0].objectives[0])
        cTimes.append(str(algorithm[1]))
    print(objectives)
    print(cTimes)
    algorithm = algorithms[argmin(objectives)]
    result = algorithm[0]

    print('Problem: ' + problem.get_name())
    print(result)
    print('Best Fitness:  ' + str(result.objectives[0]))

    print(f"{time.time()-t1} seconds.")

    bestSolution = result
    print(bestSolution)

    outputPath = pathlib.Path(r'../output/')
    bestSolutionProblem = TimePeriodsProblem(bestSolution)
    bestSolutionProblem.printJsonSolution(problemObj, outputPath)

    with open(outputPath / 'timePeriods.json', 'w') as f:
        f.write(json.dumps(bestSolution.getSolutionDict(), indent=2))

    print('Solution written to output folder.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--max_seconds', '-s', help="Time Limit in Seconds", type=int)
    parser.add_argument('--json_input_file', '-i', help="JSON input file name", type=str)
    args = parser.parse_args()
    if args.max_seconds == None:
        raise ValueError("Missing arguments {max_seconds}.")
    max_seconds = args.max_seconds
    json_input_file = args.json_input_file
    jsonFolderPath = pathlib.Path(r'../data/')
    jsonPath = jsonFolderPath / json_input_file
    main(jsonPath, max_seconds)





Python Version 3.6
Please create a conda environment from environment.yml and run the code inside the environment.

The solver runs on a JSON input file.
Be within src folder before executing.

To build the JSON input:
example usage: python ttpJsonBuilder.py "Line5Data.xlsx"

To run the solver:
example usage: python solver.py --json_input_file Line5Problem.json --max_seconds 3600

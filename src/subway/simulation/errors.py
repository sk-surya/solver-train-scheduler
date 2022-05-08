# Separate SimulationError: an error during the run and SimulationInitializationError: an error during the setup phase.
class SimulationError(RuntimeError):
    """ A base class for simulation failures """
    pass


class SimulationInitializationError(RuntimeError):
    pass
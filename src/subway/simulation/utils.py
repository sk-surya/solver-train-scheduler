
ENABLE_LOG = None
ENABLE_DEBUG_PRINT = None

def log(env, what):
    if ENABLE_LOG: print(f"T{env.now:9}: {what}")


def debugPrint(*args, **kwargs):
    if ENABLE_DEBUG_PRINT:
        return print(*args, **kwargs)
    else:
        pass

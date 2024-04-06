from .magics import NbpilotMagics


def load_ipython_extension(ipython):
    ipython.register_magics(NbpilotMagics)

from IPython import get_ipython
from IPython.core.magic import Magics, line_cell_magic, magics_class

from .nbpilot import call_copilot_without_context, call_copilot_with_context, get_context
from .rag import search_and_answer


RUNNING_CELL_ID = None


@magics_class
class NbpilotMagics(Magics):
    @line_cell_magic
    def nbpilot(self, line, cell=None):
        if cell is None:
            call_copilot_without_context(line, RUNNING_CELL_ID)
        else:
            context = get_context(RUNNING_CELL_ID)
            call_copilot_with_context(context, cell, RUNNING_CELL_ID)

    @line_cell_magic
    def search(self, line, cell=None):
        search_and_answer([], line)


def pre_run_cell(info):
    global RUNNING_CELL_ID
    RUNNING_CELL_ID = info.cell_id


get_ipython().events.register('pre_run_cell', pre_run_cell)

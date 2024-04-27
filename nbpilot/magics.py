import argparse

from IPython import get_ipython
from IPython.core.magic import Magics, line_cell_magic, magics_class
import shlex

from .interactive import Inpteracter
from .nbpilot import call_nbpilot
from .rag import search_and_answer


RUNNING_CELL_ID = None


def run(args_line, query=None):
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--llm_provider", "-p",
        default="zhipu", dest="provider", help="llm provider")
    parent_parser.add_argument('--llm_model', "-m", required=False,
        dest="model", help="model name")
    parent_parser.add_argument('--debug', "-d", default=False, type=bool,
        dest="debug", help="run with debug mode")
    parent_parser.add_argument("--history_turns", "-H", required=False, help="history turns to include", type=int, default=0)
    parent_parser.add_argument("--cells", "-c", required=False, help="cells to include in the context")
    parent_parser.add_argument("--query", "-q", required=False, help="query")

    main_parser = argparse.ArgumentParser(prog="nbpilot", parents=[parent_parser])

    subparsers = main_parser.add_subparsers(title="sub commands", dest="sub_command")

    search_parser = subparsers.add_parser("search", help="semantic search",
        parents=[parent_parser])
    search_parser.add_argument("--search_api", default="ms", required=False, help="search api to use")

    search_parser = subparsers.add_parser("interact", help="run in interactive mode",
        parents=[parent_parser])

    try:
        args = main_parser.parse_args(shlex.split(args_line) if args_line else [])
        if query is None:
            query = args.query
    except:
        main_parser.print_help()
        return

    if args.sub_command is None:
        if query is None:
            main_parser.print_help()
            return
        call_nbpilot(query, RUNNING_CELL_ID, provider=args.provider, model=args.model,
                     history_turns=args.history_turns, context_cells=args.cells, debug=args.debug)

    elif args.sub_command == "search":
        if query is None:
            main_parser.print_help()
            return
        search_and_answer([], query, provider=args.provider, model=args.model, debug=args.debug)
    elif args.sub_command == "interact":
        interacter = Inpteracter(args.provider, args.model)
        return interacter.interact()


@magics_class
class NbpilotMagics(Magics):
    @line_cell_magic
    def nbpilot(self, line, cell=None):
        return run(line, cell)


def pre_run_cell(info):
    global RUNNING_CELL_ID
    RUNNING_CELL_ID = info.cell_id


get_ipython().events.register('pre_run_cell', pre_run_cell)

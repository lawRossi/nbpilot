import argparse

from IPython import get_ipython
from IPython.core.magic import Magics, line_cell_magic, magics_class
import shlex

from .interactive import Inpteracter
from .nbpilot import call_nbpilot, summarize_webpage
from .rag import build_index_from_url, retrieve_and_answer, search_and_answer


RUNNING_CELL_ID = None


def run(args_line, query=None):
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--llm_provider", "-p",
        default="zhipu", dest="provider", help="llm provider")
    parent_parser.add_argument('--llm_model', "-m", required=False,
        dest="model", help="model name")
    parent_parser.add_argument('--debug', "-d", action="store_true",
        dest="debug", help="run with debug mode")
    parent_parser.add_argument("--history_turns", "-H", required=False, help="history turns to include", type=int, default=0)
    parent_parser.add_argument("--cells", "-c", required=False, help="cells to include in the context")
    parent_parser.add_argument("--query", "-q", required=False, help="query")

    main_parser = argparse.ArgumentParser(prog="nbpilot", parents=[parent_parser])

    subparsers = main_parser.add_subparsers(title="sub commands", dest="sub_command")

    search_parser = subparsers.add_parser("search", help="semantic search",
        parents=[parent_parser])
    search_parser.add_argument("--search_api", default="ms", required=False, help="search api to use")

    read_parser = subparsers.add_parser("read", help="read a web page or file to create index",
        parents=[parent_parser])
    read_parser.add_argument("--url", required=False, help="the url of a web page")
    read_parser.add_argument("--index-name", "-i", required=False, help="the name of the index")

    ask_parser = subparsers.add_parser("ask", help="read a web page or file to create index",
        parents=[parent_parser])
    ask_parser.add_argument("--index_name", "-i", required=False, help="the name of the index")

    summarize_parser = subparsers.add_parser("summarize", help="summarize the content of a web page or a file",
        parents=[parent_parser])
    summarize_parser.add_argument("--url", required=False, help="the url of a web page")

    interact_parser = subparsers.add_parser("interact", help="run in interactive mode",
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
    elif args.sub_command == "read":
        build_index_from_url(args.url, args.index_name)
    elif args.sub_command == "ask":
        if query is None:
            main_parser.print_help()
            return
        retrieve_and_answer(query, args.index_name, args.provider, args.model, args.debug)
    elif args.sub_command == "summarize":
        summarize_webpage(args.url, provider=args.provider, model=args.model, debug=args.debug)
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

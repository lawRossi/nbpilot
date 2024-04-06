from argparse import ArgumentParser
import platform

from ipylab import JupyterFrontEnd
import ipynbname
from IPython.display import display, HTML
import markdown
import nbformat

from .llm import get_response


system_prompt = f"""
You are a helpful AI assistant to help people use jupyter notebook with your language skill
and coding skill. You are provided the content of the notebook and the query of the user.
First, analyze the query step by step, and then generate your answer.
You should first refer to the notebook content to find answer. You should write code to solve
the problem when possible. Your code can use variables, functions, and classes defined in the
notebook directly. The os of the jupyter runtime is {platform.platform()}.

Note: Your answer must use Chinese. Your code must be quoted as ```your code```.

The content of the notebook: {{context}}

The index of the current cell is {{cell_index}}.
"""


app = JupyterFrontEnd()


def get_context(cell_id):
    notebook_path = ipynbname.path()
    with open(notebook_path, encoding="utf-8") as fi:
        notebook = nbformat.read(fi, as_version=4)

    notebook_content = ""
    current_cell_index = None
    for i, cell in enumerate(notebook.cells):
        if cell.id == cell_id:
            current_cell_index = i + 1
        notebook_content += format_cell_content(cell, i) + "\n\n"

    return {"content": notebook_content.strip(), "cell_index": current_cell_index}


def format_cell_content(cell, cell_idx):
    cell_content = f"<cell>\nindex:{cell_idx+1}\ncell_type:{cell.cell_type}\ncontent:{cell.source}\n"
    if cell.cell_type == "code" and cell.outputs:
        cell_content += "outputs:\n"
        for output in cell.outputs:
            if output.output_type == "stream":
                cell_content += output.text
            elif output.output_type == "error":
                cell_content += output.ename + ":" + output.evalue
    cell_content += "<cell>"

    return cell_content


def call_copilot_with_context(context, query, cell_id, history=None):
    prompt = system_prompt.replace("{context}", context["content"])
    prompt = prompt.replace("{query}", query)
    prompt = prompt.replace("{cell_index}", str(context["cell_index"]))
    response = get_response(query, prompt, history)
    response_html = markdown.markdown(response, extensions=['fenced_code'])
    display(HTML(response_html), metadata={"copilot-output": True, "cellId": cell_id, "raw": response})


def call_copilot_without_context(query, cell_id, history=None):
    response = get_response(query, history=history)
    response_html = markdown.markdown(response, extensions=['fenced_code'])
    display(HTML(response_html), metadata={"copilot-output": True, "cellId": cell_id, "raw": response})


def print_help_message():
    arg_parser = ArgumentParser(prog="nbpilot", description="nbpilot commands", add_help=False)
    arg_parser.add_argument("--with_context", action="store_true", help="use the content of the notebook as context")
    arg_parser.add_argument("--history_turns", type=int, default=0, help="number of dialogue history to use")
    arg_parser.add_argument("--exclude", action="store_true", help="exclude a cell from the context")

    arg_parser.print_help()

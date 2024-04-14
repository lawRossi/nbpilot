import argparse
import platform
import re
import time

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


def get_latest_notebook_content(cell_id):
    app.commands.execute('docmanager:save')
    time.sleep(1)

    notebook_path = ipynbname.path()
    with open(notebook_path, encoding="utf-8") as fi:
        notebook = nbformat.read(fi, as_version=4)
    cells = []
    current_cell_index = None
    for i, cell in enumerate(notebook.cells):
        cells.append(format_cell_content(cell, i))
        if cell.id == cell_id:
            current_cell_index = i + 1

    return {"cells": cells, "current_cell_index": current_cell_index}


def parse_range(context_range, pivot_index):
    splits = [split.strip() for split in context_range.split(",")]
    parsed_range = []
    p = re.compile("([-]*\d+)\s*-\s*([+]*\d+)")
    for split in splits:
        m = p.match(split)
        if m:
            start = m.group(1)
            end = m.group(2)
            start = pivot_index + int(start) if start[0] == "-" else int(start)
            end = pivot_index + int(end) if end[0] == "+" else int(end)
            parsed_range.extend(range(start, end+1))
        elif split[0] in "-+":
            parsed_range.append(pivot_index+int(split))
        else:
            parsed_range.append(int(split))

    return parsed_range


def get_context(cell_id, context_range="all"):
    content = get_latest_notebook_content(cell_id)
    cells = content["cells"]
    current_cell_index = content["current_cell_index"]
    if context_range != "all":
        cells = [cells[idx-1] for idx in parse_range(context_range, current_cell_index)]

    return {"content": "\n\n".join(cells), "cell_index": current_cell_index}


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


def call_copilot_without_context(query, history=None, provider="ollama", model=None):
    system_prompt = """
    You are Nbpilot, a helpful AI assistant which help people in a jupyter notebook.
    Organize your output in markdown format.
    """
    response = get_response(
        query, system_prompt, history=history, stream=True, provider=provider, model=model
    )
    for chunk in response:
        if not chunk.choices:
            continue
        chunk_content = chunk.choices[0].delta.content
        if chunk_content is not None:
            print(chunk_content, end="")

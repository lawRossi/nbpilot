import platform
import re
import time

from ipylab import JupyterFrontEnd
import ipynbname
import nbformat

from .llm import get_response


system_prompt = f"""
You are Nbpilot, a helpful AI assistant to help people with your rich knowledge and
world-class programming skill. You must follow these rules:
1. Refer to the latest notebook content to find answer if it is provided. 
2. Try to derive a step-by-step answer or solution, and give a self-contained example.
3. Organize your output in markdown format.

System information:
OS: {platform.system()}
Current time: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}
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

    context = "\n\n".join(cells)
    return context


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


history = []


def remove_redundant_system_msg(selected_history):
    prev_system_msg_idx = None
    for i in range(len(selected_history) - 1, -1, -1):
        if selected_history[i]["role"] == "system":
            if not prev_system_msg_idx:
                prev_system_msg_idx = i
            elif selected_history[prev_system_msg_idx]["content"] == selected_history[i]["content"]:
                selected_history.pop(prev_system_msg_idx)
            else:
                prev_system_msg_idx = i


def call_nbpilot(query, cell_id, provider="ollama", model=None, history_turns=0, context_cells=None):
    selected_history = []
    n = 0
    if history_turns > 0:
        for i in range(len(history) - 1, -1, -1):
            if history[i]["role"] != "system" or context_cells is not None:
                selected_history.insert(0, history[i])
                if history[i]["role"] == "user":
                    n += 1
                    if n == history_turns:
                        break

    system_msg = None
    if context_cells:
        context = get_context(cell_id, context_cells)
        if context:
            context_content = "The content of selected cells provided:\n" + context
            context_presented = False
            system_msg = {"role": "system", "content": context_content}
            selected_history.append(system_msg)

    remove_redundant_system_msg(selected_history)
    selected_history.insert(0, {"role": "system", "content": system_prompt})
    response = get_response(query, history=selected_history, provider=provider, model=model, stream=True)
    assistant_content = ""
    for chunk in response:
        if not chunk.choices:
            continue
        chunk_content = chunk.choices[0].delta.content
        if chunk_content is not None:
            print(chunk_content, end="")
            assistant_content += chunk_content

    history.append({"role": "user", "content": query})
    if system_msg:
        history.append(system_msg)
    history.append({"role": "assistant", "content": assistant_content})

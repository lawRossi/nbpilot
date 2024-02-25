from argparse import ArgumentParser
import json
import platform

from IPython.display import display, HTML, Markdown
import markdown
from openai import OpenAI


client = OpenAI()


system_prompt = f"""
You are a helpful AI assistant to help people use jupyter notebook with your language skill and coding skill.
You are provided the content of the notebook and the query of the user. First, analyze the query step by step,
and then generate your answer. You should first refer to the notebook content to find answer. You should write
code to solve the problem when possible. Your code can use variables, functions, and classes defined in the
notebook directly. The os of the jupyter runtime is {platform.platform()}.

Note: Your answer must use Chinese. Your code must be quoted as ```your code```.

The content of the notebook: {{context}}

The index of the current cell is {{cell_index}}.
"""


auto_complete_prompt = """
You are a helpful code auto completer. Given the code already written, you'll try to complete it. You must
keep the style of the code. You *must* start with the last line of the given code and include it in your completion.
Just generate the code without anything else.
Given code:{{context}}
Last line: {{prefix}}
Your completion:
"""


def get_response(user_prompt, system_prompt=None, history=None, model="gpt-3.5-turbo-1106"):
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_prompt})

    response = client.chat.completions.create(
        model=model,
        messages=messages
    )

    return response.choices[0].message.content


def call_copilot_with_context(context, query, cell_id, cell_index, history=None):
    prompt = system_prompt.replace("{context}", context)
    prompt = prompt.replace("{query}", query)
    prompt = prompt.replace("{cell_index}", str(cell_index))
    response = get_response(query, prompt, history)
    response_html = markdown.markdown(response, extensions=['fenced_code'])
    display(HTML(response_html), metadata={"copilot-output": True, "cellId": cell_id, "raw": response})


def call_copilot_without_context(query, cell_id, history=None):
    response = get_response(query, history=history)
    response_html = markdown.markdown(response, extensions=['fenced_code'])
    display(HTML(response_html), metadata={"copilot-output": True, "cellId": cell_id, "raw": response})


def get_completion(context, suffix):
    context = context.strip()
    prefix = context.split("\n")[-1]
    prompt = auto_complete_prompt.replace("{{context}}", context).replace("{{prefix}}", prefix)
    completion = get_response(prompt)

    if not completion.startswith(prefix) or (suffix != ")" and not completion.endswith(suffix)):
        completion = ""
    result = {"context": context, "completion": completion, "suffix": suffix}

    print(json.dumps(result))


def print_help_message():
    arg_parser = ArgumentParser(prog="nbpilot", description="nbpilot commands", add_help=False)
    arg_parser.add_argument("--with_context", action="store_true", help="use the content of the notebook as context")
    arg_parser.add_argument("--history_turns", type=int, default=0, help="number of dialogue history to use")
    arg_parser.add_argument("--exclude", action="store_true", help="exclude a cell from the context")

    arg_parser.print_help()

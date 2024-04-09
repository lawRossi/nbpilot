import re

from IPython import get_ipython
from IPython.display import display
import ipywidgets as widgets

from .llm import get_response


prompt = """You are Nbpilot, your task is to help people with your rich knowledge and world-class programming skill
in a jupyter notebook. For user's each request, you must analyze it carefully and try to derive an answer or a solution
step-by-step.
You must solve the problem by writting code when needed. Befor writting code, write a step-by-step plan.
Then, for each step, you must:
1. Recap your plan of this step briefly.
2. Write all your code of this step in one code block, which is wrapped as ```language\ncode```.
Write code that can run directlly in a jupyter notebook. Just code *without explaination*.
"""

history = []
output_context = widgets.Output(layout={'border': '1px solid black'})


def input_and_show_response(feedback=None):
    if not feedback:
        global input_widget
        global submit_button
        input_widget = widgets.Text(value="", description="User:", layout={"width": "100%"})
        input_widget.on_submit(submit_and_show_response)
        with output_context:
            display(input_widget)
    else:
        request_and_show_response(feedback)


def submit_and_show_response(sender):
    feedback = sender.value
    sender.disable = True
    request_and_show_response(feedback)


def request_and_show_response(feedback):
    res = get_response(user_prompt=feedback, history=history, stream=True, provider="ollama")
    response_widget = widgets.Textarea(value="", description="Assistant:", layout={"width": "100%", "height": "30px"})
    confirm_button = widgets.Button(description="Confirm")
    confirm_button.on_click(lambda _: confirm_assistant_response(response_widget))
    with output_context:
        display(response_widget, confirm_button)
    feedback = None
    for chunk in res:
        if not chunk.choices:
            continue
        chunk_content = chunk.choices[0].delta.content
        if chunk_content is not None:
            response_widget.value += chunk_content


def extract_code_blocks(msg):
    pattern = re.compile("```(.+?)\n(.+?)```", flags=re.S)
    for match in pattern.finditer(msg):
        yield {"language": match.group(1), "code": match.group(2)}


def run_code_blocks(code_blocks):
    result = {"error:": False}
    for i, code_block in enumerate(code_blocks):
        result = get_ipython().run_cell(code_block["code"])
        if not result.success:
            err = result.error_in_exec
            sys_feedback = f"Errors occurred in code block {i+1}: {type(err).__name__} - {str(err)}"
            result = {"error": True, "feedback": sys_feedback}
            return result
    return result


def confirm_assistant_response(response_widget):
    response = response_widget.value
    history.append({"role": "Assistant", "content": response})
    feedback = None
    code_blocks = list(extract_code_blocks(response))
    if code_blocks:
        with output_context:
            feedback = input("run the code?(y/n)>")
        if feedback.lower() in ["y", "yes"]:
            result = run_code_blocks(code_blocks)
            if result["error"]:
                feedback = input("feedback error?(y/n)>")
                if feedback.lower() in ["y", "yes"]:
                    feedback = result["feedback"]
    input_and_show_response(feedback)


def main():
    history.append({"role": "system", "content": prompt})
    input_and_show_response()
    return output_context

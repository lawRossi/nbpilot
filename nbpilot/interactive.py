import re

from IPython import get_ipython
from IPython.display import display
import ipywidgets as widgets

from .custom_widgets import AdaptableTextArea, ConfirmDialog
from .llm import get_response


class Inpteracter:
    prompt = """You are Nbpilot, your task is to help people using your rich knowledge and world-class programming skill
    in a jupyter notebook. For user's each request, you must perform following steps:
    1. Analyze it carefully to see if enough information is provided. If not, suggest more information.
    2. Based on the provided information, try to derive an answer or a solution step-by-step.
    3. Decide whether code is needed to solve the problem. If yes, you must follow these rules:
      - Befor writting code, write a step-by-step plan.
      - For each step, recap the plan of this step, write code to execute it in the form of ```language\ncode```, then
        wait for the feedback from the user.
      - Write code that can run directlly in a jupyter notebook. Just code *without explaination*.
    """

    def __init__(self):
        self.output_context = widgets.Output(layout={'border': '1px solid black'})
        self.input_widget = widgets.Text(value="", description="User:", layout={"width": "80%", "height": "30px"})
        self.input_widget.on_submit(self._submit_and_show_response)
        self.flush_button = widgets.Button(description="Flush")
        self.flush_button.on_click(self.flush)
        self.msg_widgets = []

    def interact(self):
        with self.output_context:
            display(widgets.HBox([self.input_widget, self.flush_button]))
        return self.output_context

    def _get_history(self):
        history = [{"role": "system", "content": self.prompt}]
        for msg_widget in self.msg_widgets:
            msg = {"content": msg_widget.value}
            if isinstance(msg_widget, AdaptableTextArea):
                msg["role"] = "assistant"
            else:
                msg["role"] = "user"
            history.append(msg)
        return history

    def _delete_user_msg(self, msg_widget, button):
        msg_widget.close()
        button.close()
        self.msg_widgets.remove(msg_widget)

    def _submit_and_show_response(self, sender):
        msg = sender.value
        sender.value = ""
        self._send_user_msg(msg)

    def _send_user_msg(self, msg):
        msg_widget = widgets.Label(msg)
        self.msg_widgets.append(msg_widget)
        delete_button = widgets.Button(description="Delete", button_style="danger")
        delete_button.on_click(lambda _: self._delete_user_msg(msg_widget, delete_button))
        with self.output_context:
            display(widgets.HBox([msg_widget, delete_button]))
        self._request_and_show_response(msg)

    def _request_and_show_response(self, msg):
        history = self._get_history()
        res = get_response(user_prompt=msg, history=history, stream=True, provider="ollama")
        response_widget = AdaptableTextArea(value="", description="Assistant:", layout={"width": "80%", "height": "30px"})
        self.msg_widgets.append(response_widget)
        with self.output_context:
            display(response_widget)
        for chunk in res:
            if not chunk.choices:
                continue
            chunk_content = chunk.choices[0].delta.content
            if chunk_content is not None:
                response_widget.value += chunk_content
        response = response_widget.value
        codeblocks = self._extract_code_blocks(response)
        buttons = []
        delete_button = widgets.Button(description="Delete", button_style="danger")
        delete_button.on_click(lambda _: self._delete_assistant_response(response_widget, buttons))
        buttons.append(delete_button)
        if codeblocks:
            run_button = widgets.Button(description="Run", button_style="success")
            run_button.on_click(lambda _: self._run_code(response_widget))
            buttons.append(run_button)
        with self.output_context:
            display(widgets.HBox(buttons))

    def _delete_assistant_response(self, response_widget, buttons):
        response_widget.close()
        self.msg_widgets.remove(response_widget)
        for button in buttons:
            button.close()

    def _extract_code_blocks(self, msg):
        pattern = re.compile("```(.+?)\n(.+?)```", flags=re.S)
        code_blocks = []
        for match in pattern.finditer(msg):
            code_blocks.append({"language": match.group(1), "code": match.group(2)})
        return code_blocks

    def _run_code_blocks(self, code_blocks):
        result = {"error": False}
        for i, code_block in enumerate(code_blocks):
            res = get_ipython().run_cell(code_block["code"])
            if not res.success:
                err = res.error_in_exec or res.error_before_exec
                err_feedback = f"Errors occurred in code block {i+1}: {type(err).__name__} - {str(err)}"
                result = {"error": True, "feedback": err_feedback}
                break
        return result

    def _run_code(self, response_widget):
        response = response_widget.value
        code_blocks = self._extract_code_blocks(response)
        if code_blocks:
            result = self._run_code_blocks(code_blocks)
            if result["error"]:
                feedback = result["feedback"]
                dialog = ConfirmDialog(
                    description="feedback error?",
                    callback=lambda: self._send_user_msg(feedback)
                )
                with self.output_context:
                    display(dialog)

    def flush(self, _):
        self.output_context.clear_output(wait=False)
        self.msg_widgets = []
        with self.output_context:
            display(widgets.HBox([self.input_widget, self.flush_button]))


def main():
    interacter = Inpteracter()
    return interacter.interact()

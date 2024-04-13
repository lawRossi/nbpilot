import ipywidgets as widgets
import markdown


class AdaptableTextArea(widgets.Textarea):
    def __init__(self, value='', **kwargs):
        super().__init__(value=value, **kwargs)
        self.observe(self.on_change)
        self.max_height = kwargs.get("max_height", 300)

    def on_change(self, _):
        value_len = len(self.value)
        height = min(((value_len // 100) + 1) * 30, self.max_height)
        self.layout.height = f"{height}px"


class ConfirmDialog(widgets.VBox):

    def  __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.callback = kwargs.get("callback")
        desc_label = widgets.Label(kwargs.get("description"))
        cancel_button = widgets.Button(description='cancel', button_style='warning', layout=dict(width='auto'))
        confirm_button = widgets.Button(description='confirm', button_style='success', layout=dict(width='auto'))
        cancel_button.on_click(lambda _: self.close())
        confirm_button.on_click(lambda _: self._callback())
        self.children = [desc_label, widgets.HBox([cancel_button, confirm_button])]

    def _callback(self):
        self.callback()
        self.close()


class PreviewTextArea(widgets.HBox):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.textarea = widgets.Textarea("", layout={"width": "30%"})
        self.html = widgets.HTML("")
        self.edit_button = widgets.Button(description="Edit", button_style="info", layout={"width": "10px", "height": "10px"})
        self.edit_button.on_click(lambda _: self.edit())
        self.preview_button = widgets.Button(description="Preview", button_style="info", layout={"width": "10px", "height": "10px"})
        self.preview_button.on_click(lambda _: self.preview())

    @property
    def value(self):
        return self.textarea.value

    @value.setter
    def value(self, value):
        self.textarea.value = value
        self.preview()

    def edit(self):
        self.children = [self.textarea, self.preview_button]

    def preview(self):
        value = self.textarea.value
        self.html.value = markdown.markdown(value, extensions=['fenced_code'])
        self.children = [self.html, self.edit_button]

define([
    'base/js/namespace',
    'base/js/keyboard',
    'jquery',
    'notebook/js/cell',
    'notebook/js/codecell',
    'notebook/js/completer',
    'require',
    './searchcursor'
], function (
    Jupyter,
    keyboard,
    $,
    cell,
    codecell,
    completer,
    requirejs,
    sc
) {
    'use strict';

    var assistActive;

    var config = {
        assist_active: false,
        options_limit: 10,
        assist_delay: 1000
    }

    var logPrefix = '[nbpilot.auto_complete]';

    var Cell = cell.Cell;
    var CodeCell = codecell.CodeCell;
    var Completer = completer.Completer;
    var keycodes = keyboard.keycodes;
    var timer;
    var specials = [
        keycodes.enter,
        keycodes.esc,
        keycodes.backspace,
        keycodes.tab,
        keycodes.up,
        keycodes.down,
        keycodes.left,
        keycodes.right,
        keycodes.shift,
        keycodes.ctrl,
        keycodes.alt,
        keycodes.meta,
        keycodes.capslock,
        // keycodes.space,
        keycodes.pageup,
        keycodes.pagedown,
        keycodes.end,
        keycodes.home,
        keycodes.insert,
        keycodes.delete,
        keycodes.numlock,
        keycodes.f1,
        keycodes.f2,
        keycodes.f3,
        keycodes.f4,
        keycodes.f5,
        keycodes.f6,
        keycodes.f7,
        keycodes.f8,
        keycodes.f9,
        keycodes.f10,
        keycodes.f11,
        keycodes.f12,
        keycodes.f13,
        keycodes.f14,
        keycodes.f15
    ];

    function onlyModifierEvent(event) {
        var key = keyboard.inv_keycodes[event.which];
        return (
            (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) &&
            (key === 'alt' || key === 'ctrl' || key === 'meta' || key === 'shift')
        );
    }

    function getContent(current_cell, editor) {
        var cells = Jupyter.notebook.get_cells();
        var context = "";
        for (let i in cells) {
            var cell = cells[i];
            if (cell == current_cell) {
                continue;
            }
            var cell_type = cell.cell_type;
            if (cell_type !== "code") {
                continue;
            }
            let lines = getCodeLines(cell);
            if (lines !== "") {
                context += lines + "\n";
            }
        }
        let content = getCurrentCellContent(editor);
        context += content.lines;

        return {"context": context, "suffix": content.suffix};
    }

    function getCodeLines(cell) {
        var lines = "";
        var text = cell.get_text().trimEnd();
        if (text.startsWith("%%") || text.startsWith("# call nbpilot #")) {
            return lines;
        }
        text.split("\n").forEach(function(line) {
            if (!line.startsWith("%") && !line.startsWith("!")) {
                lines += line + "\n";
            }
        });
        return lines;
    }

    function getCurrentCellContent(editor) {
        var text = editor.getValue();
        var lines = "";
        if (text.startsWith("%%") || text.startsWith("# call nbpilot #")) {
            return lines;
        }
        var cursor = editor.getCursor();
        var cell_lines = text.split("\n");
        var suffix;
        for (let i in cell_lines) {
            if (i < cursor.line) {
                lines += cell_lines[i] + "\n";
            } else if (i == cursor.line) {
                lines += cell_lines[i].substring(0, cursor.ch);
                suffix = cell_lines[i].substring(cursor.ch);
            }
        }

        return {"lines": lines, "suffix": suffix};
    }


    function getCompletion(cell, editor, handleCompletion) {
        var content = getContent(cell, editor);
        var code = "context='''" + content.context + "'''\nsuffix='" + content.suffix + "'\nget_completion(context, suffix)";
        Jupyter.notebook.kernel.execute(code, {iopub: {output: handleCompletion}}, { silent: false });
    }


    const LLMCompleter = function (cell, events) {
        Completer.call(this, cell, events);
    }
    LLMCompleter.prototype = Object.create(Completer.prototype);
    LLMCompleter.prototype.constructor = LLMCompleter;

    LLMCompleter.prototype.finish_completing = function (msg) {
        if (this.adopted === true) {
            this.adopted = false;
            this.close();
            return;
        }
        console.log("finish");
        if (this.visible && this.completion !== undefined && this.completion !== null) {
            console.info(logPrefix, 'complete is visible, ignore by just return');
            return;
        }

        var editor = this.editor;
        var cursor = editor.getCursor();
        var completer = this;

        getCompletion(completer.cell, editor, function (data) {
            if (data.content.text === "") {
                completer.close();
                console.log(data);
                return;
            }
            var completion = JSON.parse(data.content.text);
            console.log(completion);
            var completion_text = completion["completion"];
            if (completion_text === "") {
                completer.close();
                return;
            }
            var currLineText = editor.getLineHandle(cursor.line).text;
            var prefix = currLineText.substring(0, cursor.ch);
            var suffix = currLineText.substring(cursor.ch);
            if (suffix == ")" && completion_text.indexOf(suffix) != -1) {
                suffix = "";
                completion.suffix = "";
                let end = {"line": cursor.line, "ch": cursor.ch + 1};
                editor.replaceRange("", cursor, end);
            }
            if (!completion_text.startsWith(prefix) || suffix != completion.suffix) {
                console.log("not equal");
                completer.close();
                return;
            }
            completer.visible = true;
            completer.completion = completion;
            completer.previewCompletion();
            completer.add_keyevent_listeners()
        });
        return true;
    }

    LLMCompleter.prototype.previewCompletion = function() {
        var editor = this.editor;
        var completion_text = this.completion.completion;
        var cursor = editor.getCursor();
        var currLineText = editor.getLineHandle(cursor.line).text;
        var prefix = currLineText.substring(0, cursor.ch);
        var start = prefix.length;
        var end = completion_text.length-this.completion.suffix.length;
        completion_text = completion_text.substring(start, end);
        editor.replaceRange(completion_text, cursor);
        var end = editor.getCursor();
        var marker = editor.markText(cursor, end, {css: "color: gray", className: "completion"});
        marker.from = {"line": cursor.line, "ch": cursor.ch};
        marker.to = {"line": end.line, "ch": end.ch};
        marker.text = completion_text;
        this.completion.marker = marker;
        editor.setCursor(cursor);
    }

    LLMCompleter.prototype.removePreview = function(ignoreCursor) {
        if (this.completion && this.completion.marker !== null) {
            let marker = this.completion.marker
            if (ignoreCursor) {
                this.editor.replaceRange("", marker.from, marker.to);
                return;
            } else {
                let cursor = this.editor.getCursor();
                let from = marker.from;
                if (cursor.line == from.line && cursor.ch == from.ch) {
                    let text = this.editor.getRange(marker.from, marker.to);
                    if (text == marker.text) {
                        this.editor.replaceRange("", marker.from, marker.to);
                    }
                } else {
                    let start = {"line": cursor.line, "ch": cursor.ch};
                    if (marker.text.indexOf("\n") != -1) {
                        start.ch -= 1;
                    }
                    let previewCursor = this.editor.getSearchCursor(marker.text, start);
                    if (!previewCursor.findNext()) {
                        console.log("preview not found");
                        return;
                    }
                    start = previewCursor.from();
                    var end = previewCursor.to();
                    this.editor.replaceRange("", start, end);
                }
            }
            this.completion.marker = null;
        }
    }

    LLMCompleter.prototype.update = function () {
        console.log("update");
        var completion = this.completion;
        var editor = this.editor;
        if (!completion) {
            this.close();
            return;
        }
        this.removePreview(false);
        var cursor = editor.getCursor();
        var currLineText = editor.getLineHandle(cursor.line).text;
        var prefix = currLineText.substring(0, cursor.ch);
        if (!completion.completion.startsWith(prefix)) {
            this.close();
            return;
        }
        var completion_text = completion.completion.substring(prefix.length);
        if (completion_text == "") {
            this.close();
            return;
        }
        this.previewCompletion();
    };

    LLMCompleter.prototype.close = function () {
        this.removePreview(true);
        this.done = true;
        this.editor.off('keydown', this._handle_keydown);
        this.visible = false;
        this.completion = null;
        this.editor.off('keyup', this._handle_key_up);
    };

    LLMCompleter.prototype.add_mouse_listeners = function () {
        var completer = this;
        this._handle_mouse_down = function(cm, event) {
            completer.removePreview(true);
            completer.close();
        }
        this.editor.on("mousedown", this._handle_mouse_down);
    }

    LLMCompleter.prototype.add_keyevent_listeners = function () {
        var editor = this.editor;
        this.isKeyupFired = true;  // make keyup only fire once
        var completer = this;
        this._handle_keydown = function (cm, event) { // define as member method to handle close
            // since some opration is async, it's better to check whether complete is existing or not.
            if (!completer.completion) {
                editor.off('keydown', completer._handle_keydown);
                editor.off('keyup', completer._handle_handle_keyup);
                return;
            }
            completer.isKeyupFired = false;
            if (event.keyCode == keycodes.tab || event.keyCode == keycodes.enter) {
                event.codemirrorIgnore = true;
                event._ipkmIgnore = true;
                event.preventDefault();
                // it's better to prevent enter key when completions being shown
                if (event.keyCode == keycodes.enter) {
                    completer.removePreview(false);
                    completer.close();
                    return;
                }
                var completion = completer.completion;
                var completion_text = completion.completion;
                var suffix = completion.suffix;
                var cursor = editor.getCursor();
                var currLineText = editor.getLineHandle(cursor.line).text;
                var prefix = currLineText.substring(0, cursor.ch);
                if (!completion_text.startsWith(prefix) || !currLineText.endsWith(suffix)) {
                    completer.close(false);
                    return;
                }
                completion_text = completion_text.substring(prefix.length);
                let start = {"line": cursor.line, "ch": cursor.ch - 1};
                let previewCursor = editor.getSearchCursor(completion_text, start);
                if (!previewCursor.findNext()) {
                    completer.close();
                    return;
                }
                start = previewCursor.from();
                let end = previewCursor.to();
                if (suffix.length > 0) {
                    completion_text = completion_text.substring(0, completion_text.length-suffix.length);
                    end.ch -= suffix.length;
                }
                editor.replaceRange(completion_text, start, end);
                completion.marker = null;
                completer.adopted = true;
                completer.close();
                return;
            } else if (needUpdateComplete(event.keyCode)) {
                // Let this be handled by keyup, since it can get current pressed key.
            } else {
                completer.removePreview(false);
                completer.close();
            }
        }

        this._handle_keyup = function (cm, event) {
            if (!completer.isKeyupFired && !event.altKey &&
                !event.ctrlKey && !event.metaKey && needUpdateComplete(event.keyCode)) {
                completer.update();
                completer.isKeyupFired = true;
            };
        };

        editor.on('keydown', this._handle_keydown);
        editor.on('keyup', this._handle_keyup);
    };



    function isAlphabeticKeyCode(keyCode) {
        return keyCode >= 65 && keyCode <= 90;
    }

    function isNumberKeyCode(keyCode) {
        return (keyCode >= 48 && keyCode <= 57) || (keyCode >= 96 && keyCode <= 105);
    }

    function isOperatorKeyCode(keyCode) {
        return (keyCode >= 106 && keyCode <= 111) ||
            (keyCode >= 186 && keyCode <= 192) ||
            (keyCode >= 219 && keyCode <= 222);
    }

    function needUpdateComplete(keyCode) {
        return isAlphabeticKeyCode(keyCode) || isNumberKeyCode(keyCode) || isOperatorKeyCode(keyCode);
    }

    function patchCellKeyevent() {
        var origHandleCodemirrorKeyEvent = Cell.prototype.handle_codemirror_keyevent;
        Cell.prototype.handle_codemirror_keyevent = function (editor, event) {
            if (!this.llm_completer) {
                console.log(logPrefix, ' new llm completer');
                this.llm_completer = new LLMCompleter(this, this.events)
                this.completer = this.llm_completer;
                this.completer.add_mouse_listeners();
            }

            if (assistActive && !event.altKey && !event.metaKey && !event.ctrlKey
                && (this instanceof CodeCell) && !onlyModifierEvent(event)) {
                this.tooltip.remove_and_cancel_tooltip();
                if (!editor.somethingSelected() &&
                    editor.getSelections().length <= 1 &&
                    !this.completer.visible &&
                    specials.indexOf(event.keyCode) == -1) {
                    if (timer) {
                        console.log("timer:" + timer);
                        clearTimeout(timer);
                        timer = null;
                    }
                    var cell = this;
                    if (!event.tabKey && event.keyCode !== keycodes.tab) {
                        timer = setTimeout(function() {cell.completer.startCompletion();}, config.assist_delay);
                    }
                }
            }
            return origHandleCodemirrorKeyEvent.apply(this, arguments);
        };
    }

    function setAssistState(newState) {
        assistActive = newState;
        $('.assistant-toggle > .fa').toggleClass('fa-check', assistActive);
        console.log(logPrefix, 'continuous autocompletion', assistActive ? 'on' : 'off');
    }

    function toggleAutocompletion() {
        setAssistState(!assistActive);
    }

    function addMenuItem() {
        if ($('#help_menu').find('.assistant-toggle').length > 0) {
            return;
        }
        var menuItem = $('<li/>').insertAfter('#keyboard_shortcuts');
        var menuLink = $('<a/>').text('Nbpilot')
            .addClass('assistant-toggle')
            .attr('title', 'Provide continuous code autocompletion')
            .on('click', toggleAutocompletion)
            .appendTo(menuItem);
        $('<i/>').addClass('fa menu-icon pull-right').prependTo(menuLink);
    }


    function load_notebook_extension() {
        return Jupyter.notebook.config.loaded.then(function on_success() {
            $.extend(true, config, Jupyter.notebook.config.data.nbpilot);
        }, function on_error(err) {
            console.warn(logPrefix, 'error loading config:', err);
        }).then(function on_success() {
            patchCellKeyevent();
            addMenuItem();
            setAssistState(config.assist_active);
        });
    }

    return {
        load: load_notebook_extension
    };
});

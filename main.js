define([
    'jquery',
    'base/js/namespace',
    'base/js/events',
    'notebook/js/codecell',
    'notebook/js/outputarea',
    './auto_complete'
], function(
    $,
    Jupyter,
    events,
    codecell,
    oa,
    ac
) {
    "use strict";

    var mod_name = "nbpilot";
    var log_prefix = '[' + mod_name + '] ';

    var config = {
        module: 'nbpilot.py'
    }

    var st = {}
    st.code = "";
    var CodeCell = codecell.CodeCell;
    var nbpilot_command_prefix = "#nbpilot";
    var valid_args = ["--with_context", "--exclude", "--history_turns"]
    var processed = {};

    function code_exec_callback(msg) {
        if (msg.msg_type === "error") {
            console.log(msg);
            console.log("reload");
            nbpilotInit();
        } else {
            console.log("python module loaded");
        }
    }

    function patchCodeCellExecute () {
        var old_execute = CodeCell.prototype.execute;
        CodeCell.prototype.execute = function () {
            var cell = this;
            var code = cell.get_text();
            if (code.startsWith(nbpilot_command_prefix)) {
                let lines = code.split("\n");
                let arg_string = lines[0].replace(nbpilot_command_prefix, "").trim();
                let arg_name = "";
                if (arg_name === undefined) {
                    new_code = "print_help_message";
                } else {
                    var cellId = new Date().getTime().toString();
                    cell.metadata["cellId"] = cellId;
                    var context = readContext(cell);
                    var query = code.replace(nbpilot_command_prefix, "").trim();
                    var history = readHistory(cell, true, 5);
                    var new_code = "context='''" + context.context+ "'''\nquery='''" + query;
                    new_code += "'''\nhistory=" + history + "\n"
                    new_code += "call_copilot_with_context(context, query,\"" + cellId + "\"," + context.cell_index + ", history)";
                    console.log(new_code);
                    cell.set_text(new_code);
                    old_execute.apply(this, arguments);
                    cell.set_text(code);
                }
            } else {
                old_execute.apply(this, arguments);
            }
        };
    }

    function adoptCode(event, cellId) {
        console.log(cellId);
        if (processed[cellId] === true) {
            return;
        }

        var code = "";
        var codes = $("div#"+cellId).find("code");
        let i = 0;
        while (i < codes.length) {
            console.log(codes[i]);
            code += $(codes[i]).text() + "\n\n";
            i += 1;
        }
        code = code.trim();

        let cells = Jupyter.notebook.get_cells();
        for (let i in cells) {
            console.log(cells[i].metadata);
            if (cells[i].metadata["cellId"] === cellId) {
                Jupyter.notebook.select(parseInt(i));
                Jupyter.notebook.focus_cell();
                break;
            }
        }
        Jupyter.notebook.insert_cell_below("code").set_text(code);
        Jupyter.notebook.select_next();
        Jupyter.notebook.focus_cell();
        processed[cellId] = true;
    }

    function patchHandleOutput() {
        var old_handle_output = oa.OutputArea.prototype.handle_output;
        oa.OutputArea.prototype.handle_output = function (msg) {
            var msg_type = msg.header.msg_type;
            if (msg_type === "display_data" && msg.content.metadata["copilot-output"] !== undefined) {
                if (msg.metadata["processed"] === true) {
                    return ;
                }
                let html = msg.content.data["text/html"];
                delete(msg.content.data["text/plain"]);
                let id = msg.content.metadata["cellId"];
                let button = '<button onclick="Jupyter.notebook.events.trigger(\'adoptCode\',\'' +  id + '\');">采用结果</button>';
                html = '<div id="' + id + '">' + html + button + "</div>";
                msg.content.data["text/html"] = html;
                msg.metadata["processed"] = true;
                this.append_output({
                    "output_type": "display_data",
                    "metadata": msg.content.metadata,
                    "data": msg.content.data
                });
            } else {
                return old_handle_output.apply(this, arguments);
            }
        };
    }

    function readContext(current_cell) {
        var cells = Jupyter.notebook.get_cells();
        var context = "";
        var cell_index;
        for (let i in cells) {
            var cell = cells[i];
            if (cell === current_cell) {
                cell_index = parseInt(i) + 1;
            }
            context += formatCellContent(cell, i) + "\n";
        }
        console.log(cell_index);
        return {"context": context, "cell_index": cell_index};
    }


    function formatCellContent(cell, cell_index) {
        let index = parseInt(cell_index) + 1;
            var cell_content = "<cell>\n" + "index:" + index + "\n"
        var cell_type = cell.cell_type;
        cell_content += "cell type:" +  cell_type + "\n";
        var text = cell.get_text().trim();
        cell_content += cell_type + ":";
        if (text !== "" && !text.startsWith(nbpilot_command_prefix)) {
            if (cell_type === "code") {
                cell_content += "```" + text + "```\n";
            } else {
                cell_content += text + "\n";
            }
            if (cell_type != "markdown" && cell.output_area !== undefined) {
                cell_content += "output:\n"
                var outputs = cell.output_area.outputs;
                for (let j in outputs) {
                    var output = outputs[j];
                    if (output.output_type == "stream") {
                        if (output.text !== "") {
                            cell_content += output.text.trim() + "\n";
                        }
                    } else if (output.output_type == "error") {
                        cell_content += output.ename + ":" + output.evalue + "\n";
                    } else if (output.output_type == "display_data") {
                        if (output.metadata["raw"] !== undefined) {
                            cell_content += output.metadata["raw"];
                        } else {
                            cell_content += output.data["text/plain"];
                        }
                    }
                }
            }
        }
        cell_content += "</cell>"

        return cell_content;
    }

    function readHistory(current_cell, with_context, turns) {
        var cells = Jupyter.notebook.get_cells();
        var history = [];
        for (let i in cells) {
            let cell = cells[i];
            if (cell === current_cell) {
                break;
            }
            let text = cell.get_text();
            if (text.startsWith(nbpilot_command_prefix)) {
                let command = text.split("\n")[0];
                let idx = command.indexOf("--with_context");
                if (!with_context && idx == -1 || with_context && idx > -1) {
                    var turn = formatTurn(cell);
                    if (turn.bot !== undefined && turn.user !== undefined) {
                        history.push({"role": "user", "content": turn.user});
                        history.push({"role": "assistant", "content": turn.bot});
                    }
                }
            }
        }
        return JSON.stringify(history.slice(-2*turns));
    }

    function formatTurn(cell) {
        var turn = {};
        if (cell.output_area !== undefined) {
            var outputs = cell.output_area.outputs;
            for (let i in outputs) {
                let output = outputs[i];
                console.log(output);
                if (output.output_type == "display_data") {
                    if (output.metadata["raw"] !== undefined) {
                        turn.bot = output.metadata["raw"];
                    }
                }
            }
        }
        if (turn.bot) {
            var text = cell.get_text();
            var lines = text.split("\n");
            turn.user = lines.slice(1).join("\n");
        }
        return turn;
    }

    var nbpilotInit = function() {
        function read_code_init(module) {
            if (st.code !== "") {
                Jupyter.notebook.kernel.execute(st.code, {iopub: {output: code_exec_callback}}, { silent: false });
            } else {
                var moduleName = Jupyter.notebook.base_url + "nbextensions/nbpilot/" + module;
                $.get(moduleName).done(function(data) {
                    st.code = data;
                    Jupyter.notebook.kernel.execute(st.code, {iopub: {output: code_exec_callback}}, { silent: false });
                }).fail(function() {
                    console.log(log_prefix + 'failed to load ' + lib + ' library');
                });
            }
        }

        if (typeof Jupyter.notebook.kernel !== "undefined" && Jupyter.notebook.kernel !== null) {
            read_code_init(config.module);
            patchCodeCellExecute();
            patchHandleOutput();
            console.log("nbpilot loaded");
        } else {
            console.warn(log_prefix + "Kernel not available?");
        }

        events.on("adoptCode", adoptCode);
    }

    var load_jupyter_extension = function() {
        if (typeof Jupyter.notebook.kernel !== "undefined" && Jupyter.notebook.kernel !== null) {
            nbpilotInit();
        }

        events.on("kernel_ready.Kernel", function(evt, data) {
            console.log("kernel ready!!!");
            nbpilotInit();
        });

        ac.load();
    };

    return {
        load_ipython_extension: load_jupyter_extension,
        load_jupyter_extension: load_jupyter_extension
    };
});

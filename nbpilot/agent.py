import json
import re

from loguru import logger

from .llm import get_response


sys_prompt = """## Role
You are {{role}}. Your task is to {{task}}.

## Tools
{{tools}}

## Constraints
1. You can only use tools that are provided.
2. Use only one tool at once.
3. You must provide correct parameters of the tools.
4. If you can not get the necessary information by using provided tools, don't make up.

## Workflow 
1. Judge whether you need to use tools to collect message. If so, for each tool, apply it and wait for the user to feedback the result.
2. If necessary information is collected, respond to the user based on it. Otherwise, say "no information provided".

## Output
When appling a tool, you must output in this format: "ToolUsage: {tool_name}({parameters})" (without anything else).
"""

class Tool:
    def __init__(self, name, parameters, description, example):
        self.name = name
        self.parameters = parameters
        self.description = description
        self.example = example

    def __call__(self, stock_name="") -> str:
        return ""


class Agent:
    def __init__(self, tools, role=None, task=None):
        self.tools = {}
        for tool in tools:
            self.tools[tool.name] = tool
        role = role or "a helpful AI assistant"
        task = task or "help people with the help of provided tools"
        tool_list = self.format_tools(tools)
        self.sys_prompt = sys_prompt.replace("{{role}}", role).replace("{{task}}", task).replace("{{tools}}", tool_list)
        self.history = [{"role": "system", "content": self.sys_prompt}]
        self.tool_usage_pattern = re.compile("ToolUsage:\s?{?(?P<tool_name>[a-zA-Z0-9-_]+)}?\((?P<parameters>[^)]+)\)")

    def format_tools(self, tools):
        tool_list = ""
        for i, tool in enumerate(tools):
            parameters = ",".join(tool.parameters)
            tool_list += f"{i+1}. tool_name:{tool.name} description:{tool.description} parameters:{parameters} usage example：{tool.example}。\n"
        return tool_list.strip()

    def parse_tool_usage(self, response):
        m = self.tool_usage_pattern.search(response)
        if m:
            tool_name = m.group("tool_name")
            parameters = [split.strip('"') for split in m.group("parameters").split(",")]
            return {"tool_name": tool_name, "parameters": parameters}
        return None

    def run(self, query, max_errors=3, provider="deepseek", model=None, debug=False):
        errors = 0
        response = None
        while errors < max_errors:
            response = get_response(query, history=self.history, stream=False, provider=provider, model=model, debug=debug)
            tool_usage = self.parse_tool_usage(response)
            tool_output = None
            if tool_usage:
                logger.debug(json.dumps(tool_usage, ensure_ascii=False))
                tool = self.tools.get(tool_usage["tool_name"])
                if not tool:
                    errors += 1
                    continue
                try:
                    result = tool(*tool_usage["parameters"])
                    tool_output = "ToolOutput:" + result
                    logger.debug(tool_output)
                except:
                    errors += 1
                    continue
            self.history.append({"role": "user", "content": query})
            self.history.append({"role": "assistant", "content": response})
            if tool_output:
                query = tool_output
            else:
                break

        return response

    def reset(self):
        self.history = [{"role": "system", "content": self.sys_prompt}]

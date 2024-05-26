import json
import re

from loguru import logger

from .llm import get_response


agent_sys_prompt = """## Role
You are {{role}}. Your task is to {{task}}.

## Tools
{{tools}}

## Constraints
- You can only use tools that are provided.
- Use only one tool at once.
- You must provide correct parameters of the tools.
- If you can not get the necessary information by using provided tools, don't make up.

## Workflow 
1. Think step by step, judge whether you need to use tools to collect message or perform tasks. 
If so, for each tool, apply it and wait for feedback.
2. If necessary information is collected, respond to the user based on it. Your response must be clear and complete.

## Output
When appling a tool, you must output in this format: "ToolUsage: {tool_name}({parameters})"
"""


assisted_agent_sys_prompt = """## Role
You are {{role}}. Your task is to {{task}}. You have some assistants who you can turn to when you need help.

## Tools
{{tools}}

## Assistants
{{assistant}}

## Constraints
- You can only use tools that are provided and talk to assistants that are listed.
- Use only one tool or talk to only one assistant at once.
- You must provide correct parameters of the tools.
- If you can not get the necessary information by using provided tools or through assistants, don't make up.

## Workflow 
1. Think step by step, judge whether you need to query assistants. If so, for each assitant, speak to it and wait for feedback.
2. Think step by step, judge whether you need to use tools to collect message. If so, for each tool, apply it and wait for feedback.
3. If necessary information is collected, respond to the user based on it. Your response must be clear and complete.

## Output
1. When appling a tool, your output must be in this format: "ToolUsage: {tool_name}({parameters})" (without anything else).
2. When speaking to an assistant, your output must be in this format: "SpeakTo {assistant_name}:{utterance}".
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
    tool_usage_pattern = re.compile("ToolUsage:\s?\{?(?P<tool_name>[a-zA-Z0-9-_]+)\}?\((?P<parameters>[^)]+)\)")

    def __init__(self, tools, name=None, role=None, task=None, description=None):
        self.tools = {}
        for tool in tools:
            self.tools[tool.name] = tool
        self.name = name
        self.role = role or "a helpful AI assistant"
        self.task = task or "help people with the help of provided tools"
        self._format_sys_prompt()
        self.history = [{"role": "system", "content": self.sys_prompt}]
        self.description = description

    def _format_sys_prompt(self):
        tool_list = self._format_tools(list(self.tools.values()))
        sys_prompt = agent_sys_prompt.replace("{{role}}", self.role)
        sys_prompt = sys_prompt.replace("{{task}}", self.task)
        sys_prompt = sys_prompt.replace("{{tools}}", tool_list)
        self.sys_prompt = sys_prompt

    def _format_tools(self, tools):
        tool_list = ""
        for i, tool in enumerate(tools):
            parameters = ",".join(tool.parameters)
            tool_list += f"{i+1}. tool_name:{tool.name} description:{tool.description} parameters:{parameters} usage example：{tool.example}。\n"
        return tool_list.strip()

    def _parse_tool_usage(self, response):
        m = self.tool_usage_pattern.search(response)
        if m:
            tool_name = m.group("tool_name")
            parameters = [split.strip('"') for split in m.group("parameters").split(",")]
            return {"tool_name": tool_name, "parameters": parameters}
        return None

    def _trim_response(self, response):
        m = self.tool_usage_pattern.search(response)
        return response[:m.end()+1]

    def _apply_tool(self, tool_usage):
        logger.debug(json.dumps(tool_usage, ensure_ascii=False))
        tool = self.tools.get(tool_usage["tool_name"])
        if not tool:
            return None
        try:
            result = tool(*tool_usage["parameters"])
            tool_output = f"Output of {tool.name}:" + result
            logger.debug(tool_output)
            return tool_output
        except:
            return None

    def run(self, query, max_errors=3, provider="deepseek", model=None, debug=False):
        errors = 0
        response = None
        tool_called = False
        while errors < max_errors:
            if not tool_called:
                response = get_response(query, history=self.history, stream=False, 
                                        provider=provider, model=model, debug=debug)
            else:
                response = get_response(system_prompt=query, history=self.history, stream=False, 
                                        provider=provider, model=model, debug=debug)
            tool_usage = self._parse_tool_usage(response)
            tool_output = None
            if tool_usage:
                response = self._trim_response(response)
                tool_output = self._apply_tool(tool_usage)
                if tool_output is None:
                    errors += 1
                    response = None
                    continue
            role = "user" if not tool_called else "system"
            self.history.append({"role": "user", "content": query})
            self.history.append({"role": "assistant", "content": response})
            if tool_output:
                tool_called = True
                query = tool_output
            else:
                break

        return response

    def reset(self):
        self.history = [{"role": "system", "content": self.sys_prompt}]


class AssistedAgent(Agent):
    assistant_query_pattern = re.compile("SpeakTo\s?\{?(?P<name>[a-zA-Z0-9_-]+)\}?:\{?(?P<utterance>.+)\}?")
    assistant_response_prefix = "Response from "

    def __init__(self, tools, assistants, role=None, task=None, description=None):
        self.assistants = {}
        for assistant in assistants:
            self.assistants[assistant.name] = assistant
        super().__init__(tools, role, task, description)
        self.format_sys_prompt()
        self.history = [{"role": "system", "content": self.sys_prompt}]

    def format_sys_prompt(self):
        tool_list = self._format_tools(self.tools.values())
        assistant_list = self._format_assistants(self.assistants.values())
        sys_prompt = assisted_agent_sys_prompt.replace("{{role}}", self.role)
        sys_prompt = sys_prompt.replace("{{task}}", self.task)
        sys_prompt = sys_prompt.replace("{{tools}}", tool_list)
        sys_prompt = sys_prompt.replace("{{assistant}}", assistant_list)
        self.sys_prompt = sys_prompt

    def _format_assistants(self, assistants):
        assistant_list = ""
        for i, tool in enumerate(assistants):
            assistant_list += f"{i+1}. name:{tool.name} description:{tool.description}\n"
        return assistant_list.strip()

    def _parse_assistant_query(self, response):
        m = self.assistant_query_pattern.search(response)
        if not m:
            return None
        assistant_query = {
            "assistant_name": m.group("name"),
            "utterance": m.group("utterance")
        }
        return assistant_query

    def _query_assistant(self, assistant_query):
        logger.debug(json.dumps(assistant_query, ensure_ascii=False))
        assistant = self.assistants.get(assistant_query["assistant_name"])
        if not assistant:
            return None
        try:
            result = assistant.run(assistant_query["utterance"])
            if not result:
                return None
            assistant_response = self.assistant_response_prefix + assistant.name + ":" + result
            logger.debug(assistant_response)
            return assistant_response
        except:
            return None

    def _trim_assistant_response(self, response):
        m = self.assistant_query_pattern.search(response)
        idx = response.find(self.assistant_response_prefix, m.end())
        if idx != -1:
            return response[:idx+1]
        return response

    def run(self, query, max_errors=3, provider="deepseek", model=None, debug=False):
        errors = 0
        response = None
        tool_called = False
        assistant_called = False
        while errors < max_errors:
            if not tool_called and not assistant_called:
                response = get_response(query, history=self.history, stream=False,
                                        provider=provider, model=model, debug=debug)
            else:
                response = get_response(system_prompt=query, history=self.history, stream=False, 
                                        provider=provider, model=model, debug=debug)
            tool_usage = self._parse_tool_usage(response)
            tool_output = None
            assistant_response = None
            if tool_usage:
                response = self._trim_response(response)
                tool_output = self._apply_tool(tool_usage)
                if tool_output is None:
                    errors += 1
                    response = None
                    continue
            else:
                assistant_query = self._parse_assistant_query(response)
                if assistant_query:
                    response = self._trim_assistant_response(response)
                    assistant_response = self._query_assistant(assistant_query)
                    if assistant_response is None:
                        errors += 1
                        response = None
                        continue
            role = "system" if tool_called or assistant_called else "user"
            self.history.append({"role": role, "content": query})
            self.history.append({"role": "assistant", "content": response})
            if tool_output or assistant_response:
                query = tool_output or assistant_response
                if tool_output:
                    tool_called = True
                    assistant_called = False
                else:
                    tool_called = False
                    assistant_called = True
            else:
                break

        return response

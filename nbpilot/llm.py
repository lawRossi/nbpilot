import json

import dashscope 
from litellm import completion
from litellm.utils import Choices, Delta, Message, ModelResponse, StreamingChoices
from loguru import logger

from .config import load_config


def get_response(
        user_prompt=None,
        system_prompt=None,
        history=None,
        stream=False,
        provider="qwen",
        model=None,
        debug=False):
    config = load_config()
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if user_prompt:
        messages.append({"role": "user", "content": user_prompt})
    if history:
        messages = history + messages

    if debug:
        logger.debug(json.dumps(messages, ensure_ascii=False))

    llm_config = config["llm"][provider]
    if provider == "qwen":
        response = dashscope.Generation.call(
            api_key=llm_config["api_key"],
            model=model or llm_config["model_name"],
            messages=messages,
            stream=stream,
            result_format='message'
        )
        response = wrap_response(response) if not stream else wrap_stream_response(response) 
    else:
        response = completion(
            base_url=llm_config["base_url"],
            api_key=llm_config.get("api_key"),
            api_version=llm_config.get("api_version"),
            model=model or llm_config["model_name"],
            messages=messages,
            stream=stream
        )
    if not stream:
        return response.choices[0].message["content"]
    return response


def wrap_response(response):
    choice = response.output.choices[0]
    message = choice.message
    msg = Message(message.content, message.role)
    new_response = ModelResponse()
    new_response.choices = [Choices(choice.finish_reason, message=msg)]

    return new_response


def wrap_stream_response(response):
    content = ""
    for i, chunk in enumerate(response):
        msg = chunk.output.choices[0].message
        delta = Delta(msg.content[len(content):], role=msg.role)
        content = msg.content
        choices = StreamingChoices(chunk.output.finish_reason, i, delta)
        new_chunk = ModelResponse(stream=True)
        new_chunk.choices = [choices]
        yield new_chunk

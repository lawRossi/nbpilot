import json

from litellm import completion
from loguru import logger

from .config import load_config


def get_response(
        user_prompt=None,
        system_prompt=None,
        history=None,
        stream=False,
        provider="ollama",
        model=None,
        debug=True):
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
    response = completion(
        base_url=llm_config["base_url"],
        api_key=llm_config.get("api_key"),
        api_version=llm_config.get("api_version"),
        model=model if model is not None else llm_config["model_name"],
        messages=messages,
        stream=stream
    )
    if not stream:
        return response.choices[0].message["content"]
    return response

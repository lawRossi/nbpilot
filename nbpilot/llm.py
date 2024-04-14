from litellm import completion

from .config import load_config


def get_response(
        user_prompt=None,
        system_prompt=None,
        history=None,
        stream=False,
        provider="ollama",
        model=None):
    config = load_config()
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if user_prompt:
        messages.append({"role": "user", "content": user_prompt})
    if history:
        messages = history + messages
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

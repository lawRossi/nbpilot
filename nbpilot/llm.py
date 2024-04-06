from litellm import completion

from .config import load_config


def get_response(user_prompt, system_prompt=None, history=None, stream=False, provider="openai"):
    config = load_config()
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_prompt})
    llm_config = config["llm"][provider]
    response = completion(
        base_url=llm_config["base_url"],
        api_key=llm_config.get("api_key"),
        api_version=llm_config.get("api_version"),
        model=llm_config["model_name"],
        messages=messages,
        stream=stream
    )
    if not stream:
        return response.choices[0].message.content
    return response

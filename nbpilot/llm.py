import copy
import json

import dashscope 
from litellm import completion
from litellm.utils import Choices, Delta, Message, ModelResponse, StreamingChoices
from loguru import logger
from openai import OpenAI
from openai.resources.chat.completions import ChatCompletion, ChatCompletionChunk, Stream
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.hunyuan.v20230901 import hunyuan_client, models

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

    llm_config = copy.deepcopy(config["llm"][provider])
    if model:
        llm_config["model"] = model

    if provider == "qwen":
        response = get_qwen_response(llm_config, messages, stream)
    elif provider == "hunyuan":
        response = get_hunyuan_response(llm_config, messages, stream)
    elif provider == "mini_max":
        response = get_minimax_response(llm_config, messages, stream)
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
        return response.choices[0].message.content
    return response


def get_qwen_response(llm_config, ):
    response = dashscope.Generation.call(
        api_key=llm_config["api_key"],
        model=llm_config["model_name"],
        messages=messages,
        stream=stream,
        result_format='message'
    )
    response = wrap_response(response) if not stream else wrap_stream_response(response)
    return response


def wrap_qwen_response(response):
    choice = response.output.choices[0]
    message = choice.message
    msg = Message(message.content, message.role)
    new_response = ModelResponse()
    new_response.choices = [Choices(choice.finish_reason, message=msg)]

    return new_response


def wrap_qwen_stream_response(response):
    content = ""
    for i, chunk in enumerate(response):
        msg = chunk.output.choices[0].message
        delta = Delta(msg.content[len(content):], role=msg.role)
        content = msg.content
        choices = StreamingChoices(chunk.output.finish_reason, i, delta)
        new_chunk = ModelResponse(stream=True)
        new_chunk.choices = [choices]
        yield new_chunk


def get_hunyuan_response(llm_config, messages, stream):
    api_key = llm_config["api_key"]
    cred = credential.Credential(api_key["secret_id"], api_key["secret_key"])
    httpProfile = HttpProfile()
    httpProfile.endpoint = llm_config["base_url"]

    clientProfile = ClientProfile()
    clientProfile.httpProfile = httpProfile
    client = hunyuan_client.HunyuanClient(cred, "", clientProfile)

    req = models.ChatCompletionsRequest()
    new_messages = []
    for message in messages:
        new_messages.append({k.capitalize(): v for k, v in message.items()})
    params = {
        "Model": llm_config["model_name"],
        "Messages": new_messages,
        "Stream": stream
    }
    req.from_json_string(json.dumps(params))
    response = client.ChatCompletions(req)
    if stream:
        return wrap_hunyuan_stream_response(response)
    else:
        return wrap_hunyuan_response(response)


def wrap_hunyuan_response(response):
    choice = response.Choices[0]
    message = choice.Message
    msg = Message(message.Content, message.Role)
    new_response = ModelResponse()
    new_response.choices = [Choices(choice.FinishReason, message=msg)]

    return new_response


def wrap_hunyuan_stream_response(response):
    for i, chunk in enumerate(response):
        data = json.loads(chunk["data"])
        msg = data["Choices"][0]
        delta_ = msg["Delta"]
        delta = Delta(delta_["Content"], role=delta_["Role"])
        choices = StreamingChoices(msg["FinishReason"], i, delta)
        new_chunk = ModelResponse(stream=True)
        new_chunk.choices = [choices]
        yield new_chunk


def get_minimax_response(llm_config, messages, stream):
    client = OpenAI(base_url=llm_config["base_url"], api_key=llm_config["api_key"])
    response = client.chat.completions._post(
        "", body={"messages": messages, "model": llm_config["model_name"], "stream": stream, "max_tokens": 4096},
        cast_to=ChatCompletion, stream=stream, stream_cls=Stream[ChatCompletionChunk]
    )
    return response

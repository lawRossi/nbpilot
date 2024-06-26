import json

import requests
from tavily import TavilyClient

from .config import load_config


config = load_config()
tavily = TavilyClient(api_key=config["tools"]["search"]["tavily_search_api_key"])


def get_search_results(query, engine="ms", max_tokens=None):
    if engine == "ms":
        search_url = "https://api.bing.microsoft.com/v7.0/search"
        headers = {"Ocp-Apim-Subscription-Key": config["tools"]["search"]["azure_search_api_key"]}
        params = {"q": query, "mkt": "en-US"}
        response = requests.get(search_url, headers=headers, params=params, timeout=5)
        response.raise_for_status()
        search_results = response.json()
        search_results = search_results["webPages"]["value"]
        for result in search_results:
            result["title"] = result["name"]
            del result["name"]
            result["content"] = result["snippet"]
            del result["snippet"]
    elif engine == "tavily":
        if max_tokens is None:
            response = tavily.search(
                query=query, search_depth="advanced", max_results=10, include_domains=None,
                exclude_domains=None
            )
            search_results = response["results"]
        else:
            response = tavily.get_search_context(
                query=query, search_depth="advanced", max_tokens=max_tokens, max_results=10,
                include_domains=None, exclude_domains=None
            )
            search_results = [json.loads(result) for result in json.loads(response)]

    return search_results


def fetch_webpage_content(url, timeout=20):
    url = "https://r.jina.ai/" + url
    try:
        response = requests.get(url, timeout=timeout)
        return parse_content(response.text)
    except:
        return None


def parse_content(content):
    TITLE = "Title:"
    SOURCE = "URL Source:"
    CONTENT_START = "Markdown Content:"
    lines = content.strip().split("\n")
    title = None
    source = None
    content = None
    for i, line in enumerate(lines):
        if line.startswith(TITLE):
            title = lines[0][len(TITLE):].strip()
        if line.startswith(SOURCE):
            source = lines[2][len(SOURCE):].strip()
        if line.startswith(CONTENT_START):
            content = "\n".join(lines[i+1:]).strip()
    return {"title": title, "source": source, "content": content}

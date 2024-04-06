import json
import re
import time

from IPython.display import clear_output, display, Markdown
from loguru import logger

from .llm import get_response
from .tools import get_references


def format_references(references):
    refs_text = ""
    for i, reference in enumerate(references):
        content = reference["content"].replace("\n", "  ").strip()
        refs_text += f"[citation:{i+1}]{content}\n\n"
    return refs_text.strip()


answer_prompt = """You are a help AI assistant. You're given the history questions and some references. Each reference starts with a citation number like [citation:x]. Your task is to answer the current question with three steps:
step 1: Determine what is asked about based on history questions and the current question, use history questions as context for disambiguation. Then select all applicable references to answer the *current question*. If some are selected, output them.

step 2: If no applicable references selected, just answer with 'I can not answer your question with current message', do not make up or guess your answer. Otherwise, write your answer to the *current question* following these rules:
- You must derive your answer from references. You must cite all supporting references by adding citation numbers in your answer to indicate where they are derived from.
- Try to give clear step-by-step solution and self-contained example.
- Code snippets in your answer must be *quoted* with ```.
- Write in professional tone. Keep your answer concise and accurate, *without repetition*. Limit to 1500 tokens.

step 3: If the answer is derived from the references successfully, then write *three* follow-up questions based on the question and references. Otherwise do not show any follow-up questions.

References:
{{referenes}}

History Questions: {{history_questions}}
Current Question: {{question}}

You must organize your output like the this example:
Applicable References: [citation:x] [citation:x] [citation:x] (show only applicable references, where x is a number)
Answer: sentence1([citation:x][citation:x]). sentence2([citation:x]). (show answer snippets with *supporting citations*, where x is a number)
Follow-up Questions: (if needed)
question1
question2
question3

(Note: other than code and specific names, your output must be written in the same language as the question.)
"""


def parse_output(output):
    APPLICABLE_REFERENCE = "applicable references"
    ANSWER = "answer"
    FOLLOW_UP_QUESTIONS = "follow-up questions"
    CITATION_PATTERN = re.compile("\[citation:(\d+)\]")
    QUESTION_MARK = re.compile("[?？]")
    result = {"raw": output}
    lines = output.strip().split("\n")
    line = lines[0].lower()
    if line.startswith(APPLICABLE_REFERENCE):
        line = line[line.find(APPLICABLE_REFERENCE)+1:]
        if CITATION_PATTERN.search(line) is None:
            return result
    else:
        return result

    idx = 1
    start = None
    end = None
    while idx < len(lines):
        line = lines[idx].strip().lower()
        if start is None and line.lower().startswith(ANSWER):
            start = idx
        if start is not None and end is None and line.startswith(FOLLOW_UP_QUESTIONS):
            end = idx
            break
        idx += 1
    answer = None
    if start is not None:
        if end is None:
            end = len(lines)
        answer = "\n".join(lines[start:end]).strip()
        answer = answer[len(ANSWER)+1:].strip()
        result["answer"] = answer
    else:
        return result

    questions = []
    if end is not None:
        text = "\n".join(lines[end:]).strip()
        text = text[len(FOLLOW_UP_QUESTIONS)+1:].strip()
        splits = text.split("\n")
        if len(splits) == 3:
            questions = [split.strip() for split in splits]
        else:
            splits = QUESTION_MARK.split(text)
            questions = [split.strip() for split in splits]
        result["followup-questions"] = questions

    return result


def format_result(result):
    answer = result["answer"]
    CITATION_PATTERN = re.compile("\[citation:(\d+)\]")
    answer = CITATION_PATTERN.sub(r"[\1]", answer)
    md_content = f"## Answer\n{answer}\n\n## Related Questions\n\n"
    for i, question in enumerate(result.get("followup-questions", [])):
        if len(question) < 3:
            continue
        if question[0].isdigit() and question[1] == ".":
            if question[2] != " ":
                question = question[:2] + " " + question[2:]
            md_content += question + "\n"
            continue
        elif question[0] == "-":
            question = question[1:].strip()
        md_content += f"{i+1}. {question}\n"

    if "references" in result:
        md_content += "\n## References:\n"
        for i, ref in enumerate(result["references"]):
            md_content += f"{i+1}. [{ref['title']}]({ref['url']})\n"

    return md_content


def search_and_answer(history_questions, question, compress_context=False, model="gpt35", stream=False):
    logger.info("searching web ...")
    references = get_references(question)
    with open("references.txt", "w") as fo:
        fo.write(json.dumps(references, ensure_ascii=False, indent=4))
    with open("references.txt") as fi:
        references = json.load(fi)
    if len(references) == 0:
        logger.warning("no references fetched.")
        return
    else:
        logger.info(f"{len(references)} references fetched")
    if compress_context:
        logger.info("compressing references ...")
    if len(references) == 0:
        logger.warning("no useful references found")
        return
    else:
        logger.info(f"{len(references)} useful references found")
    refs_text = format_references(references)
    history_questions = ";".join(history_questions)
    prompt = answer_prompt.replace("{{history_questions}}", history_questions)
    prompt = prompt.replace("{{question}}", question)
    prompt = prompt.replace("{{referenes}}", refs_text)
    logger.info("extracting answer...")
    if not stream:
        response = get_response(prompt)
        result = parse_output(response)
        result["references"] = references
        md = format_result(result)
        display(Markdown(md))
    else:
        response = get_response(prompt, stream=True)
        content = ""
        cache_content = ""
        start = time.time()
        for chunk in response:
            if not chunk.choices:
                continue
            chunk_content = chunk.choices[0].delta.content
            if chunk_content is not None:
                cache_content += chunk_content
                end = time.time()
                if int((end - start) * 1000) > 40:
                    content += cache_content
                    result = parse_output(content)
                    cache_content = ""
                    if "answer" in result:
                        md = format_result(result)
                        clear_output()
                        display(Markdown(md))
                    start = time.time()
        if cache_content:
            content += cache_content
            result = parse_output(content)
        result["references"] = references
        md = format_result(result)
        clear_output()
        display(Markdown(md))

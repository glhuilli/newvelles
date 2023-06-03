import os
import time
from typing import Iterable, Any

import openai


openai.api_key = os.getenv("OPENAI_API_KEY")

_MODEL = 'gpt-3.5-turbo'
OPEN_AI_TOKEN_LIMIT = 4098


def ask_chatgpt_with_retries(prompt: str, prompt_format: str, parse_method, retries):
    full_prompt = f'{prompt} {prompt_format}'
    response = {
        'prompt': prompt,
        'prompt_format': prompt_format,
        'full_prompt': full_prompt,
        'parsed_response': {}
    }
    for i in range(retries):
        try:
            response['parsed_response'] = ask_chatgpt(full_prompt, parse_method)
            return response
        except Exception as e:
            print(f'FAILED on retry {i}: {e}')  # TODO: replace print with logger
            if i < retries - 1:
                time.sleep(1)
                continue
            else:
                return response


def ask_chatgpt(full_prompt: str, parse_method) -> Iterable[Any]:
    """
    Return processed answer from chatGPT given a prompt
    """
    # prompt_data = 'includes the artist and the name of the song'
    # prompt_format = f'using the following json schema {JSON_SCHEMA}'
    print(f'calling openai with prompt: {full_prompt}')  # TODO: replace print with logger
    response = openai.ChatCompletion.create(model=_MODEL,
                                            messages=[{
                                                "role":
                                                "user",
                                                "content":
                                                full_prompt
                                            }])
    print(f'ChatGPT response: {response}')  # TODO: replace print with logger
    return _parse_response(response, parse_method)


def _parse_response(response, parse_method) -> Iterable[Any]:
    """
    Process the OpenAIObject and returns the message content
    """
    content = response.choices[0].message.content
    return parse_method(content)


def approximate_tokens(text: str) -> float:
    """
    1 token ~= ¾ words
    100 tokens ~= 75 words
    reference: https://help.openai.com/en/articles/4936856-what-are-tokens-and-how-to-count-them
    """
    ratio = 100/75
    words = text.split(' ')
    return len(words) * ratio

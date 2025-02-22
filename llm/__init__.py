from openai import OpenAI
from repository import NewsRepository
import json
import re
import string


def parse_latest_json(input_string: str) -> str:
    # Regular expression to match JSON objects
    # This looks for content between { and } with proper nesting
    json_pattern = r"\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}"

    # Find all JSON objects in the string
    json_matches = re.findall(json_pattern, input_string, re.DOTALL)

    if not json_matches:
        return "No JSON found in the string"

    # Get the last JSON match
    latest_json_str = json_matches[-1]

    # Validate that it's actually valid JSON
    try:
        parsed = json.loads(latest_json_str)
    except Exception as e:
        print(
            f"Couldn't parse json: {latest_json_str}: {e}\nInput string was: {input_string}"
        )
    return parsed


class LLM:
    def __init__(
        self,
        translate_api_key: str,
        translate_base_url: str,
        translate_model: str,
        words_api_key: str,
        words_base_url: str,
        words_model: str,
        repository: NewsRepository,
    ):
        self.translate_client = OpenAI(
            api_key=translate_api_key,
            base_url=translate_base_url,
        )
        self.words_client = OpenAI(
            api_key=words_api_key,
            base_url=words_base_url,
        )
        self.translate_model = translate_model
        self.words_model = words_model
        self.repository = repository

    def convert_to_a1(self, text: str) -> str | None:
        task_text = f"""Retell this news on greek using basic level of language A1. Be concise and creative. Do not use more than 6 sentences. News to retell:
```
{text}
```
Do not say anything else except the translation. For any words except the translation you will be fined for $1000000.
"""
        chat_completion = self.translate_client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": task_text,
                }
            ],
            model=self.translate_model,
        )
        if not chat_completion.choices[0].message.content:
            return None

        translation = self.sanitize_output(chat_completion.choices[0].message.content)
        result = dict()
        result["translation_a1"] = translation
        result["words"] = self.create_words_list(translation)
        return result

    def create_words_list(self, text: str) -> dict | None:
        words = text.split()
        words = list(set(words))  # remove duplicates
        filtered_words = [
            word
            for word in words
            if not word.startswith("#")
            and not (word.isalpha() and all(c.isascii() for c in word))
            and not (word[0].isdigit())
        ]  # remove hashtag and english words
        translator = str.maketrans("", "", string.punctuation)
        words = [word.translate(translator) for word in filtered_words]

        known_words = self.repository.get_words(words=words)
        found_words = set(known_words.keys())
        missing_words = set(words) - found_words

        if len(missing_words) > 0:
            task_text = f"""Here is the list of words:
    {'\n'.join(missing_words)}
    Translate all of them into English and determire part of the speech in context of the text:
    {text}
    And output the result in JSON format like so: {{"word1": ["translation", "part of the speech"], "word2": ["translation", "part of the speech"]}}
    """

            chat_completion = self.words_client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": task_text,
                    }
                ],
                model=self.words_model,
                #            response_format={"type": "json_object"},
            )
            if not chat_completion.choices[0].message.content:
                return None

            result = self.sanitize_output(chat_completion.choices[0].message.content)
            try:
                result = parse_latest_json(result)
                self.repository.add_words(words=result)
            except Exception as e:
                print(
                    f"Couldn't parse JSON. Got {chat_completion.choices[0].message.content}. Error: {e}"
                )
                return None
            result = result | known_words
        else:
            result = known_words
        return self.process_words_result(words=result)

    def process_words_result(self, words: dict) -> dict:
        print(f"process words: {words}")
        exclude_categories = {
            "preposition",
            "article",
            "proper noun",
            "auxiliary verb",
            "particle",
            "pronoun",
            "conjunction",
            "symbol",
            "adverb",
        }
        result = {
            key: value[0]
            for key, value in words.items()
            if value[1] not in exclude_categories and value[0] != key
        }
        return result

    @staticmethod
    def sanitize_output(text: str) -> str:
        result = re.sub(
            r"<think>.*?</think>",
            "",
            text,
            flags=re.DOTALL,
        )
        # Remove lines starting with backticks
        result = "\n".join(
            line for line in result.split("\n") if not line.startswith("`")
        )
        return result.strip()

from repository import NewsRepository, News
from newsbot import NewsBot
from llm import LLM
from dotenv import load_dotenv
import asyncio
import os

load_dotenv()

channels = dict()
channels["general"] = os.environ["TELEGRAM_GREEK_GAME_CHANNEL"]
channels["gaming"] = os.environ["TELEGRAM_GREEK_GAME_CHANNEL"]

repository = NewsRepository(
    username=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    database=os.getenv("MYSQL_DATABASE"),
    hostname=os.getenv("MYSQL_HOST") or "localhost",
    port=os.getenv("MYSQL_PORT") or 3306,
)

words_api_key = os.getenv("OPENAI_API_KEY")
if os.getenv("WORDS_OPENAI_API_KEY") is not None:
    words_api_key = os.environ["WORDS_OPENAI_API_KEY"]
words_base_url = os.getenv("OPENAI_BASE_URL")
if os.getenv("WORDS_OPENAI_BASE_URL") is not None:
    words_base_url = os.environ["WORDS_OPENAI_BASE_URL"]
words_model = os.getenv("OPENAI_MODEL")
if os.getenv("WORDS_OPENAI_MODEL") is not None:
    words_model = os.environ["WORDS_OPENAI_MODEL"]

llm = LLM(
    translate_api_key=os.getenv("OPENAI_API_KEY"),
    translate_base_url=os.getenv("OPENAI_BASE_URL"),
    translate_model=os.getenv("OPENAI_MODEL"),
    words_model=words_model,
    words_api_key=words_api_key,
    words_base_url=words_base_url,
    repository=repository,
)

tg_bot = NewsBot(
    telegram_token=os.getenv("TELEGRAM_BOT_TOKEN"),
    admin_id=int(os.environ["ADMIN_USER_ID"]),
    repository=repository,
    channels=channels,
    llm=llm,
)

if __name__ == "__main__":
    tg_bot.run()

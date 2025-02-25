from repository import NewsRepository
from llm import LLM
from newsbot import NewsBot
from dotenv import load_dotenv
import os

load_dotenv()

# Connect the database
repository = NewsRepository(
    username=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    database=os.getenv("MYSQL_DATABASE"),
    hostname=os.getenv("MYSQL_HOST") or "localhost",
    port=os.getenv("MYSQL_PORT") or 3306,
)

# Initialize LLM Models
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

# Start userbot


# @app.on_message()
# async def handle_message(client, message):
#     if message.chat.id == -1001338358512 or message.chat.id == 1494997:  # VGTIMES and me
#         await client.read_chat_history(message.chat.id)
#         if message.media_group_id is None:
#             await message.forward(chat_id="Znaimebot")  # @znaimebot
#         else:
#             media_group = await client.get_media_group(message.chat.id, message.id)
#             if message.id == media_group[-1].id:
#                 message_ids = [msg.id for msg in media_group]
#                 await client.forward_messages(chat_id="Znaimebot", from_chat_id=message.chat.id, message_ids=message_ids,)


# Our Channels to post translated news to
post_channels = dict()
post_channels["general"] = os.environ["TELEGRAM_GREEK_GAME_CHANNEL"]
post_channels["gaming"] = os.environ["TELEGRAM_GREEK_GAME_CHANNEL"]
watch_channels = os.environ["TELEGRAM_WATCH_CHANNELS"].split(',')

tg_bot = NewsBot(
    telegram_api_id=os.getenv("TELEGRAM_API_ID"),
    telegram_api_key=os.getenv("TELEGRAM_API_HASH"),
    post_channels=post_channels,
    watch_channels=watch_channels,
    repository=repository,
    llm=llm,
)

if __name__ == "__main__":
    tg_bot.run()

from hydrogram import Client, filters, idle
from hydrogram.handlers import MessageHandler
from hydrogram.types import  Photo, Video, InputMediaPhoto, InputMediaVideo
from hydrogram.enums import ParseMode
from repository import NewsRepository, News, NewsMedia
from llm import LLM
import re


MEDIA_CLASSES = {"photo": InputMediaPhoto, "video": InputMediaVideo}

class NewsBot:
    def __init__(
        self,
        telegram_api_id: str,
        telegram_api_key: str,
        post_channels: dict,
        watch_channels: list,
        repository: NewsRepository,
        llm: LLM,
    ):
        self.post_channels = post_channels
        self.watch_channels = [int(id) for id in watch_channels]
        self.repository = repository
        self.llm = llm
        self.app = Client("my_account", api_id=telegram_api_id, api_hash=telegram_api_key)
        self.app.add_handler(
            MessageHandler(
                self.message_handler, filters=filters.chat(chats=self.watch_channels)
            )
        )

    @staticmethod
    def replace_words(text, dictionary):
        # Sort keys by length (longest first) to prioritize longer matches
        sorted_keys = sorted(dictionary.keys(), key=len, reverse=True)

        # Create a pattern to match whole words starting with dictionary keys
        pattern = r"\b(" + "|".join(map(re.escape, sorted_keys)) + r")\w*\b"

        # Replace matched words with the format {word} ({translation})
        def replacement(match):
            matched_word = match.group(0)  # The full matched word (e.g., "παιχνιδιού")
            prefix = match.group(1)  # The dictionary key (e.g., "παιχνίδι")
            translation = dictionary[prefix]
            return f"{matched_word} (||{translation}||)"

        # Perform the replacement
        result = re.sub(pattern, replacement, text)
        return result

    async def send_translation(self, news: News, chat_id: int) -> bool:
        translated_text = f"""{news.greek_text_a1}
---
Source: {news.source}
"""
        text = self.replace_words(text=translated_text, dictionary=news.greek_words_a1)

        if len(news.media) == 0:
            return await self.__send_text_only(
                news=news,
                text=text,
                chat_id=chat_id,
            )
        else:
            return await self.__send_media_group(
                news=news,
                text=text,
                chat_id=chat_id,
            )

    async def __send_text_only(self, news: News, text: str, chat_id: int) -> bool:
        try:
            await self.app.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
            return True
        except Exception as e:
            print(f"Exception while sending a message: {e}")
            return False

    async def __send_media_group(self, news: News, text: str, chat_id: int):
        try:
            if len(news.media) > 1: # Send as a media group
                media_list = []
                first = True
                for media in news.media:
                    if first:
                        media_input = MEDIA_CLASSES[media.type](
                            media=media.file_id,
                            caption=text,
                            parse_mode=ParseMode.MARKDOWN,
                        )
                        first = False
                    else:
                        media_input = MEDIA_CLASSES[media.type](media=media.file_id)
                    media_list.append(media_input)
                await self.app.send_media_group(
                    chat_id=chat_id,
                    media=media_list,
                )
            else:
                pos_args = [chat_id, news.media[0].file_id]
                func_args = {
                    "caption": text,
                    "parse_mode": ParseMode.MARKDOWN,
                }
                if news.media[0].type == 'photo':
                    await self.app.send_photo(*pos_args, **func_args)
                elif news.media[0].type == 'video':
                    await self.app.send_video(*pos_args, **func_args)

            return True
        except Exception as e:
            print(f"Exception while sending a message: {e}")
            return False

    async def process_news(self, news: News) -> bool:
        if news.greek_text_a1 is None:
            result = self.llm.convert_to_a1(news.original_text)
            if result["translation_a1"] is not None and result["words"] is not None:
                self.repository.add_translation(
                    news_id=news.id,
                    translation_a1=result["translation_a1"],
                    words_a1=result["words"],
                )
                news.greek_text_a1 = result["translation_a1"]
                news.greek_words_a1 = result["words"]
            else:
                raise ValueError(f"Unable to get a translation. Got: {result}")
        sent = await self.send_translation(news, self.post_channels[news.type])
        if sent:
            self.repository.update_news(news_id=news.id, published=True)

    async def process_unpublished_messages(self):
        while True:
            news = self.repository.get_unpublished_news()
            if news is None:
                break
            await self.process_news(news)

    async def message_handler(self, client, message) -> None:
        """
        Handle incoming messages from the watched channels
        """
        print(f"Received message from {message.chat.id}")

        await client.read_chat_history(message.chat.id)

        news = News()
        if message.chat.username is not None:
            news.source = f"https://t.me/{message.chat.username}/{message.id}"
        else:
            news.source = f"{message.chat.title}"

        if message.media_group_id is not None:
            messages = await client.get_media_group(message.chat.id, message.id)
            if messages[-1].id != message.id:
                return
            news.media_group_id = message.media_group_id
        else:
            messages = [message]

        news.message_chat_id = message.chat.id
        news.type = 'gaming' # will determine the type later using channel id
        for msg in messages:
            if msg.text is not None:
                news.original_text = msg.text
                news.message_id = msg.id
            elif msg.caption is not None:
                news.original_text = msg.caption
                news.message_id = msg.id
            if msg.video is not None and isinstance(msg.video, Video):
                video = NewsMedia(
                    file_id=msg.video.file_id,
                    type='video',
                    message_id=msg.id,
                )
                news.media.append(video)
            if msg.photo is not None and isinstance(msg.photo, Photo):
                photo = NewsMedia(
                    file_id=msg.photo.file_id,
                    type='photo',
                    message_id=msg.id,
                )
                news.media.append(photo)

        news_id = self.repository.add_news(news)
        try:
            news = self.repository.get_news_by_id(news_id)
            await self.process_news(news)
        except Exception as e:
            print(f"Unable to get translation: {e}")

    async def __run(self):
        await self.app.start()
        await self.process_unpublished_messages()
        await idle()
        await self.app.stop()

    def run(self):
        self.app.run(self.__run())

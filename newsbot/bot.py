from telegram import (
    constants,
    LinkPreviewOptions,
    Update,
    InputMediaVideo,
    InputMediaPhoto,
    MessageOriginUser,
)
from telegram.helpers import escape_markdown
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters,
)
from repository import NewsRepository, News, NewsMedia
from llm import LLM
import re


MEDIA_CLASSES = {"photo": InputMediaPhoto, "video": InputMediaVideo}


class NewsBot:
    def __init__(
        self,
        telegram_token: str,
        admin_id: int,
        channels: dict,
        repository: NewsRepository,
        llm: LLM,
    ):
        self.admin_ids = [admin_id]
        self.app = ApplicationBuilder().token(telegram_token).build()
        self.app.add_handler(
            MessageHandler(filters.FORWARDED & filters.USER, self.message_handler)
        )
        self.repository = repository
        self.llm = llm
        self.channels = channels

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
            return f"{matched_word} \\(||{translation}||\\)"

        # Perform the replacement
        result = re.sub(pattern, replacement, text)
        return result

    async def send_translation(self, news: News, chat_id: int) -> bool:
        translated_text = f"""{news.greek_text_a1}
---
Source: {news.source}
"""
        escaped_text = escape_markdown(text=translated_text, version=2)
        escaped_text = self.replace_words(
            text=escaped_text, dictionary=news.greek_words_a1
        )
        # for greek in news.greek_words_a1:
        #     escaped_text = escaped_text.replace(
        #         greek, f"{greek} \\(||{news.greek_words_a1[greek]}||\\)"
        #     )

        if len(news.media) == 0:
            return await self.__send_text_only(
                news=news,
                text=escaped_text,
                chat_id=chat_id,
            )
        else:
            return await self.__send_media_group(
                news=news,
                text=escaped_text,
                chat_id=chat_id,
            )

    async def __send_text_only(self, news: News, text: str, chat_id: int) -> bool:
        try:
            await self.app.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=constants.ParseMode.MARKDOWN_V2,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
            return True
        except Exception as e:
            print(f"Exception while sending a message: {e}")
            return False

    async def __send_media_group(self, news: News, text: str, chat_id: int):
        try:
            if len(news.media) > 1:
                media_list = []
                first = True
                for media in news.media:
                    if first:
                        media_input = MEDIA_CLASSES[media.type](
                            media=media.file_id,
                            caption=text,
                            parse_mode=constants.ParseMode.MARKDOWN_V2,
                        )
                        first = False
                    else:
                        media_input = MEDIA_CLASSES[media.type](media=media.file_id)
                    media_list.append(media_input)
                await self.app.bot.send_media_group(
                    chat_id=chat_id,
                    media=media_list,
                )
            else:
                func_name = f"send_{news.media[0].type}"
                await self.app.bot[func_name](
                    chat_id,
                    news.media[0].file_id,
                    caption=text,
                    parse_mode=constants.ParseMode.MARKDOWN_V2,
                )
            return True
        except Exception as e:
            print(f"Exception while sending a message: {e}")
            return False

    async def message_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.message.from_user.id not in self.admin_ids:
            await update.message.reply_text(
                "You are not allowed to forward me any message"
            )
            return

        news_id = 0
        # If message is just another media for previous news
        if update.message.caption is not None or update.message.text is not None:
            # The main news message
            news = News()
            news.original_text = (
                update.message.caption
                if update.message.caption
                else update.message.text
            )
            if update.message.media_group_id is not None:
                news.media_group_id = update.message.media_group_id
            forward_chat = update.message.forward_origin
            if isinstance(forward_chat, MessageOriginUser):
                news.source = f"@{forward_chat.sender_user.username}"
            else:
                news.source = f"https://t.me/{forward_chat.chat.username}/{forward_chat.message_id}"
            news.sender_id = str(update.message.from_user.id)
            news.message_id = update.message.message_id
            news.message_chat_id = update.message.chat.id
            news.type = "gaming"
            news_id = self.repository.add_news(news)

            context.job_queue.run_once(
                callback=self.process_message,
                when=15,
                data=str(news_id),
            )

        if update.message.media_group_id is not None:
            media_group_id = update.message.media_group_id
        elif news_id > 0:
            media_group_id = f"-{news_id}"
        else:
            print("No media_group_id and no news id. Refusing to store the message")
            print(update.message)
            return

        if update.message.photo is not None:
            file_id = ""
            if isinstance(update.message.photo, tuple):
                if len(update.message.photo) > 0:
                    file_id = update.message.photo[0].file_id
            else:
                file_id = update.message.photo.file_id
            if len(file_id) > 0:
                photo = NewsMedia()
                photo.file_id = file_id
                photo.media_group_id = media_group_id
                photo.message_id = update.message.message_id
                photo.type = "photo"
                self.repository.add_media(
                    media=photo,
                )

        if update.message.video is not None:
            file_id = ""
            if isinstance(update.message.video, tuple):
                if len(update.message.video) > 0:
                    file_id = update.message.video[0].file_id
            else:
                file_id = update.message.video.file_id
            if len(file_id) > 0:
                video = NewsMedia()
                video.file_id = file_id
                video.media_group_id = media_group_id
                video.message_id = update.message.message_id
                video.type = "video"
                self.repository.add_media(
                    media=video,
                )

    async def process_message(self, context: ContextTypes.DEFAULT_TYPE):
        news_id = int(context.job.data)
        news = self.repository.get_news_by_id(news_id)
        if news is not None:
            await self.process_news(news)
            # Delete message in sender's chat
            if news.message_id > 0:
                await self.app.bot.delete_message(
                    chat_id=news.message_chat_id,
                    message_id=news.message_id,
                )
                for media in news.media:
                    if media.message_id == news.message_id or media.message_id == 0:
                        continue
                    await self.app.bot.delete_message(
                        chat_id=news.message_chat_id,
                        message_id=media.message_id,
                    )

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
                return False
        await self.send_translation(news, self.channels[news.type])
        self.repository.update_news(news_id=news.id, published=True)

    async def process_unpublished_messages(self, context: ContextTypes.DEFAULT_TYPE):
        while True:
            news = self.repository.get_unpublished_news()
            if news is None:
                break
            await self.process_news(news)

    def run(self):
        self.app.job_queue.run_once(
            callback=self.process_unpublished_messages,
            when=1,
        )
        self.app.run_polling()

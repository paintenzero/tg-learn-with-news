from sqlalchemy import create_engine, Column, Integer, String, Boolean, JSON
from sqlalchemy.orm import sessionmaker, joinedload, Session
from .news import News, NewsMedia
from .words import Words
from .base import ModelBase
from urllib.parse import quote_plus
from typing import Optional
from functools import wraps


def with_session(func):
    @wraps(func)
    def wrapper(self, *args, session: Optional[Session] = None, **kwargs):
        close_session = False
        if session is None:
            session = self.create_session()
            close_session = True

        try:
            result = func(self, *args, **kwargs, session=session)
            return result
        except Exception as e:
            print(f"DB Error in {func.__name__}: {e}")
            return None
        finally:
            if close_session:
                session.close()

    return wrapper


class NewsRepository:
    def __init__(
        self,
        username: str,
        password: str,
        database: str,
        hostname: str = "localhost",
        port: int = 3306,
    ):
        p = quote_plus(password)
        url = f"mysql+pymysql://{username}:{p}@{hostname}:{port}/{database}"
        self.engine = create_engine(url, pool_size=1, pool_pre_ping=True)
        self.local_session = sessionmaker(bind=self.engine)
        self.create_tables()

    def create_tables(self):
        ModelBase.metadata.create_all(self.engine)

    def create_session(self) -> Session:
        return self.local_session()

    @with_session
    def add_news(self, news: News, session: Session) -> int | None:
        # if placeholder was already created to store media...
        if news.media_group_id is not None:
            news_id = self.get_news_id_by_media_group_id(news.media_group_id)
        else:
            news_id = -1
        if news_id > 0:
            placeholder = self.get_news_by_id(news_id, session=session)
            placeholder.original_text = news.original_text
            placeholder.greek_text_a1 = news.greek_text_a1
            placeholder.greek_words_a1 = news.greek_words_a1
            placeholder.source = news.source
            placeholder.published = news.published
            placeholder.message_id = news.message_id
            placeholder.message_chat_id = news.message_chat_id
            placeholder.sender_id = news.sender_id
            placeholder.type = news.type
        else:
            session.add(news)
        session.commit()
        if news_id < 0:  # New news
            news_id = news.id
            if news.media_group_id is None:
                news.media_group_id = str(-news_id)
                session.commit()
        return news_id

    @with_session
    def get_news_id_by_media_group_id(
        self, media_group_id: int, session: Session
    ) -> int:
        news = session.query(News).filter_by(media_group_id=media_group_id).first()
        if news is not None:
            return news.id
        else:
            return -1

    @with_session
    def get_news_by_id(self, news_id: int, session: Session) -> News | None:
        news = (
            session.query(News)
            .options(joinedload(News.media))
            .filter_by(id=news_id)
            .first()
        )
        return news

    @with_session
    def add_media(self, media: NewsMedia, session: Session):
        if (
            self.get_news_id_by_media_group_id(
                media_group_id=media.media_group_id,
                session=session,
            )
            < 0
        ):
            # Add empty news to store the media
            news = News()
            news.original_text = ""
            news.source = ""
            news.sender_id = ""
            news.media_group_id = media.media_group_id
            session.add(news)
        session.add(media)
        session.commit()
        return media

    def add_translation(
        self, news_id: int, translation_a1: str, words_a1: dict
    ) -> News | None:
        session = self.local_session()
        try:
            news = self.get_news_by_id(news_id, session=session)
            if news is not None:
                news.greek_text_a1 = translation_a1
                news.greek_words_a1 = words_a1
                session.commit()
            return news
        except Exception as e:
            print(f"Error adding translation: {e}")
            return None
        finally:
            session.close()

    @with_session
    def get_unpublished_news(self, session: Session):
        news = (
            session.query(News)
            .options(joinedload(News.media))
            .filter_by(published=False)
            .first()
        )
        return news

    @with_session
    def update_news(self, news_id, session: Session, **kwargs):
        news = session.query(News).filter_by(id=news_id).first()
        if news:
            for key, value in kwargs.items():
                if key == "greek_words_a1":
                    news.set_greek_words_a1(value)
                else:
                    setattr(news, key, value)
            session.commit()
            return news
        return None

    @with_session
    def add_words(self, words: dict, session: Session):
        for word, (translation, speech_part) in words.items():
            # Check if the word already exists
            existing_word = session.query(Words).filter_by(word=word).first()
            if existing_word:  # Skip existing word
                continue

            # Create a new Words object
            new_word = Words(
                word=word, translation=translation, speech_part=speech_part
            )

            session.add(new_word)
        session.commit()

    @with_session
    def get_words(self, words: list, session: Session) -> dict:
        results = session.query(Words).filter(Words.word.in_(words)).all()
        known_words = {
            result.word: [result.translation, result.speech_part] for result in results
        }
        return known_words

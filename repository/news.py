from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    JSON,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from .base import ModelBase
import json


class News(ModelBase):
    __tablename__ = "news"

    # Columns definition
    id = Column(Integer, primary_key=True, autoincrement=True)
    original_text = Column(String(5000), nullable=False)
    greek_text_a1 = Column(String(5000), nullable=True)
    greek_words_a1 = Column(JSON, nullable=True)
    source = Column(String(255), nullable=False)
    media_group_id = Column(String(100), nullable=True)
    published = Column(Boolean, default=False)
    message_id = Column(Integer, nullable=True)
    message_chat_id = Column(String(100), nullable=True)
    sender_id = Column(String(100), nullable=False)
    type = Column(String(32), nullable=False, default="general")

    __table_args__ = (UniqueConstraint("media_group_id", name="uq_media_group_id"),)

    # Relationships
    media = relationship(
        "NewsMedia", back_populates="news", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return (
            f"<News(id={self.id}, source='{self.source}', text={self.original_text})>"
        )

    def set_greek_words_a1(self, words_list: dict):
        self.greek_words_a1 = json.dumps(words_list)

    def get_greek_words_a1(self):
        return json.loads(self.greek_words_a1) if self.greek_words_a1 else None


class NewsMedia(ModelBase):
    __tablename__ = "news_media"

    id = Column(Integer, primary_key=True, autoincrement=True)
    media_group_id = Column(
        String(100), ForeignKey("news.media_group_id"), nullable=False
    )
    type = Column(String(20), nullable=False)
    file_id = Column(String(255), nullable=False)
    message_id = Column(Integer, nullable=True)

    # Relationship back to News
    news = relationship("News", back_populates="media")

    def __repr__(self):
        return f"<NewsMedia(id={self.id}, type={self.type}, media_group_id={self.media_group_id}, file_id={self.file_id}"

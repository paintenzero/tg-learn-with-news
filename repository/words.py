from sqlalchemy import (
    Column,
    Integer,
    String,
    UniqueConstraint,
)
from .base import ModelBase


class Words(ModelBase):
    __tablename__ = "words"

    # Columns definition
    id = Column(Integer, primary_key=True, autoincrement=True)
    word = Column(String(100), nullable=False)
    speech_part = Column(String(100), nullable=False)
    translation = Column(String(100), nullable=False)

    __table_args__ = (UniqueConstraint("word", name="uq_word"),)

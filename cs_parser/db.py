from typing import Any, Optional
import sqlalchemy as sa
from sqlmodel import SQLModel, Field, Session, create_engine
import logging

logger = logging.getLogger("db")


class Skin(SQLModel, table=True):
    __tablename__ = "skins"
    market_hash_name: str = Field(primary_key=True)
    item: Any = Field(sa_column=sa.Column(sa.JSON, nullable=False))
    paintkit: Any = Field(sa_column=sa.Column(sa.JSON, nullable=False))
    collection: Optional[Any] = Field(default=None, sa_column=sa.Column(sa.JSON, nullable=True))
    lootlist: Optional[Any] = Field(default=None, sa_column=sa.Column(sa.JSON, nullable=True))
    variants: Optional[Any] = Field(default=None, sa_column=sa.Column(sa.JSON, nullable=True))


class Sticker(SQLModel, table=True):
    __tablename__ = "stickers"
    market_hash_name: str = Field(primary_key=True)
    stickerkit: Any = Field(sa_column=sa.Column(sa.JSON, nullable=False))


class Patch(SQLModel, table=True):
    __tablename__ = "patches"
    market_hash_name: str = Field(primary_key=True)
    stickerkit: Any = Field(sa_column=sa.Column(sa.JSON, nullable=False))


class Graffiti(SQLModel, table=True):
    __tablename__ = "graffities"
    market_hash_name: str = Field(primary_key=True)
    stickerkit: Any = Field(sa_column=sa.Column(sa.JSON, nullable=False))


class MusicKit(SQLModel, table=True):
    __tablename__ = "musickits"
    market_hash_name: str = Field(primary_key=True)
    item: Any = Field(sa_column=sa.Column(sa.JSON, nullable=False))
    musicdef: Any = Field(sa_column=sa.Column(sa.JSON, nullable=False))


class KeychainItem(SQLModel, table=True):
    __tablename__ = "keychains"
    market_hash_name: str = Field(primary_key=True)
    item: Any = Field(sa_column=sa.Column(sa.JSON, nullable=False))
    keychain: Any = Field(sa_column=sa.Column(sa.JSON, nullable=False))


class Agent(SQLModel, table=True):
    __tablename__ = "agents"
    market_hash_name: str = Field(primary_key=True)
    item: Any = Field(sa_column=sa.Column(sa.JSON, nullable=False))


class Container(SQLModel, table=True):
    __tablename__ = "containers"
    market_hash_name: str = Field(primary_key=True)
    lootlist: Any = Field(sa_column=sa.Column(sa.JSON, nullable=False))
    container: Any = Field(sa_column=sa.Column(sa.JSON, nullable=False))


class ContainerKey(SQLModel, table=True):
    __tablename__ = "container_keys"
    market_hash_name: str = Field(primary_key=True)
    item: Any = Field(sa_column=sa.Column(sa.JSON, nullable=False))


class Pin(SQLModel, table=True):
    __tablename__ = "pins"
    market_hash_name: str = Field(primary_key=True)
    item: Any = Field(sa_column=sa.Column(sa.JSON, nullable=False))


class Pass(SQLModel, table=True):
    __tablename__ = "passes"
    market_hash_name: str = Field(primary_key=True)
    item: Any = Field(sa_column=sa.Column(sa.JSON, nullable=False))


_MODEL_MAP = {
    "skins": Skin,
    "stickers": Sticker,
    "patches": Patch,
    "graffities": Graffiti,
    "musickits": MusicKit,
    "keychains": KeychainItem,
    "agents": Agent,
    "containers": Container,
    "container_keys": ContainerKey,
    "pins": Pin,
    "passes": Pass,
}


def save_to_db(data: dict[str, dict], db_url: str) -> None:
    """Save parsed items to PostgreSQL. Creates tables if they don't exist, upserts records.

    Args:
        data: {item_type: {market_hash_name: {field: value, ...}}}
        db_url: SQLAlchemy-compatible PostgreSQL URL, e.g. postgresql://localhost/cs_items
    """
    engine = create_engine(db_url)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        for item_type, items in data.items():
            model_cls = _MODEL_MAP[item_type]
            for market_hash_name, values in items.items():
                record = model_cls(market_hash_name=market_hash_name, **values)
                session.merge(record)
        session.commit()

    logger.info("Data saved to database (%s)", db_url)

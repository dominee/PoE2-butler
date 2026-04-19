"""SQLAlchemy ORM models.

Kept intentionally small and read-optimised: user identity, encrypted OAuth
tokens, and snapshots of GGG data as JSONB blobs (keyed by user + league +
kind).  All large queryable data lives inside the JSONB; relational columns
exist only to index snapshots and enforce foreign keys.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")
UUIDType = Uuid(as_uuid=True)
SnapshotIdType = BigInteger().with_variant(Integer(), "sqlite")


class SnapshotKind(enum.StrEnum):
    PROFILE = "profile"
    LEAGUES = "leagues"
    CHARACTERS = "characters"
    CHARACTER = "character"
    STASH_LIST = "stash_list"
    STASH_TAB = "stash_tab"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    ggg_account_name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    ggg_uuid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    realm: Mapped[str] = mapped_column(String(16), default="pc")
    preferred_league: Mapped[str | None] = mapped_column(String(200), nullable=True)
    trade_tolerance_pct: Mapped[int] = mapped_column(default=10)
    valuable_threshold_chaos: Mapped[int] = mapped_column(default=100)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    tokens: Mapped[UserToken | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    snapshots: Mapped[list[Snapshot]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserToken(Base):
    __tablename__ = "user_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    access_token_enc: Mapped[bytes] = mapped_column(LargeBinary)
    refresh_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    scope: Mapped[str] = mapped_column(String(500), default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="tokens")


class Snapshot(Base):
    __tablename__ = "snapshots"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", "key", name="uq_snapshot_user_kind_key"),
    )

    id: Mapped[int] = mapped_column(SnapshotIdType, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[SnapshotKind] = mapped_column(
        Enum(
            SnapshotKind,
            name="snapshot_kind",
            # Store the enum's .value ("profile", not the member name "PROFILE").
            values_callable=lambda e: [m.value for m in e],
            create_type=False,
        )
    )
    key: Mapped[str] = mapped_column(String(200), default="")
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="snapshots")

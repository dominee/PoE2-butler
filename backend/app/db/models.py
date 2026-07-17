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
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")
UUIDType = Uuid(as_uuid=True)
SnapshotIdType = BigInteger().with_variant(Integer(), "sqlite")
ItemPriceEstimateIdType = BigInteger().with_variant(Integer(), "sqlite")
CharacterSnapshotHistoryIdType = BigInteger().with_variant(Integer(), "sqlite")
UserActivityEventIdType = BigInteger().with_variant(Integer(), "sqlite")


class UserActivityEventType(enum.StrEnum):
    LOGIN = "login"
    REFRESH = "refresh"


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
    preferred_character_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    trade_tolerance_pct: Mapped[int] = mapped_column(default=10)
    valuable_threshold_chaos: Mapped[int] = mapped_column(default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
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
    item_shares: Mapped[list[ItemShare]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    character_shares: Mapped[list[CharacterShare]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    item_price_estimates: Mapped[list[ItemPriceEstimate]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    activity_events: Mapped[list[UserActivityEvent]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    api_keys: Mapped[list[UserApiKey]] = relationship(
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
    __table_args__ = (UniqueConstraint("user_id", "kind", "key", name="uq_snapshot_user_kind_key"),)

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
    prev_payload: Mapped[dict | None] = mapped_column(JSONType, nullable=True, default=None)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="snapshots")


class CharacterSnapshotHistory(Base):
    """Append-only archive of past CHARACTER snapshot payloads for the gear timeline."""

    __tablename__ = "character_snapshot_history"
    __table_args__ = (
        Index("ix_char_snap_hist_user_name_fetched", "user_id", "character_name", "fetched_at"),
    )

    id: Mapped[int] = mapped_column(
        CharacterSnapshotHistoryIdType, primary_key=True, autoincrement=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    character_name: Mapped[str] = mapped_column(String(200))
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    changes: Mapped[list] = mapped_column(JSONType, default=list)


class ItemShare(Base):
    """World-readable public link to a snapshot of an item (see INSTRUCTIONS § share links)."""

    __tablename__ = "item_shares"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    league: Mapped[str] = mapped_column(String(200), default="")
    item_raw: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    user: Mapped[User] = relationship(back_populates="item_shares")


class CharacterShareViewMode(enum.StrEnum):
    SIMPLE = "simple"
    DETAILED = "detailed"


class CharacterShare(Base):
    """World-readable public link to a frozen character gear snapshot."""

    __tablename__ = "character_shares"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    league: Mapped[str] = mapped_column(String(200), default="")
    character_name: Mapped[str] = mapped_column(String(200), default="")
    character_raw: Mapped[dict] = mapped_column(JSONType, default=dict)
    view_mode: Mapped[CharacterShareViewMode] = mapped_column(
        Enum(
            CharacterShareViewMode,
            values_callable=lambda e: [m.value for m in e],
            native_enum=False,
            create_constraint=False,
        ),
        default=CharacterShareViewMode.SIMPLE,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    user: Mapped[User] = relationship(back_populates="character_shares")


class ItemPriceEstimate(Base):
    """Latest hybrid (aggregator / scout / trade) estimate for a stash item instance."""

    __tablename__ = "item_price_estimates"
    __table_args__ = (
        UniqueConstraint("user_id", "league", "item_id", name="uq_item_price_user_league_item"),
    )

    id: Mapped[int] = mapped_column(ItemPriceEstimateIdType, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    league: Mapped[str] = mapped_column(String(200), default="")
    item_id: Mapped[str] = mapped_column(String(128), default="")
    tolerance_pct: Mapped[float] = mapped_column(default=10.0)
    item_name: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(20), default="completed")
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="item_price_estimates")


class UserActivityEvent(Base):
    """Append-only login / refresh events for admin adoption and activity charts."""

    __tablename__ = "user_activity_events"
    __table_args__ = (Index("ix_user_activity_events_type_created", "event_type", "created_at"),)

    id: Mapped[int] = mapped_column(UserActivityEventIdType, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[UserActivityEventType] = mapped_column(
        Enum(
            UserActivityEventType,
            values_callable=lambda e: [m.value for m in e],
            native_enum=False,
            create_constraint=False,
        )
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    user: Mapped[User] = relationship(back_populates="activity_events")


class UserApiKey(Base):
    """Per-user machine API key for Discord bot and other integrations.

    Only one non-revoked key is allowed per user (enforced via partial unique index).
    The secret is never stored — only its HMAC-SHA256 digest with a server-side pepper.
    Key format: ``hob_<prefix12>_<secret32>``; prefix stored plaintext for O(1) lookup.
    """

    __tablename__ = "user_api_keys"
    __table_args__ = (
        # Partial unique index: one non-revoked key per user (service layer also enforces this).
        Index(
            "uq_user_api_keys_active_user",
            "user_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
            sqlite_where=text("revoked_at IS NULL"),
        ),
        Index("ix_user_api_keys_prefix", "key_prefix"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    key_prefix: Mapped[str] = mapped_column(String(16))
    key_hash: Mapped[str] = mapped_column(String(64))
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="api_keys")

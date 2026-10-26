import os, datetime as dt
from sqlalchemy import create_engine, String, Text, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

url = os.getenv("DATABASE_URL") or "sqlite:///./debrief.db"
for old in ("postgres://", "postgresql://"):
    if url.startswith(old):
        url = "postgresql+psycopg2://" + url[len(old):]
engine = create_engine(url, pool_pre_ping=True,
                       connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
Session = sessionmaker(engine, expire_on_commit=False)

def now(): return dt.datetime.now(dt.timezone.utc)

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    pw_hash: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)

class Journal(Base):
    __tablename__ = "journal"
    __table_args__ = (UniqueConstraint("user_id", "day"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    day: Mapped[str] = mapped_column(String(10))
    mood: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text, default="")
    gratitude: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

class Saved(Base):
    __tablename__ = "saved"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(120))
    input_text: Mapped[str] = mapped_column(Text)
    result: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)

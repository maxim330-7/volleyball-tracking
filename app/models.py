from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class VideoStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class ServeSide(str, enum.Enum):
    UNKNOWN = "unknown"
    NEAR = "near"
    FAR = "far"


class ArtifactKind(str, enum.Enum):
    DETECTIONS = "detections"
    TRACKS = "tracks"       


def str_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        length=20,
        values_callable=lambda e: [m.value for m in e],
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320))
    password_hash: Mapped[str] = mapped_column(String(255))  # argon2/bcrypt, не сам пароль
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    videos: Mapped[list[Video]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(512))
    duration: Mapped[float] = mapped_column(Float)          
    fps: Mapped[float] = mapped_column(Float)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    status: Mapped[VideoStatus] = mapped_column(
        str_enum(VideoStatus, "video_status"),
        default=VideoStatus.UPLOADED,
        server_default=VideoStatus.UPLOADED.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped[User] = relationship(back_populates="videos")
    jobs: Mapped[list[ProcessingJob]] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
        order_by="ProcessingJob.id",
    )
    rallies: Mapped[list[Rally]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        CheckConstraint("progress BETWEEN 0 AND 100", name="progress_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[JobStatus] = mapped_column(
        str_enum(JobStatus, "job_status"), default=JobStatus.QUEUED
    )
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0..100
    # Версия весов/пайплайна: без неё результаты разных запусков не сравнить.
    model_version: Mapped[str] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    video: Mapped[Video] = relationship(back_populates="jobs")
    rallies: Mapped[list[Rally]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list[JobArtifact]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class Rally(Base):
    __tablename__ = "rallies"
    __table_args__ = (
        UniqueConstraint("job_id", "number", name="uq_rallies_job_number"),
        CheckConstraint("end_frame >= start_frame", name="frames_order"),
        CheckConstraint("end_time >= start_time", name="times_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), index=True  # денормализация для выборок по видео
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("processing_jobs.id", ondelete="CASCADE"), index=True
    )
    number: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[float] = mapped_column(Float)
    end_time: Mapped[float] = mapped_column(Float)
    start_frame: Mapped[int] = mapped_column(Integer)
    end_frame: Mapped[int] = mapped_column(Integer)
    serve_side: Mapped[ServeSide] = mapped_column(
        str_enum(ServeSide, "serve_side"), default=ServeSide.UNKNOWN
    )

    video: Mapped[Video] = relationship(back_populates="rallies")
    job: Mapped[ProcessingJob] = relationship(back_populates="rallies")


class JobArtifact(Base):
    __tablename__ = "job_artifacts"
    __table_args__ = (
        UniqueConstraint("job_id", "kind", name="uq_job_artifacts_job_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("processing_jobs.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[ArtifactKind] = mapped_column(str_enum(ArtifactKind, "artifact_kind"))
    format: Mapped[str] = mapped_column(String(16))         # "parquet"
    storage_path: Mapped[str] = mapped_column(String(512))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    job: Mapped[ProcessingJob] = relationship(back_populates="artifacts")
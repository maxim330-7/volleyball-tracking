"""initial schema: users, videos, processing_jobs, rallies, job_artifacts

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VIDEO_STATUS = ("uploaded", "queued", "processing", "completed", "error")
JOB_STATUS = ("queued", "processing", "completed", "error")
SERVE_SIDE = ("unknown", "near", "far")
ARTIFACT_KIND = ("detections", "tracks")


def _str_enum(values: tuple[str, ...], name: str) -> sa.Enum:
    # Должно совпадать с str_enum() в app/models.py: строка + CHECK.
    return sa.Enum(
        *values,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        length=20,
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "videos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(512), nullable=False),
        sa.Column("duration", sa.Float(), nullable=False),
        sa.Column("fps", sa.Float(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            _str_enum(VIDEO_STATUS, "video_status"),
            nullable=False,
            server_default="uploaded",
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_videos_user_id", "videos", ["user_id"])

    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "video_id",
            sa.Integer(),
            sa.ForeignKey("videos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", _str_enum(JOB_STATUS, "job_status"), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("progress BETWEEN 0 AND 100", name="progress_range"),
    )
    op.create_index("ix_processing_jobs_video_id", "processing_jobs", ["video_id"])

    op.create_table(
        "rallies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "video_id",
            sa.Integer(),
            sa.ForeignKey("videos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("processing_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("start_frame", sa.Integer(), nullable=False),
        sa.Column("end_frame", sa.Integer(), nullable=False),
        sa.Column("serve_side", _str_enum(SERVE_SIDE, "serve_side"), nullable=False),
        sa.UniqueConstraint("job_id", "number", name="uq_rallies_job_number"),
        sa.CheckConstraint("end_frame >= start_frame", name="frames_order"),
        sa.CheckConstraint("end_time >= start_time", name="times_order"),
    )
    op.create_index("ix_rallies_video_id", "rallies", ["video_id"])
    op.create_index("ix_rallies_job_id", "rallies", ["job_id"])

    op.create_table(
        "job_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("processing_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", _str_enum(ARTIFACT_KIND, "artifact_kind"), nullable=False),
        sa.Column("format", sa.String(16), nullable=False),
        sa.Column("storage_path", sa.String(512), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("job_id", "kind", name="uq_job_artifacts_job_kind"),
    )
    op.create_index("ix_job_artifacts_job_id", "job_artifacts", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_job_artifacts_job_id", table_name="job_artifacts")
    op.drop_table("job_artifacts")

    op.drop_index("ix_rallies_job_id", table_name="rallies")
    op.drop_index("ix_rallies_video_id", table_name="rallies")
    op.drop_table("rallies")

    op.drop_index("ix_processing_jobs_video_id", table_name="processing_jobs")
    op.drop_table("processing_jobs")

    op.drop_index("ix_videos_user_id", table_name="videos")
    op.drop_table("videos")

    op.drop_table("users")
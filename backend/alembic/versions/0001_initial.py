"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "catalog",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("source_pdf_name", sa.String(length=255), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wm_opacity", sa.Integer(), nullable=False, server_default="55"),
        sa.Column("wm_font_scale", sa.Integer(), nullable=False, server_default="28"),
        sa.Column("wm_text_suffix", sa.String(length=60), nullable=False, server_default="CONFIDENTIAL"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_catalog_slug"),
    )
    op.create_index("ix_catalog_slug", "catalog", ["slug"])

    op.create_table(
        "catalog_image",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("catalog_id", sa.Integer(), nullable=False),
        sa.Column("page_index", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["catalog_id"], ["catalog.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("catalog_id", "page_index", name="uq_catalog_page"),
    )
    op.create_index("ix_catalog_image_catalog_id", "catalog_image", ["catalog_id"])

    op.create_table(
        "share_link",
        sa.Column("token", sa.String(length=6), primary_key=True),
        sa.Column("catalog_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("max_devices", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("client_label", sa.String(length=120), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["catalog_id"], ["catalog.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_share_link_catalog_id", "share_link", ["catalog_id"])

    op.create_table(
        "registered_device",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token", sa.String(length=6), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("fingerprint_hash", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("friendly_name", sa.String(length=120), nullable=False, server_default="Unknown device"),
        sa.Column("approx_location", sa.String(length=120), nullable=False, server_default="Local/Unknown"),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["token"], ["share_link.token"], ondelete="CASCADE"),
        sa.UniqueConstraint("token", "device_id", name="uq_token_device"),
    )
    op.create_index("ix_registered_device_token", "registered_device", ["token"])

    op.create_table(
        "access_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token", sa.String(length=6), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("friendly_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("approx_location", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("ip", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("user_agent", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["token"], ["share_link.token"], ondelete="CASCADE"),
    )
    op.create_index("ix_access_event_token", "access_event", ["token"])
    op.create_index("ix_access_event_token_created", "access_event", ["token", "created_at"])


def downgrade() -> None:
    op.drop_table("access_event")
    op.drop_table("registered_device")
    op.drop_table("share_link")
    op.drop_table("catalog_image")
    op.drop_table("catalog")

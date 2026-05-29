"""fuzzy device fingerprint: signals column + device_browser map table

Revision ID: 0002_fuzzy_device
Revises: 0001_initial
Create Date: 2026-05-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_fuzzy_device"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Widen primary browser id and add the fuzzy-match signals blob.
    op.alter_column("registered_device", "device_id",
                    type_=sa.String(length=160), existing_type=sa.String(length=128))
    op.add_column("registered_device",
                  sa.Column("signals", sa.Text(), nullable=False, server_default="{}"))

    # Browser -> logical-device map.
    op.create_table(
        "device_browser",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("registered_device_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=6), nullable=False),
        sa.Column("browser_device_id", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["registered_device_id"], ["registered_device.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["token"], ["share_link.token"], ondelete="CASCADE"),
        sa.UniqueConstraint("token", "browser_device_id", name="uq_token_browser"),
    )
    op.create_index("ix_device_browser_token", "device_browser", ["token"])
    op.create_index("ix_device_browser_registered_device_id", "device_browser", ["registered_device_id"])

    # Backfill: every existing registered device gets a browser mapping for its device_id.
    op.execute(
        "INSERT INTO device_browser (registered_device_id, token, browser_device_id, created_at, last_seen) "
        "SELECT id, token, device_id, first_seen, last_seen FROM registered_device"
    )


def downgrade() -> None:
    op.drop_index("ix_device_browser_registered_device_id", table_name="device_browser")
    op.drop_index("ix_device_browser_token", table_name="device_browser")
    op.drop_table("device_browser")
    op.drop_column("registered_device", "signals")
    op.alter_column("registered_device", "device_id",
                    type_=sa.String(length=128), existing_type=sa.String(length=160))

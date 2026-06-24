"""Add perfilado table

Revision ID: c2d3e4f5a6b7
Revises: b1a2c3d4e5f6
Create Date: 2026-06-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "b1a2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "perfilado",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("id_dataset", sa.Integer(), nullable=False),
        sa.Column("path_perfilado", sa.String(), nullable=False),
        sa.Column("weigth_mb", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["id_dataset"], ["datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id_dataset"),
    )
    op.create_index(op.f("ix_perfilado_id"), "perfilado", ["id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_perfilado_id"), table_name="perfilado")
    op.drop_table("perfilado")

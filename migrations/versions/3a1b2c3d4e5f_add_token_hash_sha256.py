"""add token_hash_sha256 column for O(1) refresh token lookup

Revision ID: 3a1b2c3d4e5f
Revises: 02cc7a4980ec
Create Date: 2026-06-16 19:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3a1b2c3d4e5f'
down_revision: Union[str, Sequence[str], None] = '02cc7a4980ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('refresh_tokens',
        sa.Column('token_hash_sha256', sa.String(length=64), nullable=True)
    )
    op.create_index(
        op.f('ix_refresh_tokens_token_hash_sha256'),
        'refresh_tokens',
        ['token_hash_sha256'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_refresh_tokens_token_hash_sha256'),
        table_name='refresh_tokens'
    )
    op.drop_column('refresh_tokens', 'token_hash_sha256')

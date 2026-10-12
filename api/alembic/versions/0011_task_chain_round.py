"""task chain round: a fresh contract key each time a dropped task is listed again

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-12 11:05:00
"""
import sqlalchemy as sa

from alembic import op

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tasks', sa.Column('chain_round', sa.Integer(), nullable=False, server_default='0'))
    op.create_table('translations',
    sa.Column('id', sa.String(length=40), nullable=False),
    sa.Column('lang', sa.String(length=8), nullable=False),
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('source', sa.Text(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    if_not_exists=True,
    )
    op.create_index(op.f('ix_translations_created_at'), 'translations', ['created_at'], unique=False, if_not_exists=True)
    op.create_index(op.f('ix_translations_key'), 'translations', ['key'], unique=True, if_not_exists=True)
    op.create_index(op.f('ix_translations_lang'), 'translations', ['lang'], unique=False, if_not_exists=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_translations_lang'), table_name='translations')
    op.drop_index(op.f('ix_translations_key'), table_name='translations')
    op.drop_index(op.f('ix_translations_created_at'), table_name='translations')
    op.drop_table('translations')
    op.drop_column('tasks', 'chain_round')

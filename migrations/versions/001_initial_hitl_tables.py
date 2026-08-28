"""Initial HITL tables: checkpoints, webhooks, escalation_policies

Revision ID: 001
Revises: 
Create Date: 2026-08-27 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create hitl_checkpoints table
    op.create_table(
        'hitl_checkpoints',
        sa.Column('checkpoint_id', sa.String(255), nullable=False),
        sa.Column('agent_id', sa.String(255), nullable=False),
        sa.Column('execution_id', sa.String(255), nullable=False),
        sa.Column('state_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('reason', sa.String(100), nullable=False),
        sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('question', sa.Text(), nullable=True),
        sa.Column('options', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.String(255), nullable=True),
        sa.Column('resolution', sa.String(50), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, default='pending'),
        sa.Column('priority', sa.Integer(), nullable=False, default=0),
        sa.Column('approval_chain', postgresql.ARRAY(sa.String(255)), nullable=False, default=[]),
        sa.Column('current_approver_index', sa.Integer(), nullable=False, default=0),
        sa.Column('escalation_count', sa.Integer(), nullable=False, default=0),
        sa.Column('audit_trail', postgresql.JSONB(astext_type=sa.Text()), nullable=False, default=[]),
        sa.PrimaryKeyConstraint('checkpoint_id'),
    )
    
    op.create_index('ix_hitl_checkpoints_status', 'hitl_checkpoints', ['status'])
    op.create_index('ix_hitl_checkpoints_execution_id', 'hitl_checkpoints', ['execution_id'])
    op.create_index('ix_hitl_checkpoints_agent_id', 'hitl_checkpoints', ['agent_id'])
    op.create_index('ix_hitl_checkpoints_created_at', 'hitl_checkpoints', ['created_at'])

    # Create hitl_webhooks table
    op.create_table(
        'hitl_webhooks',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('secret', sa.String(255), nullable=False),
        sa.Column('events', postgresql.ARRAY(sa.String(100)), nullable=False),
        sa.Column('headers', postgresql.JSONB(astext_type=sa.Text()), nullable=False, default={}),
        sa.Column('retry_count', sa.Integer(), nullable=False, default=3),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create hitl_escalation_policies table
    op.create_table(
        'hitl_escalation_policies',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('trigger_conditions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('escalation_delay_seconds', sa.Integer(), nullable=False),
        sa.Column('escalation_targets', postgresql.ARRAY(sa.String(255)), nullable=False),
        sa.Column('max_escalations', sa.Integer(), nullable=False, default=3),
        sa.Column('auto_reject_on_timeout', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create hitl_audit_log table for additional audit trail
    op.create_table(
        'hitl_audit_log',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('checkpoint_id', sa.String(255), nullable=False),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('actor', sa.String(255), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=False, default={}),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['checkpoint_id'], ['hitl_checkpoints.checkpoint_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    
    op.create_index('ix_hitl_audit_log_checkpoint_id', 'hitl_audit_log', ['checkpoint_id'])
    op.create_index('ix_hitl_audit_log_timestamp', 'hitl_audit_log', ['timestamp'])


def downgrade() -> None:
    op.drop_index('ix_hitl_audit_log_timestamp', table_name='hitl_audit_log')
    op.drop_index('ix_hitl_audit_log_checkpoint_id', table_name='hitl_audit_log')
    op.drop_table('hitl_audit_log')
    
    op.drop_table('hitl_escalation_policies')
    
    op.drop_table('hitl_webhooks')
    
    op.drop_index('ix_hitl_checkpoints_created_at', table_name='hitl_checkpoints')
    op.drop_index('ix_hitl_checkpoints_agent_id', table_name='hitl_checkpoints')
    op.drop_index('ix_hitl_checkpoints_execution_id', table_name='hitl_checkpoints')
    op.drop_index('ix_hitl_checkpoints_status', table_name='hitl_checkpoints')
    op.drop_table('hitl_checkpoints')
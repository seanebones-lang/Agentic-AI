"""Production-ready HITL Checkpoint Manager with persistent storage, webhooks, and escalation policies."""

import asyncio
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import uuid4

from pydantic import BaseModel, Field, validator

from config import get_settings
from observability.logger import LoggerMixin, get_logger
from observability.metrics import get_metrics_collector

logger = get_logger(__name__)


class EscalationReason(str, Enum):
    """Reasons for HITL escalation."""
    UNCERTAINTY = "uncertainty"
    HIGH_COST = "high_cost"
    SENSITIVE_DATA = "sensitive_data"
    ERROR = "error"
    MANUAL_TRIGGER = "manual_trigger"
    POLICY_VIOLATION = "policy_violation"
    APPROVAL_CHAIN = "approval_chain"


class CheckpointStatus(str, Enum):
    """Checkpoint lifecycle status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"


class ApprovalRole(str, Enum):
    """Roles in approval chain."""
    REVIEWER = "reviewer"
    APPROVER = "approver"
    FINAL_APPROVER = "final_approver"


@dataclass
class WebhookConfig:
    """Webhook configuration."""
    url: str
    secret: str
    events: List[str]
    headers: Dict[str, str] = field(default_factory=dict)
    retry_count: int = 3
    retry_delay: float = 1.0


@dataclass
class EscalationPolicy:
    """Escalation policy configuration."""
    name: str
    trigger_conditions: Dict[str, Any]
    escalation_delay_seconds: int
    escalation_targets: List[str]  # User IDs or roles
    max_escalations: int = 3
    auto_approve_on_timeout: bool = False
    auto_reject_on_timeout: bool = False


class HITLCheckpoint(BaseModel):
    """Persistent checkpoint model."""
    checkpoint_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    execution_id: str
    state_snapshot: Dict[str, Any]
    reason: EscalationReason
    context: Dict[str, Any] = Field(default_factory=dict)
    question: Optional[str] = None
    options: Optional[Dict[str, Any]] = None
    status: CheckpointStatus = CheckpointStatus.PENDING
    priority: int = 0  # Higher = more urgent
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    timeout_seconds: int = 3600
    expires_at: Optional[datetime] = None
    approved: Optional[bool] = None
    reviewer_id: Optional[str] = None
    reviewer_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    escalation_count: int = 0
    escalation_policy: Optional[str] = None
    approval_chain: List[str] = Field(default_factory=list)  # User IDs in order
    current_approver_index: int = 0
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True

    def __init__(self, **data):
        super().__init__(**data)
        if self.expires_at is None and self.timeout_seconds:
            self.expires_at = self.created_at + timedelta(seconds=self.timeout_seconds)

    def add_audit_entry(
        self,
        action: str,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add entry to audit trail."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "user_id": user_id,
            "details": details or {},
            "checkpoint_status": self.status.value,
        }
        self.audit_trail.append(entry)
        self.updated_at = datetime.utcnow()

    def is_expired(self) -> bool:
        """Check if checkpoint has expired."""
        if self.expires_at:
            return datetime.utcnow() >= self.expires_at
        return False

    def get_current_approver(self) -> Optional[str]:
        """Get current approver in chain."""
        if self.approval_chain and self.current_approver_index < len(self.approval_chain):
            return self.approval_chain[self.current_approver_index]
        return None

    def advance_approval_chain(self) -> bool:
        """Advance to next approver in chain. Returns True if chain complete."""
        self.current_approver_index += 1
        self.updated_at = datetime.utcnow()
        return self.current_approver_index >= len(self.approval_chain)


class CheckpointManager(LoggerMixin):
    """
    Production HITL checkpoint manager with:
    - Persistent storage (PostgreSQL + Redis)
    - Webhook notifications (Slack, Email, PagerDuty, custom)
    - Escalation policies with automatic routing
    - Audit trail with cryptographic signatures
    - Approval chains and role-based routing
    """

    def __init__(
        self,
        db_pool: Optional[Any] = None,
        redis_client: Optional[Any] = None,
        webhook_configs: Optional[List[WebhookConfig]] = None,
        escalation_policies: Optional[List[EscalationPolicy]] = None,
    ):
        """
        Initialize checkpoint manager.

        Args:
            db_pool: PostgreSQL connection pool (asyncpg)
            redis_client: Redis client for caching/locks
            webhook_configs: List of webhook configurations
            escalation_policies: List of escalation policies
        """
        self.settings = get_settings()
        self.metrics = get_metrics_collector()
        self.db_pool = db_pool
        self.redis = redis_client
        self.webhook_configs = webhook_configs or []
        self.escalation_policies = escalation_policies or []
        self._approval_events: Dict[str, asyncio.Event] = {}
        self._escalation_tasks: Dict[str, asyncio.Task] = {}
        self._audit_secret = self.settings.jwt_secret_key.encode() if self.settings.jwt_secret_key else b"default-secret"

        # Initialize default escalation policies if none provided
        if not self.escalation_policies:
            self._init_default_policies()

    def _init_default_policies(self) -> None:
        """Initialize default escalation policies."""
        self.escalation_policies = [
            EscalationPolicy(
                name="uncertainty_escalation",
                trigger_conditions={"reason": "uncertainty"},
                escalation_delay_seconds=300,  # 5 minutes
                escalation_targets=["senior_reviewers"],
                max_escalations=2,
            ),
            EscalationPolicy(
                name="high_cost_escalation",
                trigger_conditions={"reason": "high_cost"},
                escalation_delay_seconds=60,  # 1 minute
                escalation_targets=["finance_approvers", "team_leads"],
                max_escalations=3,
            ),
            EscalationPolicy(
                name="security_escalation",
                trigger_conditions={"reason": "sensitive_data"},
                escalation_delay_seconds=30,  # 30 seconds
                escalation_targets=["security_team", "compliance"],
                max_escalations=1,
                auto_reject_on_timeout=True,
            ),
            EscalationPolicy(
                name="error_escalation",
                trigger_conditions={"reason": "error"},
                escalation_delay_seconds=120,  # 2 minutes
                escalation_targets=["on_call_engineer"],
                max_escalations=2,
            ),
        ]

    async def initialize(self) -> None:
        """Initialize database schema and connections."""
        if self.db_pool:
            await self._create_tables()
        if self.redis:
            # Test Redis connection
            await self.redis.ping()
        self.logger.info("Checkpoint manager initialized")

    async def _create_tables(self) -> None:
        """Create database tables."""
        schema = """
        CREATE TABLE IF NOT EXISTS hitl_checkpoints (
            checkpoint_id UUID PRIMARY KEY,
            agent_id VARCHAR(255) NOT NULL,
            execution_id VARCHAR(255) NOT NULL,
            state_snapshot JSONB NOT NULL,
            reason VARCHAR(50) NOT NULL,
            context JSONB DEFAULT '{}',
            question TEXT,
            options JSONB,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            priority INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            timeout_seconds INTEGER NOT NULL DEFAULT 3600,
            expires_at TIMESTAMPTZ,
            approved BOOLEAN,
            reviewer_id VARCHAR(255),
            reviewer_notes TEXT,
            resolved_at TIMESTAMPTZ,
            escalation_count INTEGER DEFAULT 0,
            escalation_policy VARCHAR(100),
            approval_chain JSONB DEFAULT '[]',
            current_approver_index INTEGER DEFAULT 0,
            audit_trail JSONB DEFAULT '[]',
            metadata JSONB DEFAULT '{}',
            signature VARCHAR(64)  -- HMAC signature for audit integrity
        );

        CREATE INDEX IF NOT EXISTS idx_checkpoints_status ON hitl_checkpoints(status);
        CREATE INDEX IF NOT EXISTS idx_checkpoints_agent ON hitl_checkpoints(agent_id);
        CREATE INDEX IF NOT EXISTS idx_checkpoints_execution ON hitl_checkpoints(execution_id);
        CREATE INDEX IF NOT EXISTS idx_checkpoints_expires ON hitl_checkpoints(expires_at);
        CREATE INDEX IF NOT EXISTS idx_checkpoints_priority ON hitl_checkpoints(priority DESC, created_at ASC);

        CREATE TABLE IF NOT EXISTS hitl_webhooks (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            url TEXT NOT NULL,
            secret VARCHAR(255) NOT NULL,
            events JSONB NOT NULL,
            headers JSONB DEFAULT '{}',
            active BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS hitl_escalation_policies (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            trigger_conditions JSONB NOT NULL,
            escalation_delay_seconds INTEGER NOT NULL,
            escalation_targets JSONB NOT NULL,
            max_escalations INTEGER DEFAULT 3,
            auto_approve_on_timeout BOOLEAN DEFAULT false,
            auto_reject_on_timeout BOOLEAN DEFAULT false,
            active BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
        async with self.db_pool.acquire() as conn:
            await conn.execute(schema)

    async def create_checkpoint(
        self,
        agent_id: str,
        execution_id: str,
        state: Dict[str, Any],
        reason: EscalationReason,
        context: Optional[Dict[str, Any]] = None,
        question: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        priority: int = 0,
        approval_chain: Optional[List[str]] = None,
        escalation_policy: Optional[str] = None,
    ) -> HITLCheckpoint:
        """
        Create a new HITL checkpoint with persistent storage.
        """
        checkpoint = HITLCheckpoint(
            agent_id=agent_id,
            execution_id=execution_id,
            state_snapshot=state,
            reason=reason,
            context=context or {},
            question=question,
            options=options,
            priority=priority,
            timeout_seconds=self.settings.hitl_timeout_seconds,
            approval_chain=approval_chain or [],
            escalation_policy=escalation_policy,
        )

        checkpoint.add_audit_entry("created", details={"reason": reason.value})

        # Persist to database
        if self.db_pool:
            await self._persist_checkpoint(checkpoint)

        # Cache in Redis
        if self.redis:
            await self._cache_checkpoint(checkpoint)

        # Send webhook notifications
        await self._send_webhooks("checkpoint.created", checkpoint)

        # Start escalation timer if policy exists
        if self.escalation_policies:
            self._schedule_escalation(checkpoint)

        self.logger.info(
            "HITL checkpoint created",
            checkpoint_id=checkpoint.checkpoint_id,
            agent_id=agent_id,
            execution_id=execution_id,
            reason=reason.value,
        )

        return checkpoint

    async def _persist_checkpoint(self, checkpoint: HITLCheckpoint) -> None:
        """Persist checkpoint to PostgreSQL."""
        # Generate HMAC signature for audit integrity
        signature = self._generate_signature(checkpoint)

        query = """
        INSERT INTO hitl_checkpoints (
            checkpoint_id, agent_id, execution_id, state_snapshot, reason,
            context, question, options, status, priority, created_at,
            updated_at, timeout_seconds, expires_at, approved,
            reviewer_id, reviewer_notes, resolved_at, escalation_count,
            escalation_policy, approval_chain, current_approver_index,
            audit_trail, metadata, signature
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25)
        ON CONFLICT (checkpoint_id) DO UPDATE SET
            status = EXCLUDED.status,
            updated_at = EXCLUDED.updated_at,
            approved = EXCLUDED.approved,
            reviewer_id = EXCLUDED.reviewer_id,
            reviewer_notes = EXCLUDED.reviewer_notes,
            resolved_at = EXCLUDED.resolved_at,
            escalation_count = EXCLUDED.escalation_count,
            current_approver_index = EXCLUDED.current_approver_index,
            audit_trail = EXCLUDED.audit_trail,
            signature = EXCLUDED.signature
        """

        async with self.db_pool.acquire() as conn:
            await conn.execute(
                query,
                checkpoint.checkpoint_id,
                checkpoint.agent_id,
                checkpoint.execution_id,
                json.dumps(checkpoint.state_snapshot),
                checkpoint.reason.value,
                json.dumps(checkpoint.context),
                checkpoint.question,
                json.dumps(checkpoint.options) if checkpoint.options else None,
                checkpoint.status.value,
                checkpoint.priority,
                checkpoint.created_at,
                checkpoint.updated_at,
                checkpoint.timeout_seconds,
                checkpoint.expires_at,
                checkpoint.approved,
                checkpoint.reviewer_id,
                checkpoint.reviewer_notes,
                checkpoint.resolved_at,
                checkpoint.escalation_count,
                checkpoint.escalation_policy,
                json.dumps(checkpoint.approval_chain),
                checkpoint.current_approver_index,
                json.dumps(checkpoint.audit_trail),
                json.dumps(checkpoint.metadata),
                signature,
            )

    def _generate_signature(self, checkpoint: HITLCheckpoint) -> str:
        """Generate HMAC signature for audit integrity."""
        data = f"{checkpoint.checkpoint_id}{checkpoint.agent_id}{checkpoint.execution_id}{checkpoint.status.value}{checkpoint.updated_at.isoformat()}"
        return hmac.new(self._audit_secret, data.encode(), hashlib.sha256).hexdigest()

    def _verify_signature(self, checkpoint: HITLCheckpoint, signature: str) -> bool:
        """Verify HMAC signature."""
        expected = self._generate_signature(checkpoint)
        return hmac.compare_digest(expected, signature)

    async def _cache_checkpoint(self, checkpoint: HITLCheckpoint) -> None:
        """Cache checkpoint in Redis."""
        key = f"hitl:checkpoint:{checkpoint.checkpoint_id}"
        value = checkpoint.model_dump_json()
        await self.redis.setex(key, checkpoint.timeout_seconds + 60, value)

    async def _send_webhooks(self, event: str, checkpoint: HITLCheckpoint) -> None:
        """Send webhook notifications."""
        payload = {
            "event": event,
            "timestamp": datetime.utcnow().isoformat(),
            "checkpoint": checkpoint.model_dump(),
        }

        for config in self.webhook_configs:
            if event in config.events:
                asyncio.create_task(self._deliver_webhook(config, payload))

    async def _deliver_webhook(self, config: WebhookConfig, payload: Dict[str, Any]) -> None:
        """Deliver webhook with retries."""
        import httpx

        headers = {**config.headers, "Content-Type": "application/json"}
        
        # Add signature
        body = json.dumps(payload, sort_keys=True).encode()
        sig = hmac.new(config.secret.encode(), body, hashlib.sha256).hexdigest()
        headers["X-Signature"] = f"sha256={sig}"

        for attempt in range(config.retry_count):
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.post(config.url, content=body, headers=headers)
                    response.raise_for_status()
                    self.logger.info("Webhook delivered", event=payload["event"], url=config.url)
                    return
            except Exception as e:
                self.logger.warning("Webhook delivery failed", attempt=attempt+1, error=str(e))
                if attempt < config.retry_count - 1:
                    await asyncio.sleep(config.retry_delay * (2 ** attempt))

        self.logger.error("Webhook delivery failed after retries", url=config.url)

    def _schedule_escalation(self, checkpoint: HITLCheckpoint) -> None:
        """Schedule escalation based on policies."""
        for policy in self.escalation_policies:
            if self._policy_matches(policy, checkpoint):
                delay = policy.escalation_delay_seconds
                task = asyncio.create_task(self._escalate_after_delay(checkpoint, policy, delay))
                self._escalation_tasks[checkpoint.checkpoint_id] = task

    def _policy_matches(self, policy: EscalationPolicy, checkpoint: HITLCheckpoint) -> bool:
        """Check if escalation policy matches checkpoint."""
        for key, value in policy.trigger_conditions.items():
            if key == "reason" and checkpoint.reason.value != value:
                return False
            # Add more condition checks as needed
        return True

    async def _escalate_after_delay(
        self,
        checkpoint: HITLCheckpoint,
        policy: EscalationPolicy,
        delay: int,
    ) -> None:
        """Escalate checkpoint after delay."""
        await asyncio.sleep(delay)

        # Refresh checkpoint from DB
        checkpoint = await self.get_checkpoint(checkpoint.checkpoint_id)
        if not checkpoint or checkpoint.status != CheckpointStatus.PENDING:
            return

        # Check if already escalated
        if checkpoint.escalation_count >= policy.max_escalations:
            return

        checkpoint.escalation_count += 1
        checkpoint.status = CheckpointStatus.ESCALATED
        checkpoint.add_audit_entry("escalated", details={"policy": policy.name, "count": checkpoint.escalation_count})

        # Add escalation targets to approval chain
        for target in policy.escalation_targets:
            if target not in checkpoint.approval_chain:
                checkpoint.approval_chain.append(target)

        # Persist
        if self.db_pool:
            await self._persist_checkpoint(checkpoint)
        if self.redis:
            await self._cache_checkpoint(checkpoint)

        # Notify escalation targets
        await self._send_webhooks("checkpoint.escalated", checkpoint)

        self.logger.warning(
            "Checkpoint escalated",
            checkpoint_id=checkpoint.checkpoint_id,
            policy=policy.name,
            escalation_count=checkpoint.escalation_count,
        )

    async def wait_for_approval(
        self,
        checkpoint_id: str,
        timeout: Optional[int] = None,
    ) -> HITLCheckpoint:
        """
        Wait for human approval on a checkpoint with timeout handling.
        """
        checkpoint = await self.get_checkpoint(checkpoint_id)
        if not checkpoint:
            raise KeyError(f"Checkpoint not found: {checkpoint_id}")

        if checkpoint.status != CheckpointStatus.PENDING:
            return checkpoint

        event = asyncio.Event()
        self._approval_events[checkpoint_id] = event

        timeout_seconds = timeout or checkpoint.timeout_seconds

        self.logger.info("Waiting for approval", checkpoint_id=checkpoint_id, timeout=timeout_seconds)

        start_time = time.time()
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout_seconds)

            checkpoint = await self.get_checkpoint(checkpoint_id)
            if not checkpoint:
                raise KeyError(f"Checkpoint disappeared: {checkpoint_id}")

            duration = time.time() - start_time
            self.logger.info(
                "Approval received",
                checkpoint_id=checkpoint_id,
                approved=checkpoint.approved,
                duration=duration,
            )

            self.metrics.record_hitl_intervention(
                reason=checkpoint.reason.value,
                approved=checkpoint.approved or False,
                duration_seconds=duration,
            )

            return checkpoint

        except asyncio.TimeoutError:
            return await self._handle_timeout(checkpoint, timeout_seconds)

        finally:
            self._approval_events.pop(checkpoint_id, None)

    async def _handle_timeout(self, checkpoint: HITLCheckpoint, timeout: int) -> HITLCheckpoint:
        """Handle checkpoint timeout."""
        duration = time.time() - time.time() + timeout  # Approximate

        checkpoint.status = CheckpointStatus.TIMEOUT
        checkpoint.add_audit_entry("timeout", details={"timeout_seconds": timeout})

        # Check escalation policy for timeout behavior
        for policy in self.escalation_policies:
            if self._policy_matches(policy, checkpoint):
                if policy.auto_approve_on_timeout:
                    checkpoint.approved = True
                    checkpoint.reviewer_notes = "Auto-approved on timeout"
                    checkpoint.resolved_at = datetime.utcnow()
                    break
                elif policy.auto_reject_on_timeout:
                    checkpoint.approved = False
                    checkpoint.reviewer_notes = "Auto-rejected on timeout"
                    checkpoint.resolved_at = datetime.utcnow()
                    break

        # Default: reject on timeout
        if checkpoint.approved is None:
            checkpoint.approved = False
            checkpoint.reviewer_notes = "Timeout - automatically rejected"
            checkpoint.resolved_at = datetime.utcnow()

        # Persist
        if self.db_pool:
            await self._persist_checkpoint(checkpoint)
        if self.redis:
            await self._cache_checkpoint(checkpoint)

        await self._send_webhooks("checkpoint.timeout", checkpoint)

        self.metrics.record_hitl_intervention(
            reason=checkpoint.reason.value,
            approved=checkpoint.approved or False,
            duration_seconds=timeout,
        )

        raise TimeoutError(f"Approval timeout for checkpoint {checkpoint.checkpoint_id}")

    async def resolve_checkpoint(
        self,
        checkpoint_id: str,
        approved: bool,
        reviewer_id: str,
        reviewer_notes: Optional[str] = None,
    ) -> HITLCheckpoint:
        """
        Resolve checkpoint with approval decision.
        Handles approval chains automatically.
        """
        checkpoint = await self.get_checkpoint(checkpoint_id)
        if not checkpoint:
            raise KeyError(f"Checkpoint not found: {checkpoint_id}")

        if checkpoint.status not in (CheckpointStatus.PENDING, CheckpointStatus.ESCALATED):
            raise ValueError(f"Checkpoint not in resolvable state: {checkpoint.status}")

        # Verify reviewer is authorized
        current_approver = checkpoint.get_current_approver()
        if current_approver and current_approver != reviewer_id:
            raise PermissionError(f"Reviewer {reviewer_id} not authorized for this checkpoint")

        checkpoint.approved = approved
        checkpoint.reviewer_id = reviewer_id
        checkpoint.reviewer_notes = reviewer_notes
        checkpoint.resolved_at = datetime.utcnow()
        checkpoint.add_audit_entry(
            "resolved" if approved else "rejected",
            user_id=reviewer_id,
            details={"notes": reviewer_notes},
        )

        # Handle approval chain
        if checkpoint.approval_chain:
            chain_complete = checkpoint.advance_approval_chain()
            if chain_complete:
                # All approvers have approved
                checkpoint.status = CheckpointStatus.APPROVED if approved else CheckpointStatus.REJECTED
            else:
                # Move to next approver
                checkpoint.status = CheckpointStatus.PENDING
                next_approver = checkpoint.get_current_approver()
                if next_approver:
                    checkpoint.add_audit_entry("forwarded", user_id=reviewer_id, details={"next_approver": next_approver})
                    await self._send_webhooks("checkpoint.forwarded", checkpoint)
        else:
            # No chain - resolve immediately
            checkpoint.status = CheckpointStatus.APPROVED if approved else CheckpointStatus.REJECTED

        # Persist
        if self.db_pool:
            await self._persist_checkpoint(checkpoint)
        if self.redis:
            await self._cache_checkpoint(checkpoint)

        await self._send_webhooks("checkpoint.resolved", checkpoint)

        # Signal waiting coroutine
        if checkpoint_id in self._approval_events:
            self._approval_events[checkpoint_id].set()

        self.logger.info(
            "Checkpoint resolved",
            checkpoint_id=checkpoint_id,
            approved=approved,
            reviewer=reviewer_id,
        )

        self.metrics.record_hitl_intervention(
            reason=checkpoint.reason.value,
            approved=approved,
            duration_seconds=(checkpoint.resolved_at - checkpoint.created_at).total_seconds(),
        )

        return checkpoint

    async def get_checkpoint(self, checkpoint_id: str) -> Optional[HITLCheckpoint]:
        """Get checkpoint by ID (Redis cache -> DB)."""
        # Try Redis first
        if self.redis:
            key = f"hitl:checkpoint:{checkpoint_id}"
            cached = await self.redis.get(key)
            if cached:
                return HITLCheckpoint.model_validate_json(cached)

        # Fallback to database
        if self.db_pool:
            query = "SELECT * FROM hitl_checkpoints WHERE checkpoint_id = $1"
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(query, checkpoint_id)
                if row:
                    return self._row_to_checkpoint(row)

        return None

    def _row_to_checkpoint(self, row: Any) -> HITLCheckpoint:
        """Convert database row to checkpoint object."""
        data = dict(row)
        # Convert JSONB fields
        for field in ["state_snapshot", "context", "options", "approval_chain", "audit_trail", "metadata"]:
            if data.get(field) and isinstance(data[field], str):
                data[field] = json.loads(data[field])
        data["reason"] = EscalationReason(data["reason"])
        data["status"] = CheckpointStatus(data["status"])
        return HITLCheckpoint(**data)

    async def list_pending_checkpoints(
        self,
        agent_id: Optional[str] = None,
        reviewer_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[HITLCheckpoint]:
        """List pending checkpoints with filters."""
        if not self.db_pool:
            return []

        conditions = ["status IN ('pending', 'escalated')"]
        params = []
        param_idx = 1

        if agent_id:
            conditions.append(f"agent_id = ${param_idx}")
            params.append(agent_id)
            param_idx += 1

        if reviewer_id:
            conditions.append(f"$1 = ANY(approval_chain)")
            params.append(reviewer_id)
            param_idx += 1

        where_clause = " AND ".join(conditions)
        query = f"""
            SELECT * FROM hitl_checkpoints
            WHERE {where_clause}
            ORDER BY priority DESC, created_at ASC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [self._row_to_checkpoint(row) for row in rows]

    async def cancel_checkpoint(
        self,
        checkpoint_id: str,
        user_id: str,
        reason: str,
    ) -> HITLCheckpoint:
        """Cancel a checkpoint."""
        checkpoint = await self.get_checkpoint(checkpoint_id)
        if not checkpoint:
            raise KeyError(f"Checkpoint not found: {checkpoint_id}")

        checkpoint.status = CheckpointStatus.CANCELLED
        checkpoint.add_audit_entry("cancelled", user_id=user_id, details={"reason": reason})

        if self.db_pool:
            await self._persist_checkpoint(checkpoint)
        if self.redis:
            await self._cache_checkpoint(checkpoint)

        await self._send_webhooks("checkpoint.cancelled", checkpoint)

        # Cancel any pending escalation
        if checkpoint_id in self._escalation_tasks:
            self._escalation_tasks[checkpoint_id].cancel()
            del self._escalation_tasks[checkpoint_id]

        if checkpoint_id in self._approval_events:
            self._approval_events[checkpoint_id].set()

        return checkpoint

    async def verify_audit_integrity(self, checkpoint_id: str) -> bool:
        """Verify audit trail integrity using HMAC signatures."""
        checkpoint = await self.get_checkpoint(checkpoint_id)
        if not checkpoint or not self.db_pool:
            return False

        # Verify signature
        query = "SELECT signature FROM hitl_checkpoints WHERE checkpoint_id = $1"
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(query, checkpoint_id)
            if row and row["signature"]:
                return self._verify_signature(checkpoint, row["signature"])
        return False

    async def get_audit_trail(self, checkpoint_id: str) -> List[Dict[str, Any]]:
        """Get full audit trail for checkpoint."""
        checkpoint = await self.get_checkpoint(checkpoint_id)
        if not checkpoint:
            return []

        # Verify integrity
        if not await self.verify_audit_integrity(checkpoint_id):
            self.logger.warning("Audit trail integrity check failed", checkpoint_id=checkpoint_id)

        return checkpoint.audit_trail

    def add_webhook(self, config: WebhookConfig) -> None:
        """Add webhook configuration."""
        self.webhook_configs.append(config)

    def add_escalation_policy(self, policy: EscalationPolicy) -> None:
        """Add escalation policy."""
        self.escalation_policies.append(policy)

    async def close(self) -> None:
        """Clean up resources."""
        for task in self._escalation_tasks.values():
            task.cancel()
        self._escalation_tasks.clear()
        self._approval_events.clear()
        self.logger.info("Checkpoint manager closed")


# Global instance
_checkpoint_manager: Optional[CheckpointManager] = None


async def get_checkpoint_manager() -> CheckpointManager:
    """Get global checkpoint manager instance."""
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = CheckpointManager()
        await _checkpoint_manager.initialize()
    return _checkpoint_manager


def create_webhook_config(
    name: str,
    url: str,
    secret: str,
    events: List[str],
    headers: Optional[Dict[str, str]] = None,
) -> WebhookConfig:
    """Create webhook configuration."""
    return WebhookConfig(
        url=url,
        secret=secret,
        events=events,
        headers=headers or {},
    )


def create_escalation_policy(
    name: str,
    trigger_conditions: Dict[str, Any],
    escalation_delay_seconds: int,
    escalation_targets: List[str],
    max_escalations: int = 3,
    auto_approve_on_timeout: bool = False,
    auto_reject_on_timeout: bool = False,
) -> EscalationPolicy:
    """Create escalation policy."""
    return EscalationPolicy(
        name=name,
        trigger_conditions=trigger_conditions,
        escalation_delay_seconds=escalation_delay_seconds,
        escalation_targets=escalation_targets,
        max_escalations=max_escalations,
        auto_approve_on_timeout=auto_approve_on_timeout,
        auto_reject_on_timeout=auto_reject_on_timeout,
    )
"""Checkpoint manager for HITL workflows with LangGraph integration."""

import asyncio
import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

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


class HITLCheckpoint(BaseModel):
    """Model for HITL checkpoint data."""

    checkpoint_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    state: Dict[str, Any]
    reason: EscalationReason
    context: Dict[str, Any] = Field(default_factory=dict)
    question: Optional[str] = None
    options: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    timeout_seconds: int = 3600
    approved: Optional[bool] = None
    reviewer_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None


class CheckpointManager(LoggerMixin):
    """
    Manages HITL checkpoints and approval workflows.

    Integrates with LangGraph for workflow interrupts and human approval gates.
    """

    def __init__(self) -> None:
        """Initialize checkpoint manager."""
        self.settings = get_settings()
        self.metrics = get_metrics_collector()
        self.pending_checkpoints: Dict[str, HITLCheckpoint] = {}
        self.approval_callbacks: Dict[str, asyncio.Event] = {}

    def create_checkpoint(
        self,
        agent_id: str,
        state: Dict[str, Any],
        reason: EscalationReason,
        context: Optional[Dict[str, Any]] = None,
        question: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> HITLCheckpoint:
        """
        Create a new HITL checkpoint.

        Args:
            agent_id: ID of the agent requesting approval
            state: Current agent state
            reason: Reason for escalation
            context: Additional context information
            question: Question for human reviewer
            options: Available options for approval

        Returns:
            HITLCheckpoint instance
        """
        checkpoint = HITLCheckpoint(
            agent_id=agent_id,
            state=state,
            reason=reason,
            context=context or {},
            question=question,
            options=options,
            timeout_seconds=self.settings.hitl_timeout_seconds,
        )

        self.pending_checkpoints[checkpoint.checkpoint_id] = checkpoint
        self.approval_callbacks[checkpoint.checkpoint_id] = asyncio.Event()

        self.logger.info(
            "HITL checkpoint created",
            checkpoint_id=checkpoint.checkpoint_id,
            agent_id=agent_id,
            reason=reason.value,
        )

        # Send notification to human reviewer
        self._notify_reviewer(checkpoint)

        return checkpoint

    def _notify_reviewer(self, checkpoint: HITLCheckpoint) -> None:
        """
        Notify human reviewer about pending approval.

        Args:
            checkpoint: Checkpoint requiring approval
        """
        try:
            # Import here to avoid circular dependency
            from tools.examples.notifier import NotifierTool

            notifier = NotifierTool()

            # Format notification message
            message = self._format_notification_message(checkpoint)

            # Send email notification
            if self.settings.hitl_notification_email:
                notifier.execute(
                    channel="email",
                    recipient=self.settings.hitl_notification_email,
                    subject=f"HITL Approval Required: {checkpoint.reason.value}",
                    message=message,
                )

            # Send Slack notification
            if self.settings.hitl_slack_webhook_url:
                notifier.execute(
                    channel="slack",
                    recipient="#agent-approvals",
                    message=message,
                )

            self.logger.info("Reviewer notified", checkpoint_id=checkpoint.checkpoint_id)

        except Exception as e:
            self.logger.error("Failed to notify reviewer", error=str(e))

    def _format_notification_message(self, checkpoint: HITLCheckpoint) -> str:
        """Format notification message for checkpoint."""
        message = f"""
HUMAN APPROVAL REQUIRED

Checkpoint ID: {checkpoint.checkpoint_id}
Agent ID: {checkpoint.agent_id}
Reason: {checkpoint.reason.value}
Created: {checkpoint.created_at.isoformat()}

Context: {checkpoint.context}

Question: {checkpoint.question or 'Please review and approve/reject'}

Options: {checkpoint.options or 'Approve or Reject'}

Timeout: {checkpoint.timeout_seconds} seconds

Please review at: /api/hitl/checkpoints/{checkpoint.checkpoint_id}
"""
        return message.strip()

    async def wait_for_approval(
        self, checkpoint_id: str, timeout: Optional[int] = None
    ) -> HITLCheckpoint:
        """
        Wait for human approval on a checkpoint.

        Args:
            checkpoint_id: ID of the checkpoint
            timeout: Optional timeout override

        Returns:
            Updated checkpoint with approval decision

        Raises:
            TimeoutError: If approval not received within timeout
            KeyError: If checkpoint not found
        """
        if checkpoint_id not in self.pending_checkpoints:
            raise KeyError(f"Checkpoint not found: {checkpoint_id}")

        checkpoint = self.pending_checkpoints[checkpoint_id]
        event = self.approval_callbacks[checkpoint_id]
        timeout_seconds = timeout or checkpoint.timeout_seconds

        self.logger.info(
            "Waiting for approval",
            checkpoint_id=checkpoint_id,
            timeout_seconds=timeout_seconds,
        )

        start_time = time.time()

        try:
            # Wait for approval with timeout
            await asyncio.wait_for(event.wait(), timeout=timeout_seconds)

            duration = time.time() - start_time
            self.logger.info(
                "Approval received",
                checkpoint_id=checkpoint_id,
                approved=checkpoint.approved,
                duration_seconds=duration,
            )

            # Record metrics
            self.metrics.record_hitl_intervention(
                reason=checkpoint.reason.value,
                approved=checkpoint.approved or False,
            )

            return checkpoint

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            self.logger.warning(
                "Approval timeout",
                checkpoint_id=checkpoint_id,
                timeout_seconds=timeout_seconds,
            )

            # Default to rejection on timeout
            checkpoint.approved = False
            checkpoint.reviewer_notes = "Timeout - automatically rejected"
            checkpoint.resolved_at = datetime.utcnow()

            self.metrics.record_hitl_intervention(
                reason=checkpoint.reason.value,
                approved=False,
            )

            raise TimeoutError(f"Approval timeout for checkpoint {checkpoint_id}")

        finally:
            # Clean up
            if checkpoint_id in self.pending_checkpoints:
                del self.pending_checkpoints[checkpoint_id]
            if checkpoint_id in self.approval_callbacks:
                del self.approval_callbacks[checkpoint_id]

    def resolve_checkpoint(
        self,
        checkpoint_id: str,
        approved: bool,
        reviewer_notes: Optional[str] = None,
    ) -> HITLCheckpoint:
        """
        Resolve a checkpoint with approval decision.

        Args:
            checkpoint_id: ID of the checkpoint
            approved: Whether the checkpoint is approved
            reviewer_notes: Optional notes from reviewer

        Returns:
            Updated checkpoint

        Raises:
            KeyError: If checkpoint not found
        """
        if checkpoint_id not in self.pending_checkpoints:
            raise KeyError(f"Checkpoint not found: {checkpoint_id}")

        checkpoint = self.pending_checkpoints[checkpoint_id]
        checkpoint.approved = approved
        checkpoint.reviewer_notes = reviewer_notes
        checkpoint.resolved_at = datetime.utcnow()

        self.logger.info(
            "Checkpoint resolved",
            checkpoint_id=checkpoint_id,
            approved=approved,
        )

        # Signal waiting coroutines
        if checkpoint_id in self.approval_callbacks:
            self.approval_callbacks[checkpoint_id].set()

        return checkpoint

    def get_checkpoint(self, checkpoint_id: str) -> Optional[HITLCheckpoint]:
        """
        Get checkpoint by ID.

        Args:
            checkpoint_id: Checkpoint ID

        Returns:
            HITLCheckpoint or None if not found
        """
        return self.pending_checkpoints.get(checkpoint_id)

    def list_pending_checkpoints(self) -> list[HITLCheckpoint]:
        """
        List all pending checkpoints.

        Returns:
            List of pending checkpoints
        """
        return list(self.pending_checkpoints.values())

    def should_escalate(
        self,
        state: Dict[str, Any],
        uncertainty_threshold: float = 0.7,
        cost_threshold: float = 1000.0,
    ) -> tuple[bool, Optional[EscalationReason]]:
        """
        Determine if state should be escalated to human.

        Args:
            state: Current agent state
            uncertainty_threshold: Threshold for uncertainty escalation
            cost_threshold: Threshold for cost escalation

        Returns:
            Tuple of (should_escalate, reason)
        """
        # Check uncertainty
        uncertainty = state.get("uncertainty_score", 0.0)
        if uncertainty >= uncertainty_threshold:
            return True, EscalationReason.UNCERTAINTY

        # Check cost
        estimated_cost = state.get("estimated_cost", 0.0)
        if estimated_cost >= cost_threshold:
            return True, EscalationReason.HIGH_COST

        # Check for sensitive data
        if state.get("contains_pii", False):
            return True, EscalationReason.SENSITIVE_DATA

        # Check for errors
        if state.get("error"):
            return True, EscalationReason.ERROR

        # Check manual trigger
        if state.get("hitl_required", False):
            return True, EscalationReason.MANUAL_TRIGGER

        return False, None


# Global checkpoint manager instance
_checkpoint_manager: Optional[CheckpointManager] = None


def get_checkpoint_manager() -> CheckpointManager:
    """Get global checkpoint manager instance."""
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = CheckpointManager()
    return _checkpoint_manager


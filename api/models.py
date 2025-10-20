"""Pydantic models for API request/response validation."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentExecuteRequest(BaseModel):
    """Request model for agent execution."""

    goal: str = Field(..., description="The agent's goal or objective")
    initial_state: Dict[str, Any] = Field(
        default_factory=dict, description="Initial state for the agent"
    )
    agent_type: str = Field(default="simple", description="Type of agent to use")
    tools: List[str] = Field(default_factory=list, description="List of tool names to enable")
    max_iterations: int = Field(default=10, ge=1, le=100, description="Maximum iterations")
    uncertainty_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Threshold for HITL escalation"
    )


class AgentExecuteResponse(BaseModel):
    """Response model for agent execution."""

    execution_id: str = Field(..., description="Unique execution ID")
    status: str = Field(..., description="Execution status")
    result: Optional[Dict[str, Any]] = Field(None, description="Execution result")
    error: Optional[str] = Field(None, description="Error message if failed")
    duration_seconds: float = Field(..., description="Execution duration")
    steps_taken: int = Field(..., description="Number of steps executed")


class AgentStatusResponse(BaseModel):
    """Response model for agent status check."""

    execution_id: str
    status: str
    progress: float = Field(..., ge=0.0, le=1.0, description="Execution progress (0-1)")
    current_step: int
    total_steps: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ApprovalRequest(BaseModel):
    """Request model for HITL approval."""

    checkpoint_id: str = Field(..., description="Checkpoint ID to approve/reject")
    approved: bool = Field(..., description="Whether to approve the checkpoint")
    reviewer_notes: Optional[str] = Field(None, description="Optional notes from reviewer")
    reviewer_id: Optional[str] = Field(None, description="ID of the reviewer")


class ApprovalResponse(BaseModel):
    """Response model for HITL approval."""

    checkpoint_id: str
    approved: bool
    resolved_at: datetime
    message: str


class CheckpointListResponse(BaseModel):
    """Response model for listing checkpoints."""

    checkpoints: List[Dict[str, Any]]
    total_count: int
    pending_count: int


class AgentHistoryResponse(BaseModel):
    """Response model for agent execution history."""

    execution_id: str
    agent_type: str
    goal: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    steps_taken: int
    result: Optional[Dict[str, Any]]
    error: Optional[str]


class HealthCheckResponse(BaseModel):
    """Response model for health check."""

    status: str
    version: str
    timestamp: datetime
    services: Dict[str, str] = Field(
        default_factory=dict, description="Status of dependent services"
    )


class ErrorResponse(BaseModel):
    """Response model for errors."""

    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


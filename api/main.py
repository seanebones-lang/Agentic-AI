"""FastAPI main application for agent orchestration."""

import time
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agents.base_agent import SimpleAgent
from api.middleware import LoggingMiddleware, RateLimitMiddleware, get_api_key, require_permission, Permission
from api.models import (
    AgentExecuteRequest,
    AgentExecuteResponse,
    AgentStatusResponse,
    ApprovalRequest,
    ApprovalResponse,
    CheckpointListResponse,
    AgentHistoryResponse,
    HealthCheckResponse,
    ErrorResponse,
)
from config import get_settings
from hitl.checkpoint_manager_v2 import CheckpointManager, WebhookConfig, EscalationPolicy
from memory.memory_manager import MemoryManager
from observability.logger import get_logger, setup_logging, set_correlation_id
from observability.metrics import get_metrics_collector
from observability.tracing import setup_tracing
from tools.tool_manager import ToolManager
from tools.examples import APICallerTool, DatabaseQueryTool, FileOperationsTool, NotifierTool, CodeExecutionTool, WebSearchTool, VectorSearchTool, BrowserTool, ShellTool

# Initialize logging and tracing
setup_logging()
setup_tracing()

logger = get_logger(__name__)
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="Agentic AI Starter Template",
    description="Production-ready API for autonomous AI agents with HITL oversight",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
if settings.enable_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Add custom middleware
app.add_middleware(LoggingMiddleware)
if settings.rate_limit_enabled:
    app.add_middleware(RateLimitMiddleware)

# Global state
executions: Dict[str, Dict] = {}
_checkpoint_manager: Optional[CheckpointManager] = None

# Tool manager (reused across requests)
tool_manager = ToolManager()
tool_manager.register_tool(APICallerTool())
tool_manager.register_tool(DatabaseQueryTool())
tool_manager.register_tool(FileOperationsTool())
tool_manager.register_tool(NotifierTool())
tool_manager.register_tool(CodeExecutionTool())
tool_manager.register_tool(WebSearchTool())
tool_manager.register_tool(VectorSearchTool())
tool_manager.register_tool(BrowserTool())
tool_manager.register_tool(ShellTool())

# Memory manager (reused)
memory_manager = MemoryManager()


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize services on startup."""
    global _checkpoint_manager
    logger.info("Starting Agentic AI API", environment=settings.environment)

    # Initialize v2 checkpoint manager with DB and Redis
    try:
        import redis.asyncio as redis
        from asyncpg import create_pool

        redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        db_pool = await create_pool(
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=settings.postgres_user,
            password=settings.postgres_password,
            database=settings.postgres_db,
        )

        webhook_configs = [
            WebhookConfig(
                url=settings.hitl_slack_webhook_url or "",
                secret=settings.hitl_webhook_secret or "default",
                events=["checkpoint.created", "checkpoint.resolved", "checkpoint.escalated"],
            )
        ] if settings.hitl_slack_webhook_url else []

        escalation_policies = [
            EscalationPolicy(
                name="uncertainty_escalation",
                trigger_conditions={"reason": "uncertainty"},
                escalation_delay_seconds=300,
                escalation_targets=["senior_reviewers"],
                max_escalations=2,
            ),
            EscalationPolicy(
                name="high_cost_escalation",
                trigger_conditions={"reason": "high_cost"},
                escalation_delay_seconds=60,
                escalation_targets=["finance_approvers", "team_leads"],
                max_escalations=3,
            ),
            EscalationPolicy(
                name="security_escalation",
                trigger_conditions={"reason": "sensitive_data"},
                escalation_delay_seconds=30,
                escalation_targets=["security_team", "compliance"],
                max_escalations=1,
                auto_reject_on_timeout=True,
            ),
            EscalationPolicy(
                name="error_escalation",
                trigger_conditions={"reason": "error"},
                escalation_delay_seconds=120,
                escalation_targets=["on_call_engineer"],
                max_escalations=2,
            ),
        ]

        _checkpoint_manager = CheckpointManager(
            db_pool=db_pool,
            redis_client=redis_client,
            webhook_configs=webhook_configs,
            escalation_policies=escalation_policies,
        )
        await _checkpoint_manager.initialize()
        logger.info("HITL v2 checkpoint manager initialized")

    except Exception as e:
        logger.warning("Failed to initialize HITL v2 (will use in-memory fallback)", error=str(e))
        _checkpoint_manager = None


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Cleanup on shutdown."""
    logger.info("Shutting down Agentic AI API")
    metrics = get_metrics_collector()
    metrics.publish_metrics()


def get_checkpoint_manager_v2() -> CheckpointManager:
    """Get or create v2 checkpoint manager instance."""
    global _checkpoint_manager
    if _checkpoint_manager is None:
        # Fallback to in-memory if v2 not initialized
        from hitl.checkpoint_manager import CheckpointManager as LegacyCheckpointManager
        return LegacyCheckpointManager()
    return _checkpoint_manager


@app.get("/", response_model=HealthCheckResponse)
async def root() -> HealthCheckResponse:
    """Root endpoint with health check."""
    return HealthCheckResponse(
        status="healthy",
        version="0.1.0",
        timestamp=datetime.utcnow(),
        services={
            "api": "operational",
            "hitl": "operational" if settings.hitl_enabled else "disabled",
        },
    )


@app.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """Health check endpoint."""
    services = {
        "api": "operational",
        "redis": "unknown",  # Would check Redis connection in production
        "vector_db": "unknown",  # Would check vector DB connection
    }

    return HealthCheckResponse(
        status="healthy",
        version="0.1.0",
        timestamp=datetime.utcnow(),
        services=services,
    )


@app.get("/health/ready")
async def readiness_check() -> dict:
    """Readiness check with dependency verification."""
    checks = {
        "api": "healthy",
        "redis": "unknown",
        "postgres": "unknown",
        "vector_db": "unknown",
    }
    
    overall_status = "healthy"
    
    # Check Redis
    try:
        import redis.asyncio as redis
        redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        await redis_client.ping()
        await redis_client.close()
        checks["redis"] = "healthy"
    except Exception:
        checks["redis"] = "unhealthy"
        overall_status = "degraded"
    
    # Check PostgreSQL
    try:
        from asyncpg import create_pool
        pool = await create_pool(
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=settings.postgres_user,
            password=settings.postgres_password,
            database=settings.postgres_db,
        )
        await pool.close()
        checks["postgres"] = "healthy"
    except Exception:
        checks["postgres"] = "unhealthy"
        overall_status = "degraded"
    
    return {
        "status": overall_status,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus metrics endpoint."""
    metrics = get_metrics_collector()
    return metrics.export_prometheus()


@app.post("/agents/execute", response_model=AgentExecuteResponse)
async def execute_agent(
    request: AgentExecuteRequest,
    api_key: str = Depends(get_api_key),
) -> AgentExecuteResponse:
    """
    Execute an agent with the specified goal and configuration.

    Requires API key authentication.
    """
    execution_id = str(uuid4())
    set_correlation_id(execution_id)

    logger.info(
        "Agent execution requested",
        execution_id=execution_id,
        goal=request.goal,
        agent_type=request.agent_type,
    )

    start_time = time.time()

    try:
        # Create agent with shared tool manager and memory manager
        agent = SimpleAgent(
            tools=list(tool_manager.tools.values()),
            memory_manager=memory_manager,
            max_iterations=request.max_iterations,
            uncertainty_threshold=request.uncertainty_threshold,
        )

        # Prepare initial state
        initial_state = {
            "goal": request.goal,
            **request.initial_state,
        }

        # Execute agent (async)
        final_state = await agent.arun(initial_state)

        duration = time.time() - start_time

        # Store execution result
        executions[execution_id] = {
            "execution_id": execution_id,
            "agent_type": request.agent_type,
            "goal": request.goal,
            "status": "completed" if not final_state.get("error") else "failed",
            "result": final_state,
            "started_at": datetime.utcnow(),
            "duration_seconds": duration,
            "steps_taken": final_state.get("current_step", 0),
        }

        logger.info(
            "Agent execution completed",
            execution_id=execution_id,
            duration_seconds=duration,
            status=executions[execution_id]["status"],
        )

        return AgentExecuteResponse(
            execution_id=execution_id,
            status=executions[execution_id]["status"],
            result=final_state,
            error=final_state.get("error"),
            duration_seconds=duration,
            steps_taken=final_state.get("current_step", 0),
        )

    except Exception as e:
        duration = time.time() - start_time
        logger.error("Agent execution failed", execution_id=execution_id, error=str(e))

        executions[execution_id] = {
            "execution_id": execution_id,
            "status": "failed",
            "error": str(e),
            "started_at": datetime.utcnow(),
            "duration_seconds": duration,
        }

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent execution failed: {str(e)}",
        )


@app.get("/agents/{execution_id}/status", response_model=AgentStatusResponse)
async def get_agent_status(
    execution_id: str,
    api_key: str = Depends(get_api_key),
) -> AgentStatusResponse:
    """Get status of an agent execution."""
    if execution_id not in executions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution not found: {execution_id}",
        )

    execution = executions[execution_id]
    result = execution.get("result", {})

    return AgentStatusResponse(
        execution_id=execution_id,
        status=execution["status"],
        progress=1.0 if execution["status"] in ["completed", "failed"] else 0.5,
        current_step=result.get("current_step", 0),
        total_steps=execution.get("steps_taken", 0),
        started_at=execution["started_at"],
        completed_at=execution.get("completed_at"),
        result=result if execution["status"] == "completed" else None,
        error=execution.get("error"),
    )


@app.post("/agents/{execution_id}/approve", response_model=ApprovalResponse)
async def approve_checkpoint(
    execution_id: str,
    request: ApprovalRequest,
    api_key: str = Depends(get_api_key),
) -> ApprovalResponse:
    """Approve or reject a HITL checkpoint."""
    checkpoint_manager = get_checkpoint_manager_v2()

    try:
        checkpoint = checkpoint_manager.resolve_checkpoint(
            checkpoint_id=request.checkpoint_id,
            approved=request.approved,
            reviewer_notes=request.reviewer_notes,
        )

        logger.info(
            "Checkpoint resolved",
            checkpoint_id=request.checkpoint_id,
            approved=request.approved,
        )

        return ApprovalResponse(
            checkpoint_id=request.checkpoint_id,
            approved=request.approved,
            resolved_at=checkpoint.resolved_at or datetime.utcnow(),
            message=f"Checkpoint {'approved' if request.approved else 'rejected'}",
        )

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Checkpoint not found: {request.checkpoint_id}",
        )


@app.get("/hitl/checkpoints", response_model=CheckpointListResponse)
async def list_checkpoints(
    api_key: str = Depends(get_api_key),
) -> CheckpointListResponse:
    """List all pending HITL checkpoints."""
    checkpoint_manager = get_checkpoint_manager_v2()
    checkpoints = await checkpoint_manager.list_pending_checkpoints()

    return CheckpointListResponse(
        checkpoints=[checkpoint.dict() for checkpoint in checkpoints],
        total_count=len(checkpoints),
        pending_count=len(checkpoints),
    )


@app.get("/hitl/checkpoints/stats")
async def get_checkpoint_stats(
    api_key: str = Depends(get_api_key),
) -> dict:
    """Get checkpoint statistics for dashboard."""
    checkpoint_manager = get_checkpoint_manager_v2()
    checkpoints = await checkpoint_manager.list_pending_checkpoints()

    stats = {
        "pending": sum(1 for c in checkpoints if c.status == "pending"),
        "approved": sum(1 for c in checkpoints if c.status == "approved"),
        "rejected": sum(1 for c in checkpoints if c.status == "rejected"),
        "escalated": sum(1 for c in checkpoints if c.status == "escalated"),
        "total": len(checkpoints),
    }
    return stats


@app.get("/hitl/checkpoints/{checkpoint_id}")
async def get_checkpoint_detail(
    checkpoint_id: str,
    api_key: str = Depends(get_api_key),
) -> dict:
    """Get checkpoint detail for dashboard view."""
    checkpoint_manager = get_checkpoint_manager_v2()
    checkpoint = await checkpoint_manager.get_checkpoint(checkpoint_id)
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    return checkpoint.dict()


@app.post("/hitl/checkpoints/{checkpoint_id}/escalate")
async def escalate_checkpoint(
    checkpoint_id: str,
    api_key: str = Depends(get_api_key),
) -> dict:
    """Escalate a checkpoint."""
    checkpoint_manager = get_checkpoint_manager_v2()
    checkpoint = await checkpoint_manager.get_checkpoint(checkpoint_id)
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    # Escalate by advancing approval chain
    checkpoint.escalation_count += 1
    checkpoint.status = "escalated"
    checkpoint.add_audit_entry("escalated", details={"manual": True})

    if checkpoint_manager.db_pool:
        await checkpoint_manager._persist_checkpoint(checkpoint)
    if checkpoint_manager.redis:
        await checkpoint_manager._cache_checkpoint(checkpoint)

    return {"message": "Checkpoint escalated", "checkpoint": checkpoint.dict()}


@app.get("/agents/{execution_id}/history", response_model=AgentHistoryResponse)
async def get_agent_history(
    execution_id: str,
    api_key: str = Depends(get_api_key),
) -> AgentHistoryResponse:
    """Get execution history for an agent."""
    if execution_id not in executions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution not found: {execution_id}",
        )

    execution = executions[execution_id]

    return AgentHistoryResponse(
        execution_id=execution_id,
        agent_type=execution.get("agent_type", "unknown"),
        goal=execution.get("goal", ""),
        status=execution["status"],
        started_at=execution["started_at"],
        completed_at=execution.get("completed_at"),
        duration_seconds=execution.get("duration_seconds"),
        steps_taken=execution.get("steps_taken", 0),
        result=execution.get("result"),
        error=execution.get("error"),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: any, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail or "An error occurred",
            detail=str(exc),
        ).dict(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: any, exc: Exception) -> JSONResponse:
    """Handle general exceptions."""
    logger.error("Unhandled exception", error=str(exc), error_type=type(exc).__name__)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc) if not settings.is_production else None,
        ).dict(),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers if settings.is_production else 1,
        reload=not settings.is_production,
    )


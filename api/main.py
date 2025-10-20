"""FastAPI main application for agent orchestration."""

import time
from datetime import datetime
from typing import Dict, List
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agents.base_agent import SimpleAgent
from api.middleware import LoggingMiddleware, RateLimitMiddleware, get_api_key
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
from hitl.checkpoint_manager import get_checkpoint_manager
from memory.memory_manager import MemoryManager
from observability.logger import get_logger, setup_logging, set_correlation_id
from observability.metrics import get_metrics_collector
from observability.tracing import setup_tracing
from tools.tool_manager import ToolManager
from tools.examples import APICallerTool, DatabaseQueryTool, FileOperationsTool, NotifierTool

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

# Global state for execution tracking
executions: Dict[str, Dict] = {}


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize services on startup."""
    logger.info("Starting Agentic AI API", environment=settings.environment)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Cleanup on shutdown."""
    logger.info("Shutting down Agentic AI API")
    metrics = get_metrics_collector()
    metrics.publish_metrics()


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
        # Initialize tool manager and register tools
        tool_manager = ToolManager()
        tool_manager.register_tool(APICallerTool())
        tool_manager.register_tool(DatabaseQueryTool())
        tool_manager.register_tool(FileOperationsTool())
        tool_manager.register_tool(NotifierTool())

        # Initialize memory manager
        memory_manager = MemoryManager()

        # Create agent
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

        # Execute agent
        final_state = agent.run(initial_state)

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
    checkpoint_manager = get_checkpoint_manager()

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
    checkpoint_manager = get_checkpoint_manager()
    checkpoints = checkpoint_manager.list_pending_checkpoints()

    return CheckpointListResponse(
        checkpoints=[checkpoint.dict() for checkpoint in checkpoints],
        total_count=len(checkpoints),
        pending_count=len(checkpoints),
    )


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


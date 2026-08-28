# Agentic AI Starter Template

**PROPRIETARY SOFTWARE - ALL RIGHTS RESERVED**

Production-ready starter template for building autonomous AI agents with reasoning chains, human-in-the-loop oversight, and cloud deployment.

## License Notice

This software is proprietary and confidential. No evaluation, testing, or use of any kind is permitted without an express written license from Sean McDonnell. See LICENSE file for complete terms.

## Features

- **Autonomous Reasoning**: LangGraph-based state management with multiple reasoning patterns (chain-of-thought, ReAct, reflection loops)
- **Multi-Agent Orchestration**: Supervisor, Swarm, Pipeline, and Debate patterns with parallel execution
- **Tool Integration**: 9 built-in tools (API, Database, Files, Code Execution, Web Search, Vector Search, Browser, Shell, Notifier) with semantic search
- **Human-in-the-Loop (HITL) v2**: PostgreSQL/Redis-backed checkpoints, webhooks (Slack), escalation policies, audit trails with HMAC signing
- **HITL Dashboard**: React + TypeScript + Vite real-time monitoring with approve/reject/escalate actions
- **Memory Management**: Hybrid short-term (Redis) and long-term (vector DB) memory with conversation history
- **FastAPI Backend**: Production-ready async API with JWT/RBAC authentication, rate limiting, health checks
- **Prometheus Metrics**: /metrics endpoint with agent, tool, and HITL counters/histograms
- **Alembic Migrations**: Database schema versioning for HITL tables
- **Observability**: Structured logging, metrics collection, LangSmith tracing
- **Security**: OWASP-compliant input validation, PII detection, nsjail sandbox for code execution, command injection prevention
- **AWS Deployment**: Docker/ECS Fargate ready

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI API                              │
│  (JWT/RBAC Auth, Rate Limiting, Request Logging, Health Checks) │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────────────┐
│                     Agent Framework                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Reasoning  │  │     Tools    │  │     HITL     │         │
│  │    Chains    │  │   Manager    │  │  Checkpoints │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  Supervisor  │  │    Swarm     │  │   Pipeline   │         │
│  │ Orchestrator │  │ Orchestrator │  │ Orchestrator │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────────────┐
│                    Memory & State                               │
│  ┌──────────────┐              ┌──────────────┐               │
│  │    Redis     │              │  Vector DB   │               │
│  │ (Short-term) │              │ (Long-term)  │               │
│  └──────────────┘              └──────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

## Licensing

**IMPORTANT**: This is proprietary software. To obtain a license for evaluation, development, or production use, contact Sean McDonnell.

### Prohibited Without License:
- Evaluation or testing
- Development or production use
- Copying or modification
- Distribution or sublicensing
- Reverse engineering

## Quick Start (Licensed Users Only)

### Prerequisites
- Python 3.10+
- Docker and Docker Compose
- Poetry (for dependency management)
- Valid license agreement
- PostgreSQL 15+
- Redis 7+

### Installation

1. **Clone the repository** (requires access)
```bash
git clone https://github.com/seanebones-lang/Agentic-AI.git
cd Agentic-AI
```

2. **Install dependencies**
```bash
poetry install
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

4. **Start services with Docker Compose**
```bash
docker-compose -f deployment/docker-compose.yml up -d
```

5. **Run database migrations**
```bash
poetry run alembic -c migrations/alembic.ini upgrade head
```

6. **Run the API**
```bash
poetry run python -m uvicorn api.main:app --reload
```

The API will be available at `http://localhost:8000`

### HITL Dashboard
```bash
cd hitl/dashboard
npm install
npm run dev
```
Dashboard available at `http://localhost:3001`

### API Documentation
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Prometheus Metrics: `http://localhost:8000/metrics`
- Readiness Check: `http://localhost:8000/health/ready`

## Usage Examples

### Execute an Agent
```bash
curl -X POST "http://localhost:8000/agents/execute" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt-token>" \
  -d '{
    "goal": "Analyze sales data and generate insights",
    "agent_type": "simple",
    "max_iterations": 10
  }'
```

### Check Agent Status
```bash
curl "http://localhost:8000/agents/{execution_id}/status" \
  -H "Authorization: Bearer <jwt-token>"
```

### HITL Checkpoint Management
```bash
# List all checkpoints
curl "http://localhost:8000/hitl/checkpoints" \
  -H "Authorization: Bearer <jwt-token>"

# Get checkpoint stats for dashboard
curl "http://localhost:8000/hitl/checkpoints/stats" \
  -H "Authorization: Bearer <jwt-token>"

# Get checkpoint detail
curl "http://localhost:8000/hitl/checkpoints/{checkpoint_id}" \
  -H "Authorization: Bearer <jwt-token>"

# Approve checkpoint
curl -X POST "http://localhost:8000/agents/{execution_id}/approve" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt-token>" \
  -d '{
    "checkpoint_id": "checkpoint-uuid",
    "approved": true,
    "reviewer_notes": "Approved after review"
  }'

# Reject checkpoint
curl -X POST "http://localhost:8000/agents/{execution_id}/approve" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt-token>" \
  -d '{
    "checkpoint_id": "checkpoint-uuid",
    "approved": false,
    "reviewer_notes": "Rejected: insufficient data"
  }'

# Escalate checkpoint
curl -X POST "http://localhost:8000/hitl/checkpoints/{checkpoint_id}/escalate" \
  -H "Authorization: Bearer <jwt-token>"
```

### Create JWT Token (for testing)
```python
from api.middleware import create_access_token, UserRole

token = create_access_token(
    subject="user123",
    roles=[UserRole.OPERATOR],
)
print(token)
```

## Configuration

Configuration is managed through environment variables. See `.env.example` for all available options.

### Key Configuration Options

**LLM Providers:**
- `DEFAULT_LLM_PROVIDER` (openai, anthropic, azure_openai)
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `AZURE_OPENAI_API_KEY`

**Database:**
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_DB`

**Vector DB:**
- `VECTOR_DB_PROVIDER` (chroma, pinecone, faiss)
- `CHROMA_HOST`, `CHROMA_PORT`
- `PINECONE_API_KEY`, `PINECONE_ENVIRONMENT`

**HITL:**
- `HITL_ENABLED`, `HITL_TIMEOUT_SECONDS`
- `HITL_SLACK_WEBHOOK_URL`, `HITL_WEBHOOK_SECRET`

**Auth:**
- `JWT_SECRET_KEY`, `JWT_ALGORITHM` (HS256), `JWT_EXPIRATION_MINUTES`

**Observability:**
- `LOG_LEVEL`, `LOG_FORMAT` (json/text)
- `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`
- `CLOUDWATCH_ENABLED`, `AWS_REGION`

**Rate Limiting:**
- `RATE_LIMIT_ENABLED`, `RATE_LIMIT_PER_MINUTE`

**Security:**
- `PII_DETECTION_ENABLED`, `INPUT_SANITIZATION_ENABLED`
- `ENABLE_CORS`, `CORS_ORIGINS`

## Development

### Project Structure
```
agentic-ai-template/
├── agents/                 # Agent framework and reasoning chains
│   ├── base_agent.py       # BaseAgent with async graph execution
│   ├── orchestration.py    # Multi-agent patterns (Supervisor, Swarm, Pipeline, Debate)
│   ├── llm.py             # LLM Provider abstraction (OpenAI, Anthropic, Azure)
│   ├── registry.py        # Agent registry with health checks + stale cleanup
│   └── reasoning_chains.py # CoT, ReAct, Reflection chains
├── tools/                  # Tool system
│   ├── tool_manager.py     # Tool registration + semantic search
│   └── examples/           # 9 built-in tools
│       ├── api_caller.py
│       ├── db_query.py
│       ├── file_ops.py
│       ├── code_execution.py  # nsjail sandbox support
│       ├── web_search.py
│       ├── vector_search.py
│       ├── browser.py
│       ├── shell.py         # Path resolution + shell -c blocking
│       └── notifier.py
├── hitl/                   # Human-in-the-loop system
│   ├── checkpoint_manager.py     # v1 in-memory
│   ├── checkpoint_manager_v2.py  # v2 PostgreSQL/Redis + webhooks + escalation
│   └── dashboard/         # React + TypeScript + Vite dashboard
├── memory/                 # Memory management
│   ├── memory_manager.py   # Redis + Vector DB hybrid
│   └── vector_store.py     # ChromaDB wrapper
├── api/                    # FastAPI application
│   ├── main.py            # API routes + startup/shutdown
│   ├── middleware.py       # JWT/RBAC, rate limiting, logging
│   └── models.py          # Pydantic request/response models
├── config/                 # Configuration and prompts
│   ├── settings.py        # Pydantic Settings
│   └── prompts.py         # System prompts
├── observability/          # Logging, metrics, tracing
│   ├── logger.py          # Structured JSON logging
│   ├── metrics.py         # CloudWatch + Prometheus
│   └── tracing.py         # LangSmith integration
├── security/               # Security utilities
│   └── security_utils.py  # PII detection, input sanitization
├── migrations/             # Alembic database migrations
│   ├── alembic.ini
│   ├── env.py
│   └── versions/001_initial_hitl_tables.py
├── deployment/             # Docker and AWS deployment files
├── tests/                  # Unit tests (27 passing)
├── examples/               # Example agent implementations
└── docs/                   # Additional documentation
```

### Running Tests
```bash
poetry run pytest              # All tests
poetry run pytest -v           # Verbose
poetry run pytest --cov        # With coverage
```

### Code Quality
```bash
# Format code
poetry run black .

# Lint code
poetry run ruff check .

# Type checking
poetry run mypy .
```

## Database Migrations

```bash
# Create new migration
poetry run alembic -c migrations/alembic.ini revision --autogenerate -m "Description"

# Apply migrations
poetry run alembic -c migrations/alembic.ini upgrade head

# Rollback
poetry run alembic -c migrations/alembic.ini downgrade -1

# Show history
poetry run alembic -c migrations/alembic.ini history
```

## HITL Dashboard Development
```bash
cd hitl/dashboard
npm install          # Install dependencies
npm run dev          # Development server (port 3001)
npm run build        # Production build (outputs to ../static/hitl-dashboard)
```

## Security Considerations

- **Authentication**: JWT Bearer tokens with RBAC (admin/operator/viewer roles)
- **Authorization**: 14 granular permissions via `require_permission()` dependency
- **Rate Limiting**: 60 requests/minute per API key (in-memory, ready for Redis)
- **Code Execution**: nsjail sandbox with CPU/memory/network isolation; fallback restricted exec
- **Shell Commands**: Full path resolution via `shutil.which()`, blocks shell `-c` flag
- **PII Detection**: `security.detect_pii()` for sensitive data identification
- **Input Sanitization**: `security.sanitize_input()` for XSS/injection prevention
- **Audit Trails**: HMAC-signed checkpoint audit logs
- **Secrets**: Environment variables / AWS Secrets Manager (production)

## Observability

### Logging
Structured JSON logging with correlation IDs for request tracing.

### Prometheus Metrics (`/metrics`)
| Metric | Type | Description |
|--------|------|-------------|
| `agentic_ai_agent_executions_total` | Counter | Total executions by agent_type & status |
| `agentic_ai_agent_execution_duration_seconds` | Histogram | Execution latency |
| `agentic_ai_tool_usage_total` | Counter | Tool invocations by tool_name & status |
| `agentic_ai_tool_execution_duration_seconds` | Histogram | Tool latency |
| `agentic_ai_hitl_interventions_total` | Counter | HITL interventions by reason & status |
| `agentic_ai_hitl_checkpoint_duration_seconds` | Histogram | Checkpoint resolution time |
| `agentic_ai_active_checkpoints` | Gauge | Active checkpoints by status |
| `agentic_ai_errors_total` | Counter | Errors by type & component |

### CloudWatch Metrics
Custom metrics published on shutdown or via cron:
- Agent execution time
- Tool usage
- HITL intervention rate
- Token usage
- Error rates

### Tracing
LangSmith integration for LLM call tracing and execution flow visualization.

## AWS Deployment

See `docs/DEPLOYMENT.md` for complete deployment instructions.

### Docker
```bash
# Build
docker build -t agentic-ai:latest .

# Run
docker run -p 8000:8000 --env-file .env agentic-ai:latest
```

## Creating Custom Agents

### Example: Data Analysis Agent
```python
from agents.base_agent import BaseAgent, AgentState
from agents.reasoning_chains import ReflectionChain
from langgraph.graph import StateGraph, END

class DataAnalysisAgent(BaseAgent):
    def build_graph(self) -> StateGraph:
        graph = StateGraph(AgentState)
        
        graph.add_node("analyze_data", self.analyze_data_node)
        graph.add_node("generate_insights", self.generate_insights_node)
        graph.add_node("create_report", self.create_report_node)
        
        graph.add_edge("analyze_data", "generate_insights")
        graph.add_edge("generate_insights", "create_report")
        graph.add_edge("create_report", END)
        
        graph.set_entry_point("analyze_data")
        return graph
    
    def analyze_data_node(self, state: AgentState) -> dict:
        return {"analysis": "results"}
```

### Example: Multi-Agent Pipeline
```python
from agents.orchestration import PipelineOrchestrator, AgentCapability
from agents.registry import register_agent, get_agent_registry

# Register specialized agents
register_agent(
    name="researcher",
    factory=lambda: ResearchAgent(),
    description="Web research specialist",
    capabilities=[AgentCapability.RESEARCH, AgentCapability.WEB_SEARCH],
)

register_agent(
    name="analyst",
    factory=lambda: DataAnalystAgent(),
    description="Data analysis specialist",
    capabilities=[AgentCapability.DATA_ANALYSIS],
)

# Create pipeline
pipeline = PipelineOrchestrator(stages=[
    {"capability": AgentCapability.RESEARCH, "task_template": "Research: {input}"},
    {"capability": AgentCapability.DATA_ANALYSIS, "task_template": "Analyze: {input}"},
])
result = await pipeline.execute("Analyze Q4 market trends")
```

## Creating Custom Tools

```python
from tools.tool_manager import BaseTool

class CustomTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="custom_tool",
            description="Description of what the tool does",
            parameters={
                "type": "object",
                "properties": {
                    "param1": {"type": "string", "description": "Parameter description"}
                },
                "required": ["param1"]
            },
            category="custom",
            tags=["custom", "tool"]
        )
    
    def _execute(self, param1: str) -> dict:
        return {"result": "success"}
```

## RBAC Permissions Reference

| Role | Permissions |
|------|-------------|
| **admin** | All permissions |
| **operator** | agent:execute, agent:read, agent:history, hitl:read, hitl:approve, hitl:reject, hitl:escalate |
| **viewer** | agent:read, agent:history, hitl:read |

## Support

For licensing inquiries and support:
- Contact: Sean McDonnell
- Repository: https://github.com/seanebones-lang/Agentic-AI (private)

## Copyright

Copyright (c) 2025 Sean McDonnell. All Rights Reserved.

This software is proprietary and confidential. Unauthorized use is strictly prohibited.

## Acknowledgments

Built with:
- [LangGraph](https://github.com/langchain-ai/langgraph) for agent state management
- [LangChain](https://github.com/langchain-ai/langchain) for LLM integrations
- [FastAPI](https://fastapi.tiangolo.com/) for the API framework
- [ChromaDB](https://www.trychroma.com/) for vector storage
- [Prometheus Client](https://github.com/prometheus/client_python) for metrics
- [Alembic](https://alembic.sqlalchemy.org/) for database migrations
- [nsjail](https://github.com/google/nsjail) for code execution sandboxing
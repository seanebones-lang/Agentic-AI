# Agentic AI Starter Template

**PROPRIETARY SOFTWARE - ALL RIGHTS RESERVED**

Production-ready starter template for building autonomous AI agents with reasoning chains, human-in-the-loop oversight, and AWS cloud deployment.

## License Notice

This software is proprietary and confidential. No evaluation, testing, or use of any kind is permitted without an express written license from Sean McDonnell. See LICENSE file for complete terms.

## Features

- **Autonomous Reasoning**: LangGraph-based state management with multiple reasoning patterns (chain-of-thought, ReAct, reflection loops)
- **Tool Integration**: Extensible tool system with semantic search and error handling
- **Human-in-the-Loop (HITL)**: Built-in approval gates and escalation logic for critical decisions
- **Memory Management**: Hybrid short-term (Redis) and long-term (vector DB) memory
- **FastAPI Backend**: Production-ready async API with authentication and rate limiting
- **Observability**: Structured logging, metrics collection, and LangSmith tracing
- **Security**: OWASP-compliant input validation, PII detection, and secrets management
- **AWS Deployment**: CloudFormation templates for ECS Fargate deployment

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        FastAPI API                           │
│  (Authentication, Rate Limiting, Request Logging)            │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────────┐
│                     Agent Framework                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Reasoning  │  │     Tools    │  │     HITL     │      │
│  │    Chains    │  │   Manager    │  │  Checkpoints │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────────┐
│                    Memory & State                            │
│  ┌──────────────┐              ┌──────────────┐            │
│  │    Redis     │              │  Vector DB   │            │
│  │ (Short-term) │              │ (Long-term)  │            │
│  └──────────────┘              └──────────────┘            │
└─────────────────────────────────────────────────────────────┘
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

5. **Run the API**
```bash
poetry run python -m uvicorn api.main:app --reload
```

The API will be available at `http://localhost:8000`

### API Documentation

Interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Usage Examples

### Execute an Agent

```bash
curl -X POST "http://localhost:8000/agents/execute" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-api-key" \
  -d '{
    "goal": "Analyze sales data and generate insights",
    "agent_type": "simple",
    "max_iterations": 10
  }'
```

### Check Agent Status

```bash
curl "http://localhost:8000/agents/{execution_id}/status" \
  -H "X-API-Key: demo-api-key"
```

### Approve HITL Checkpoint

```bash
curl -X POST "http://localhost:8000/agents/{execution_id}/approve" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-api-key" \
  -d '{
    "checkpoint_id": "checkpoint-uuid",
    "approved": true,
    "reviewer_notes": "Approved after review"
  }'
```

## Configuration

Configuration is managed through environment variables. See `.env.example` for all available options.

### Key Configuration Options

- **LLM Provider**: `DEFAULT_LLM_PROVIDER` (openai, anthropic, azure_openai)
- **Vector DB**: `VECTOR_DB_PROVIDER` (chroma, pinecone, faiss)
- **HITL**: `HITL_ENABLED`, `HITL_TIMEOUT_SECONDS`
- **Observability**: `LOG_LEVEL`, `LANGSMITH_API_KEY`, `CLOUDWATCH_ENABLED`

## Development

### Project Structure

```
agentic-ai-template/
├── agents/              # Agent framework and reasoning chains
├── tools/               # Tool system and example tools
├── hitl/                # Human-in-the-loop system
├── memory/              # Memory management
├── api/                 # FastAPI application
├── config/              # Configuration and prompts
├── observability/       # Logging, metrics, tracing
├── security/            # Security utilities
├── deployment/          # Docker and AWS deployment files
├── tests/               # Unit and integration tests
├── examples/            # Example agent implementations
└── docs/                # Additional documentation
```

### Running Tests

```bash
poetry run pytest
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

## AWS Deployment

See `docs/DEPLOYMENT.md` for complete deployment instructions.

## Creating Custom Agents

### Example: Data Analysis Agent

```python
from agents.base_agent import BaseAgent, AgentState
from agents.reasoning_chains import ReflectionChain
from langgraph.graph import StateGraph, END

class DataAnalysisAgent(BaseAgent):
    def build_graph(self) -> StateGraph:
        graph = StateGraph(AgentState)
        
        # Add nodes
        graph.add_node("analyze_data", self.analyze_data_node)
        graph.add_node("generate_insights", self.generate_insights_node)
        graph.add_node("create_report", self.create_report_node)
        
        # Add edges
        graph.add_edge("analyze_data", "generate_insights")
        graph.add_edge("generate_insights", "create_report")
        graph.add_edge("create_report", END)
        
        graph.set_entry_point("analyze_data")
        
        return graph
    
    def analyze_data_node(self, state: AgentState) -> dict:
        # Implement data analysis logic
        return {"analysis": "results"}
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
        # Implement tool logic
        return {"result": "success"}
```

## Security Considerations

- API keys are required for all endpoints (configurable in development)
- Rate limiting is enabled by default (60 requests/minute)
- PII detection and redaction available via `security.detect_pii()`
- Input sanitization via `security.sanitize_input()`
- HTTPS required in production (configured in ALB)
- Secrets stored in AWS Secrets Manager

## Observability

### Logging

Structured JSON logging with correlation IDs for request tracing.

### Metrics

Custom CloudWatch metrics:
- Agent execution time
- Tool usage
- HITL intervention rate
- Token usage
- Error rates

### Tracing

LangSmith integration for LLM call tracing and execution flow visualization.

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

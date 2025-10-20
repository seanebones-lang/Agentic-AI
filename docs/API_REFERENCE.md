# API Reference

Complete API reference for the Agentic AI Starter Template.

## Base URL

- Local: `http://localhost:8000`
- Production: `https://your-alb-url.amazonaws.com`

## Authentication

All endpoints require API key authentication via header:

```
X-API-Key: your-api-key-here
```

## Endpoints

### Health Check

#### GET /health

Check API health status.

**Response**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2025-10-20T12:00:00Z",
  "services": {
    "api": "operational",
    "redis": "operational",
    "vector_db": "operational"
  }
}
```

### Agent Execution

#### POST /agents/execute

Execute an agent with specified configuration.

**Request Body**
```json
{
  "goal": "Analyze sales data and provide insights",
  "initial_state": {
    "data_source": "Q4_sales.csv"
  },
  "agent_type": "simple",
  "tools": ["api_caller", "database_query"],
  "max_iterations": 10,
  "uncertainty_threshold": 0.7
}
```

**Response**
```json
{
  "execution_id": "uuid-here",
  "status": "completed",
  "result": {
    "goal": "Analyze sales data and provide insights",
    "plan": ["step1", "step2"],
    "actions": [...],
    "result": {...}
  },
  "error": null,
  "duration_seconds": 12.5,
  "steps_taken": 5
}
```

**Status Codes**
- 200: Success
- 401: Unauthorized (missing/invalid API key)
- 429: Rate limit exceeded
- 500: Internal server error

#### GET /agents/{execution_id}/status

Get status of an agent execution.

**Response**
```json
{
  "execution_id": "uuid-here",
  "status": "running",
  "progress": 0.6,
  "current_step": 3,
  "total_steps": 5,
  "started_at": "2025-10-20T12:00:00Z",
  "completed_at": null,
  "result": null,
  "error": null
}
```

#### GET /agents/{execution_id}/history

Get execution history for an agent.

**Response**
```json
{
  "execution_id": "uuid-here",
  "agent_type": "simple",
  "goal": "Analyze sales data",
  "status": "completed",
  "started_at": "2025-10-20T12:00:00Z",
  "completed_at": "2025-10-20T12:00:12Z",
  "duration_seconds": 12.5,
  "steps_taken": 5,
  "result": {...},
  "error": null
}
```

### HITL (Human-in-the-Loop)

#### GET /hitl/checkpoints

List all pending HITL checkpoints.

**Response**
```json
{
  "checkpoints": [
    {
      "checkpoint_id": "uuid-here",
      "agent_id": "agent-uuid",
      "reason": "uncertainty",
      "context": {...},
      "question": "Should we proceed with this action?",
      "created_at": "2025-10-20T12:00:00Z",
      "timeout_seconds": 3600
    }
  ],
  "total_count": 1,
  "pending_count": 1
}
```

#### POST /agents/{execution_id}/approve

Approve or reject a HITL checkpoint.

**Request Body**
```json
{
  "checkpoint_id": "uuid-here",
  "approved": true,
  "reviewer_notes": "Approved after review",
  "reviewer_id": "user-123"
}
```

**Response**
```json
{
  "checkpoint_id": "uuid-here",
  "approved": true,
  "resolved_at": "2025-10-20T12:05:00Z",
  "message": "Checkpoint approved"
}
```

## Rate Limiting

- Default: 60 requests per minute per API key
- Headers included in response:
  - `X-RateLimit-Limit`: Maximum requests allowed
  - `X-RateLimit-Remaining`: Remaining requests
  - `X-RateLimit-Reset`: Timestamp when limit resets

## Error Responses

All errors follow this format:

```json
{
  "error": "Error message",
  "detail": "Detailed error information",
  "timestamp": "2025-10-20T12:00:00Z"
}
```

## Request Tracing

All requests include a correlation ID for tracing:
- Request header: `X-Correlation-ID` (optional, auto-generated if not provided)
- Response header: `X-Correlation-ID` (always included)

## Examples

### cURL

```bash
# Execute agent
curl -X POST "http://localhost:8000/agents/execute" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-api-key" \
  -d '{
    "goal": "Analyze data",
    "agent_type": "simple"
  }'

# Check status
curl "http://localhost:8000/agents/{execution_id}/status" \
  -H "X-API-Key: demo-api-key"

# Approve checkpoint
curl -X POST "http://localhost:8000/agents/{execution_id}/approve" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-api-key" \
  -d '{
    "checkpoint_id": "uuid",
    "approved": true
  }'
```

### Python

```python
import requests

API_URL = "http://localhost:8000"
API_KEY = "demo-api-key"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

# Execute agent
response = requests.post(
    f"{API_URL}/agents/execute",
    headers=headers,
    json={
        "goal": "Analyze data",
        "agent_type": "simple"
    }
)

execution_id = response.json()["execution_id"]

# Check status
status = requests.get(
    f"{API_URL}/agents/{execution_id}/status",
    headers=headers
)

print(status.json())
```

### JavaScript

```javascript
const API_URL = "http://localhost:8000";
const API_KEY = "demo-api-key";

// Execute agent
const response = await fetch(`${API_URL}/agents/execute`, {
  method: "POST",
  headers: {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    goal: "Analyze data",
    agent_type: "simple"
  })
});

const { execution_id } = await response.json();

// Check status
const status = await fetch(
  `${API_URL}/agents/${execution_id}/status`,
  {
    headers: { "X-API-Key": API_KEY }
  }
);

console.log(await status.json());
```


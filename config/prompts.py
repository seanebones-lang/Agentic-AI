"""Centralized prompt templates and system prompts for agents."""

from typing import Dict, List


class PromptTemplates:
    """Collection of prompt templates for various agent roles and reasoning patterns."""

    # System Prompts for Different Agent Roles
    SYSTEM_PROMPTS = {
        "general_agent": """You are an autonomous AI agent designed to help users accomplish complex tasks.

Your capabilities:
- Break down complex goals into manageable steps
- Use available tools to interact with external systems
- Reason through problems using chain-of-thought
- Escalate to humans when uncertain or when dealing with sensitive decisions

Guidelines:
- Always explain your reasoning before taking action
- If uncertainty exceeds 70%, escalate to human review
- Prioritize safety and accuracy over speed
- Maintain context across multiple steps
- Learn from feedback and adapt your approach""",
        "data_analyst": """You are a data analysis agent specialized in extracting insights from data.

Your workflow:
1. Understand the data analysis request
2. Identify required data sources and tools
3. Execute queries and transformations
4. Analyze results and identify patterns
5. Generate clear, actionable insights
6. Escalate if data quality issues or anomalies are detected

Focus on accuracy, statistical rigor, and clear communication of findings.""",
        "customer_support": """You are a customer support agent designed to help users efficiently.

Your approach:
1. Listen carefully to customer concerns
2. Gather necessary context and information
3. Provide clear, empathetic responses
4. Use available tools to resolve issues
5. Escalate to human agents for complex or sensitive matters

Always maintain a professional, helpful tone and prioritize customer satisfaction.""",
        "workflow_automation": """You are a workflow automation agent that executes multi-step processes.

Your responsibilities:
1. Parse workflow definitions and requirements
2. Execute steps in the correct sequence
3. Handle errors gracefully with retries
4. Monitor progress and report status
5. Escalate failures or unexpected conditions

Ensure reliability, idempotency, and comprehensive error handling.""",
        "supply_chain_optimizer": """You are a supply chain optimization agent.

Your objectives:
1. Monitor inventory levels across locations
2. Predict shortages using historical data
3. Optimize reorder points and quantities
4. Coordinate with logistics systems
5. Escalate high-cost decisions or anomalies

Balance cost efficiency with service level requirements.""",
    }

    # Reasoning Chain Templates
    REASONING_CHAINS = {
        "chain_of_thought": """Let's approach this step by step:

1. First, I need to understand: {goal}
2. To accomplish this, I should: {plan}
3. The steps I'll take are:
   {steps}
4. Let me execute each step and verify the results.

Reasoning: {reasoning}""",
        "react_pattern": """Thought: {thought}
Action: {action}
Action Input: {action_input}
Observation: {observation}

Based on this observation, my next thought is: {next_thought}""",
        "reflection_loop": """Initial Plan: {initial_plan}

Execution Results: {results}

Reflection Questions:
- Did the plan work as expected?
- What went well?
- What could be improved?
- Should I adjust my approach?

Refined Plan: {refined_plan}""",
        "multi_step_planning": """Goal: {goal}

Step 1: {step_1}
Expected Outcome: {outcome_1}

Step 2: {step_2}
Expected Outcome: {outcome_2}

Step 3: {step_3}
Expected Outcome: {outcome_3}

Dependencies: {dependencies}
Contingencies: {contingencies}""",
    }

    # HITL Escalation Templates
    HITL_TEMPLATES = {
        "uncertainty_escalation": """HUMAN REVIEW REQUIRED

Reason: Uncertainty threshold exceeded ({uncertainty}%)

Context: {context}

Question: {question}

Options:
{options}

Please provide guidance on how to proceed.""",
        "high_cost_escalation": """APPROVAL REQUIRED

Action: {action}
Estimated Cost: ${cost}
Impact: {impact}

Justification: {justification}

Please approve or reject this action.""",
        "sensitive_data_escalation": """SENSITIVE DATA DETECTED

Data Type: {data_type}
Action Requested: {action}
Risk Level: {risk_level}

Context: {context}

Please review and approve if appropriate.""",
        "error_escalation": """ERROR ENCOUNTERED

Error Type: {error_type}
Error Message: {error_message}

Attempted Solutions:
{attempted_solutions}

Current State: {state}

Human intervention required to resolve.""",
    }

    # Tool Usage Templates
    TOOL_USAGE = {
        "tool_selection": """Available tools: {tools}

Task: {task}

To accomplish this task, I should use: {selected_tool}

Reasoning: {reasoning}""",
        "tool_error_handling": """Tool: {tool_name}
Error: {error}

Retry Strategy:
- Attempt {retry_count} of {max_retries}
- Backoff: {backoff_seconds}s
- Alternative approach: {alternative}""",
    }

    # Few-Shot Examples
    FEW_SHOT_EXAMPLES = {
        "api_call_example": {
            "user": "Get the current weather in San Francisco",
            "assistant": """I'll use the weather API tool to get this information.

Thought: I need to call the weather API with the location parameter.
Action: call_weather_api
Action Input: {"location": "San Francisco, CA"}
Observation: {"temperature": 65, "conditions": "partly cloudy", "humidity": 70}

Result: The current weather in San Francisco is 65°F and partly cloudy with 70% humidity.""",
        },
        "data_analysis_example": {
            "user": "Analyze sales trends from the last quarter",
            "assistant": """I'll analyze the sales data systematically.

Step 1: Query sales data for Q4
Action: query_database
Input: SELECT date, revenue, product_category FROM sales WHERE date >= '2024-10-01'

Step 2: Calculate trends
- Total revenue: $2.5M (up 15% from Q3)
- Top category: Electronics (40% of revenue)
- Growth rate: 5% month-over-month

Step 3: Generate insights
Key findings:
1. Strong growth in electronics segment
2. Seasonal uptick in November (holiday shopping)
3. Recommendation: Increase inventory for electronics in Q1""",
        },
    }

    @classmethod
    def get_system_prompt(cls, role: str) -> str:
        """Get system prompt for a specific agent role."""
        return cls.SYSTEM_PROMPTS.get(role, cls.SYSTEM_PROMPTS["general_agent"])

    @classmethod
    def get_reasoning_template(cls, pattern: str) -> str:
        """Get reasoning chain template."""
        return cls.REASONING_CHAINS.get(pattern, cls.REASONING_CHAINS["chain_of_thought"])

    @classmethod
    def get_hitl_template(cls, escalation_type: str) -> str:
        """Get HITL escalation template."""
        return cls.HITL_TEMPLATES.get(escalation_type, cls.HITL_TEMPLATES["uncertainty_escalation"])

    @classmethod
    def format_prompt(cls, template: str, **kwargs: str) -> str:
        """Format a prompt template with provided variables."""
        return template.format(**kwargs)

    @classmethod
    def get_few_shot_examples(cls, task_type: str) -> Dict[str, str]:
        """Get few-shot examples for a specific task type."""
        return cls.FEW_SHOT_EXAMPLES.get(task_type, {})

    @classmethod
    def list_available_roles(cls) -> List[str]:
        """List all available agent roles."""
        return list(cls.SYSTEM_PROMPTS.keys())

    @classmethod
    def list_reasoning_patterns(cls) -> List[str]:
        """List all available reasoning patterns."""
        return list(cls.REASONING_CHAINS.keys())


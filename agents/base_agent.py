"""Base agent class using LangGraph StateGraph for state management."""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Literal

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from agents.llm import LLMProvider, create_provider, LLMMessage
from observability.logger import LoggerMixin, get_logger
from observability.metrics import get_metrics_collector

logger = get_logger(__name__)


class PlanStep(BaseModel):
    """A single step in the agent's plan."""
    step: str
    tool: Optional[str] = None
    args: Dict[str, Any] = Field(default_factory=dict)
    description: str = ""


class PlanOutput(BaseModel):
    """Structured output for planning."""
    plan: List[PlanStep]
    reasoning: str


class ReflectionOutput(BaseModel):
    """Structured output for reflection."""
    assessment: str
    needs_replan: bool
    uncertainty_score: float = Field(ge=0.0, le=1.0)
    next_actions: List[str] = Field(default_factory=list)


class AgentState(BaseModel):
    """State model for agent execution using Pydantic."""

    goal: str = Field(..., description="The agent's primary goal or objective")
    plan: List[str] = Field(default_factory=list, description="List of planned steps")
    actions: List[Dict[str, Any]] = Field(
        default_factory=list, description="Actions taken by the agent"
    )
    reflections: List[str] = Field(
        default_factory=list, description="Agent's reflections on execution"
    )
    memory: Dict[str, Any] = Field(
        default_factory=dict, description="Working memory for the agent"
    )
    hitl_approval: bool = Field(default=False, description="Human-in-the-loop approval status")
    hitl_required: bool = Field(default=False, description="Whether HITL approval is required")
    current_step: int = Field(default=0, description="Current execution step")
    error: Optional[str] = Field(default=None, description="Error message if execution failed")
    result: Optional[Any] = Field(default=None, description="Final result of agent execution")
    needs_replan: bool = Field(default=False, description="Whether replanning is needed")
    uncertainty_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Uncertainty score")

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True


class BaseAgent(ABC, LoggerMixin):
    """Abstract base class for all agents with LangGraph state management."""

    def __init__(
        self,
        tools: Optional[List[Any]] = None,
        memory_manager: Optional[Any] = None,
        max_iterations: int = 10,
        uncertainty_threshold: float = 0.7,
        llm_provider: Optional[LLMProvider] = None,
        llm_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize base agent.

        Args:
            tools: List of tools available to the agent
            memory_manager: Memory manager instance for state persistence
            max_iterations: Maximum number of execution iterations
            uncertainty_threshold: Threshold for HITL escalation
            llm_provider: Pre-configured LLM provider instance
            llm_config: Configuration dict for creating LLM provider (provider, model, api_key, etc.)
        """
        self.tools = tools or []
        self.memory_manager = memory_manager
        self.max_iterations = max_iterations
        self.uncertainty_threshold = uncertainty_threshold
        self.metrics = get_metrics_collector()

        # Initialize LLM provider
        if llm_provider:
            self.llm = llm_provider
        elif llm_config:
            self.llm = create_provider(**llm_config)
        else:
            self.llm = None

        self.graph = self.build_graph()
        self.logger.info(
            "Agent initialized",
            agent_type=self.__class__.__name__,
            num_tools=len(self.tools),
            llm_enabled=self.llm is not None,
        )

    @abstractmethod
    def build_graph(self) -> StateGraph:
        """
        Build the agent's execution graph using LangGraph.

        Returns:
            StateGraph: Configured state graph for agent execution
        """
        pass

    def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the agent with the given initial state.

        Args:
            initial_state: Initial state dictionary

        Returns:
            Dict containing the final state after execution
        """
        import time

        start_time = time.time()
        state = AgentState(**initial_state)

        self.logger.info("Starting agent execution", goal=state.goal)

        try:
            # Compile and invoke the graph
            compiled_graph = self.graph.compile()
            final_state = compiled_graph.invoke(state.dict())

            duration = time.time() - start_time
            success = final_state.get("error") is None

            # Record metrics
            self.metrics.record_agent_execution(
                agent_type=self.__class__.__name__,
                success=success,
                duration_seconds=duration,
            )

            self.logger.info(
                "Agent execution completed",
                success=success,
                duration_seconds=duration,
                steps_taken=final_state.get("current_step", 0),
            )

            return final_state

        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(
                "Agent execution failed",
                error=str(e),
                error_type=type(e).__name__,
                duration_seconds=duration,
            )
            self.metrics.record_agent_execution(
                agent_type=self.__class__.__name__,
                success=False,
                duration_seconds=duration,
            )
            self.metrics.record_error(
                error_type=type(e).__name__,
                component=self.__class__.__name__,
            )
            raise

    async def arun(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Async execution of the agent (for async workflows).

        Args:
            initial_state: Initial state dictionary

        Returns:
            Dict containing the final state after execution
        """
        import time

        start_time = time.time()
        state = AgentState(**initial_state)

        self.logger.info("Starting async agent execution", goal=state.goal)

        try:
            compiled_graph = self.graph.compile()
            final_state = await compiled_graph.ainvoke(state.dict())

            duration = time.time() - start_time
            success = final_state.get("error") is None

            self.metrics.record_agent_execution(
                agent_type=self.__class__.__name__,
                success=success,
                duration_seconds=duration,
            )

            self.logger.info(
                "Async agent execution completed",
                success=success,
                duration_seconds=duration,
            )

            return final_state

        except Exception as e:
            duration = time.time() - start_time
            self.logger.error("Async agent execution failed", error=str(e))
            self.metrics.record_agent_execution(
                agent_type=self.__class__.__name__,
                success=False,
                duration_seconds=duration,
            )
            raise

    def should_escalate_to_human(self, state: AgentState) -> bool:
        """
        Determine if human intervention is required.

        Args:
            state: Current agent state

        Returns:
            bool: True if HITL is required
        """
        return state.uncertainty_score >= self.uncertainty_threshold or state.hitl_required


class SimpleAgent(BaseAgent):
    """Simple agent implementation with plan-execute-reflect pattern using real LLM."""

    def __init__(
        self,
        tools: Optional[List[Any]] = None,
        memory_manager: Optional[Any] = None,
        max_iterations: int = 10,
        uncertainty_threshold: float = 0.7,
        llm_provider: Optional[LLMProvider] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
    ):
        super().__init__(
            tools=tools,
            memory_manager=memory_manager,
            max_iterations=max_iterations,
            uncertainty_threshold=uncertainty_threshold,
            llm_provider=llm_provider,
            llm_config=llm_config,
        )
        self.system_prompt = system_prompt or self._default_system_prompt()
        self._tool_schemas = self._build_tool_schemas()

    def _default_system_prompt(self) -> str:
        tool_descriptions = "\n".join([
            f"- {t.__class__.__name__}: {getattr(t, 'description', 'No description')}"
            for t in self.tools
        ]) if self.tools else "No tools available."

        return f"""You are an autonomous agent that plans, executes, and reflects on tasks.

Available tools:
{tool_descriptions}

Your process:
1. PLAN: Analyze the goal and create a step-by-step plan with specific tool calls
2. EXECUTE: Execute each step using the appropriate tools
3. REFLECT: Evaluate results, decide if replanning is needed

Always respond with structured output matching the required schema."""

    def _build_tool_schemas(self) -> List[Dict[str, Any]]:
        """Build JSON schemas for available tools."""
        schemas = []
        for tool in self.tools:
            if hasattr(tool, "schema"):
                schemas.append(tool.schema())
            elif hasattr(tool, "name") and hasattr(tool, "description"):
                schemas.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": getattr(tool, "parameters", {"type": "object", "properties": {}}),
                    },
                })
        return schemas

    def build_graph(self) -> StateGraph:
        """Build a simple plan-execute-reflect graph."""
        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("agent_plan", self.plan_node)
        graph.add_node("agent_execute", self.execute_node)
        graph.add_node("agent_reflect", self.reflect_node)
        graph.add_node("agent_hitl_check", self.hitl_check_node)

        # Add edges
        graph.add_edge("agent_plan", "agent_hitl_check")
        graph.add_conditional_edges(
            "agent_hitl_check",
            self.should_wait_for_approval,
            {"approved": "agent_execute", "waiting": END},
        )
        graph.add_edge("agent_execute", "agent_reflect")
        graph.add_conditional_edges(
            "agent_reflect",
            self.decide_next_step,
            {"replan": "agent_plan", "end": END},
        )

        # Set entry point
        graph.set_entry_point("agent_plan")

        return graph

    def plan_node(self, state: AgentState) -> Dict[str, Any]:
        """Planning node - uses LLM to create a structured plan."""
        if not self.llm:
            self.logger.warning("No LLM provider, using fallback plan")
            return self._fallback_plan(state)

        self.logger.info("Planning step with LLM", goal=state.goal)

        plan_prompt = f"""Goal: {state.goal}

Create a step-by-step plan to achieve this goal. Available tools: {[t.get('function', {}).get('name', 'unknown') for t in self._tool_schemas]}.

Respond with JSON:
{{
  "plan": [
    {{"step": "description", "tool": "tool_name", "args": {{"key": "value"}}, "description": "what this does"}}
  ],
  "reasoning": "why this plan"
}}"""

        messages = [
            LLMMessage(role="system", content=self.system_prompt),
            LLMMessage(role="user", content=plan_prompt),
        ]

        try:
            import asyncio
            response = asyncio.run(self.llm.chat(messages, tools=self._tool_schemas))

            import json
            try:
                plan_data = json.loads(response.content)
                plan_steps = [
                    f"{p['step']} (tool: {p.get('tool', 'none')})"
                    for p in plan_data.get("plan", [])
                ]
            except json.JSONDecodeError:
                plan_steps = [
                    f"Analyze goal: {state.goal}",
                    "Identify required tools",
                    "Execute actions",
                    "Verify results",
                ]

            return {
                "plan": plan_steps,
                "current_step": state.current_step + 1,
            }
        except Exception as e:
            self.logger.error("LLM planning failed, using fallback", error=str(e))
            return self._fallback_plan(state)

    def _fallback_plan(self, state: AgentState) -> Dict[str, Any]:
        plan = [
            f"Analyze goal: {state.goal}",
            "Identify required tools",
            "Execute actions",
            "Verify results",
        ]
        return {
            "plan": plan,
            "current_step": state.current_step + 1,
        }

    def execute_node(self, state: AgentState) -> Dict[str, Any]:
        """Execution node - executes planned actions using ToolManager."""
        self.logger.info("Executing step", plan_length=len(state.plan))

        from tools.tool_manager import ToolManager

        tool_manager = ToolManager()
        for tool in self.tools:
            tool_manager.register_tool(tool)

        actions = []
        for i, step in enumerate(state.plan):
            self.logger.info("Executing plan step", step=i, step_text=step)

            try:
                result = tool_manager.execute_tool(
                    tool_name="auto",
                    args={"task": step},
                )
                actions.append({"action": step, "status": "completed", "result": str(result)[:200]})
            except Exception as e:
                actions.append({"action": step, "status": "failed", "error": str(e)})
                self.logger.error("Step execution failed", step=step, error=str(e))

        return {
            "actions": state.actions + actions,
            "current_step": state.current_step + 1,
        }

    def reflect_node(self, state: AgentState) -> Dict[str, Any]:
        """Reflection node - uses LLM to evaluate execution."""
        if not self.llm:
            self.logger.warning("No LLM provider, using fallback reflection")
            return self._fallback_reflection(state)

        self.logger.info("Reflecting on execution with LLM", actions_count=len(state.actions))

        actions_summary = "\n".join([
            f"- {a['action']}: {a.get('status', 'unknown')}"
            for a in state.actions
        ])

        reflection_prompt = f"""Goal: {state.goal}

Actions taken:
{actions_summary}

Evaluate the execution. Has the goal been achieved? What's the uncertainty level (0-1)?
Should we replan or end?

Respond with JSON:
{{
  "assessment": "evaluation text",
  "needs_replan": true/false,
  "uncertainty_score": 0.0-1.0,
  "next_actions": ["action1", "action2"]
}}"""

        messages = [
            LLMMessage(role="system", content=self.system_prompt),
            LLMMessage(role="user", content=reflection_prompt),
        ]

        try:
            import asyncio
            response = asyncio.run(self.llm.chat(messages))

            import json
            try:
                reflection_data = json.loads(response.content)
                needs_replan = reflection_data.get("needs_replan", False)
                uncertainty = reflection_data.get("uncertainty_score", 0.0)
                assessment = reflection_data.get("assessment", "No assessment")
            except json.JSONDecodeError:
                needs_replan = state.current_step >= self.max_iterations
                uncertainty = 0.5
                assessment = "Could not parse LLM reflection"

            return {
                "reflections": state.reflections + [assessment],
                "needs_replan": needs_replan,
                "uncertainty_score": uncertainty,
                "current_step": state.current_step + 1,
                "result": {"status": "completed" if not needs_replan else "replan", "actions": state.actions},
            }
        except Exception as e:
            self.logger.error("LLM reflection failed, using fallback", error=str(e))
            return self._fallback_reflection(state)

    def _fallback_reflection(self, state: AgentState) -> Dict[str, Any]:
        reflection = "Execution completed successfully"
        needs_replan = state.current_step >= self.max_iterations

        return {
            "reflections": state.reflections + [reflection],
            "needs_replan": needs_replan,
            "current_step": state.current_step + 1,
            "result": {"status": "completed", "actions": state.actions},
        }

    def hitl_check_node(self, state: AgentState) -> Dict[str, Any]:
        """
        HITL checkpoint node - checks if human approval is needed.

        Args:
            state: Current agent state

        Returns:
            Updated state dictionary
        """
        if self.should_escalate_to_human(state):
            self.logger.info("HITL approval required", uncertainty=state.uncertainty_score)
            return {"hitl_required": True}

        return {"hitl_approval": True}

    def should_wait_for_approval(self, state: AgentState) -> str:
        """Decide if we should wait for approval or proceed."""
        if state.hitl_required and not state.hitl_approval:
            return "waiting"
        return "approved"

    def decide_next_step(self, state: AgentState) -> str:
        """Decide whether to replan or end execution."""
        if state.needs_replan and state.current_step < self.max_iterations:
            return "replan"
        return "end"
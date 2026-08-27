"""Base agent class using LangGraph StateGraph for state management."""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from observability.logger import LoggerMixin, get_logger
from observability.metrics import get_metrics_collector

logger = get_logger(__name__)


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
    ):
        """
        Initialize base agent.

        Args:
            tools: List of tools available to the agent
            memory_manager: Memory manager instance for state persistence
            max_iterations: Maximum number of execution iterations
            uncertainty_threshold: Threshold for HITL escalation
        """
        self.tools = tools or []
        self.memory_manager = memory_manager
        self.max_iterations = max_iterations
        self.uncertainty_threshold = uncertainty_threshold
        self.metrics = get_metrics_collector()
        self.graph = self.build_graph()
        self.logger.info(
            "Agent initialized",
            agent_type=self.__class__.__name__,
            num_tools=len(self.tools),
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
    """
    Simple agent implementation with plan-execute-reflect pattern.

    This is a concrete example showing how to extend BaseAgent.
    """

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
        """
        Planning node - creates a plan to achieve the goal.

        Args:
            state: Current agent state

        Returns:
            Updated state dictionary
        """
        self.logger.info("Planning step", goal=state.goal)

        # In production, this would use an LLM to generate the plan
        # For now, create a simple plan
        plan = [
            f"Analyze goal: {state.goal}",
            "Identify required tools",
            "Execute actions",
            "Verify results",
        ]

        return {
            "agent_plan": plan,
            "current_step": state.current_step + 1,
        }

    def execute_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Execution node - executes the planned actions.

        Args:
            state: Current agent state

        Returns:
            Updated state dictionary
        """
        self.logger.info("Executing step", plan_length=len(state.plan))

        # Execute actions (placeholder for actual tool execution)
        actions = [{"action": step, "status": "completed"} for step in state.plan]

        return {
            "actions": state.actions + actions,
            "current_step": state.current_step + 1,
        }

    def reflect_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Reflection node - evaluates execution and decides next steps.

        Args:
            state: Current agent state

        Returns:
            Updated state dictionary
        """
        self.logger.info("Reflecting on execution", actions_count=len(state.actions))

        # Simple reflection logic
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


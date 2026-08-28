"""Multi-agent orchestration patterns."""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from agents.llm import LLMMessage
from agents.base_agent import BaseAgent, AgentState
from agents.registry import AgentRegistry, AgentCapability, get_agent_registry
from observability.logger import LoggerMixin, get_logger

logger = get_logger(__name__)


class OrchestrationPattern(str, Enum):
    """Orchestration patterns."""
    SUPERVISOR = "supervisor"
    SWARM = "swarm"
    PIPELINE = "pipeline"
    DEBATE = "debate"


class HandoffContext(BaseModel):
    """Context passed between agents during handoff."""
    source_agent: str
    target_agent: str
    task: str
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrchestrationState(AgentState):
    """Extended state for multi-agent orchestration."""
    active_agent: str = ""
    handoff_context: Optional[HandoffContext] = None
    sub_results: Dict[str, Any] = Field(default_factory=dict)
    completed_agents: List[str] = Field(default_factory=list)
    pending_agents: List[str] = Field(default_factory=list)
    orchestration_pattern: OrchestrationPattern = OrchestrationPattern.SUPERVISOR


class BaseOrchestrator(BaseAgent, ABC):
    """Base class for multi-agent orchestrators."""

    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        **kwargs,
    ):
        self.registry = registry or get_agent_registry()
        super().__init__(**kwargs)

    @abstractmethod
    def build_orchestration_graph(self) -> StateGraph:
        """Build the orchestration graph."""
        pass

    def build_graph(self) -> StateGraph:
        return self.build_orchestration_graph()

    async def handoff_to_agent(
        self,
        state: OrchestrationState,
        target_agent_name: str,
        task: str,
        artifacts: Optional[Dict[str, Any]] = None,
    ) -> OrchestrationState:
        """
        Hand off execution to another agent.

        Args:
            state: Current orchestration state
            target_agent_name: Name of agent to hand off to
            task: Task description for target agent
            artifacts: Artifacts to pass

        Returns:
            Updated state
        """
        source_agent = state.active_agent or self.__class__.__name__
        
        handoff = HandoffContext(
            source_agent=source_agent,
            target_agent=target_agent_name,
            task=task,
            artifacts=artifacts or {},
            conversation_history=state.actions[-5:] if state.actions else [],
        )

        # Get target agent
        target_instance = self.registry.get(target_agent_name)
        if not target_instance:
            raise ValueError(f"Target agent not found: {target_agent_name}")

        # Create and run target agent
        target_agent = target_instance.factory()
        
        # Prepare initial state for target agent
        target_state = {
            "goal": task,
            "memory": {
                **state.memory,
                "handoff_context": handoff.model_dump(),
            },
        }

        # Execute target agent
        result = await target_agent.arun(target_state) if hasattr(target_agent, "arun") else target_agent.run(target_state)

        # Update state with result
        state.sub_results[target_agent_name] = result
        state.completed_agents.append(target_agent_name)
        if target_agent_name in state.pending_agents:
            state.pending_agents.remove(target_agent_name)

        # Release agent back to registry
        self.registry.release_agent(target_agent_name, success=result.get("error") is None)

        return state


class SupervisorOrchestrator(BaseOrchestrator):
    """
    Supervisor pattern: Routes tasks to specialist agents based on capability.

    Flow:
    1. Analyze incoming task
    2. Identify required capabilities
    3. Discover and select best agents
    4. Delegate to agents (sequential or parallel)
    5. Aggregate results
    6. Return final response
    """

    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        max_parallel: int = 3,
        **kwargs,
    ):
        super().__init__(registry=registry, **kwargs)
        self.max_parallel = max_parallel

    def build_orchestration_graph(self) -> StateGraph:
        graph = StateGraph(OrchestrationState)

        graph.add_node("analyze_task", self.analyze_task_node)
        graph.add_node("select_agents", self.select_agents_node)
        graph.add_node("delegate_parallel", self.delegate_parallel_node)
        graph.add_node("aggregate_results", self.aggregate_results_node)

        graph.set_entry_point("analyze_task")
        graph.add_edge("analyze_task", "select_agents")
        graph.add_edge("select_agents", "delegate_parallel")
        graph.add_edge("delegate_parallel", "aggregate_results")
        graph.add_edge("aggregate_results", END)

        return graph

    def analyze_task_node(self, state: OrchestrationState) -> Dict[str, Any]:
        """Analyze task and identify required capabilities."""
        if not self.llm:
            return {"memory": {**state.memory, "required_capabilities": ["reasoning"]}}

        # Use LLM to analyze task
        import asyncio
        analysis_prompt = f"""Task: {state.goal}

Identify the capabilities needed to complete this task. Choose from:
- code_generation, code_review, research, data_analysis, writing, reasoning, planning, tool_use, web_search, file_operations, database, browser_automation

Respond with JSON:
{{"capabilities": ["capability1", "capability2"], "reasoning": "why these capabilities"}}"""

        messages = [
            LLMMessage(role="system", content="You are a task analyzer that identifies required agent capabilities."),
            LLMMessage(role="user", content=analysis_prompt),
        ]

        try:
            response = asyncio.run(self.llm.chat(messages))
            import json
            analysis = json.loads(response.content)
            capabilities = [AgentCapability(c) for c in analysis.get("capabilities", ["reasoning"])]
        except Exception:
            capabilities = [AgentCapability.REASONING]

        return {
            "memory": {**state.memory, "required_capabilities": capabilities},
            "current_step": state.current_step + 1,
        }

    def select_agents_node(self, state: OrchestrationState) -> Dict[str, Any]:
        """Select best agents for required capabilities."""
        capabilities = state.memory.get("required_capabilities", [AgentCapability.REASONING])
        
        selected = []
        for cap in capabilities:
            agents = self.registry.discover_by_capability(cap, max_results=2)
            for agent in agents:
                if agent.metadata.name not in selected:
                    selected.append(agent.metadata.name)

        # Limit parallel agents
        selected = selected[:self.max_parallel]

        return {
            "pending_agents": selected,
            "active_agent": self.__class__.__name__,
            "current_step": state.current_step + 1,
        }

    def delegate_parallel_node(self, state: OrchestrationState) -> Dict[str, Any]:
        """Delegate to selected agents in parallel."""
        import asyncio

        async def delegate_all():
            for agent_name in state.pending_agents:
                await self.handoff_to_agent(state, agent_name, state.goal)

        asyncio.run(delegate_all())
        return {"current_step": state.current_step + 1}

    def aggregate_results_node(self, state: OrchestrationState) -> Dict[str, Any]:
        """Aggregate results from all agents."""
        if not self.llm:
            # Simple concatenation fallback
            combined = "\n\n".join([
                f"--- {agent} ---\n{result.get('result', {})}"
                for agent, result in state.sub_results.items()
            ])
            return {
                "result": {"combined": combined, "sub_results": state.sub_results},
                "current_step": state.current_step + 1,
            }

        # Use LLM to synthesize results
        import asyncio
        results_summary = "\n\n".join([
            f"Agent: {agent}\nResult: {result.get('result', {})}"
            for agent, result in state.sub_results.items()
        ])

        synthesis_prompt = f"""Original task: {state.goal}

Results from specialist agents:
{results_summary}

Synthesize these results into a coherent final answer that addresses the original task."""

        messages = [
            LLMMessage(role="system", content="You are a result synthesizer that combines multiple agent outputs into a coherent response."),
            LLMMessage(role="user", content=synthesis_prompt),
        ]

        try:
            response = asyncio.run(self.llm.chat(messages))
            synthesized = response.content
        except Exception:
            synthesized = results_summary

        return {
            "result": {"synthesized": synthesized, "sub_results": state.sub_results},
            "current_step": state.current_step + 1,
        }


class SwarmOrchestrator(BaseOrchestrator):
    """
    Swarm pattern: Multiple agents work in parallel on the same task,
    then results are aggregated (e.g., consensus, best-of, ensemble).
    """

    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        swarm_size: int = 3,
        aggregation_strategy: str = "consensus",  # consensus, best_of, ensemble
        **kwargs,
    ):
        super().__init__(registry=registry, **kwargs)
        self.swarm_size = swarm_size
        self.aggregation_strategy = aggregation_strategy

    def build_orchestration_graph(self) -> StateGraph:
        graph = StateGraph(OrchestrationState)

        graph.add_node("create_swarm", self.create_swarm_node)
        graph.add_node("execute_swarm", self.execute_swarm_node)
        graph.add_node("aggregate_swarm", self.aggregate_swarm_node)

        graph.set_entry_point("create_swarm")
        graph.add_edge("create_swarm", "execute_swarm")
        graph.add_edge("execute_swarm", "aggregate_swarm")
        graph.add_edge("aggregate_swarm", END)

        return graph

    def create_swarm_node(self, state: OrchestrationState) -> Dict[str, Any]:
        """Create swarm of agents with same capability."""
        # Find agents with reasoning capability (general purpose)
        agents = self.registry.discover_by_capability(AgentCapability.REASONING, max_results=self.swarm_size)
        agent_names = [a.metadata.name for a in agents]

        return {
            "pending_agents": agent_names,
            "active_agent": self.__class__.__name__,
            "current_step": state.current_step + 1,
        }

    def execute_swarm_node(self, state: OrchestrationState) -> Dict[str, Any]:
        """Execute all swarm agents in parallel."""
        import asyncio

        async def run_swarm():
            tasks = []
            for agent_name in state.pending_agents:
                tasks.append(self.handoff_to_agent(state, agent_name, state.goal))
            await asyncio.gather(*tasks)

        asyncio.run(run_swarm())
        return {"current_step": state.current_step + 1}

    def aggregate_swarm_node(self, state: OrchestrationState) -> Dict[str, Any]:
        # Aggregate swarm results based on strategy.
        results = list(state.sub_results.values())

        if self.aggregation_strategy == "best_of":
            # Pick result with highest confidence/success
            best = max(results, key=lambda r: r.get("result", {}).get("confidence", 0)) if results else {}
            return {"result": best, "current_step": state.current_step + 1}

        elif self.aggregation_strategy == "ensemble":
            # Combine all results
            combined = "\n\n---\n\n".join([
                f"Agent {agent}: {result.get('result', {})}"
                for agent, result in state.sub_results.items()
            ])
            return {"result": {"ensemble": combined, "sub_results": state.sub_results}, "current_step": state.current_step + 1}

        else:  # consensus
            if not self.llm:
                return {"result": results[0] if results else {}, "current_step": state.current_step + 1}

            import asyncio
            consensus_prompt = f"""Task: {state.goal}

Multiple agents provided these results:
{chr(10).join([f'Agent {a}: {r.get("result", {})}' for a, r in state.sub_results.items()])}

Find consensus or synthesize the best answer. If agents disagree, explain the disagreement and provide the most likely correct answer."""

            messages = [
                LLMMessage(role="system", content="You are a consensus builder for multi-agent outputs."),
                LLMMessage(role="user", content=consensus_prompt),
            ]

            try:
                response = asyncio.run(self.llm.chat(messages))
                consensus = response.content
            except Exception:
                consensus = "Could not reach consensus"

            return {"result": {"consensus": consensus, "sub_results": state.sub_results}, "current_step": state.current_step + 1}


class PipelineOrchestrator(BaseOrchestrator):
    """
    Pipeline pattern: Sequential agents where each agent's output
    becomes the next agent's input.
    """

    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        stages: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ):
        """
        Initialize pipeline orchestrator.

        Args:
            registry: Agent registry
            stages: List of stage configs: [{"capability": "...", "task_template": "..."}, ...]
        """
        super().__init__(registry=registry, **kwargs)
        self.stages = stages or [
            {"capability": AgentCapability.RESEARCH, "task_template": "Research: {input}"},
            {"capability": AgentCapability.REASONING, "task_template": "Analyze: {input}"},
            {"capability": AgentCapability.WRITING, "task_template": "Write final response: {input}"},
        ]

    def build_orchestration_graph(self) -> StateGraph:
        graph = StateGraph(OrchestrationState)

        # Add stage nodes dynamically
        for i, stage in enumerate(self.stages):
            node_name = f"stage_{i}_{stage['capability'].value}"
            graph.add_node(node_name, self._create_stage_node(i, stage))

        graph.set_entry_point(f"stage_0_{self.stages[0]['capability'].value}")

        # Chain stages
        for i in range(len(self.stages) - 1):
            current = f"stage_{i}_{self.stages[i]['capability'].value}"
            next_stage = f"stage_{i+1}_{self.stages[i+1]['capability'].value}"
            graph.add_edge(current, next_stage)

        graph.add_edge(f"stage_{len(self.stages)-1}_{self.stages[-1]['capability'].value}", END)

        return graph

    def _create_stage_node(self, index: int, stage: Dict[str, Any]) -> Callable:
        """Create a node function for a pipeline stage."""
        def stage_node(state: OrchestrationState) -> Dict[str, Any]:
            capability = stage["capability"]
            task_template = stage["task_template"]

            # Get input from previous stage or original goal
            if index == 0:
                input_data = state.goal
            else:
                prev_stage = self.stages[index - 1]
                prev_name = f"stage_{index-1}_{prev_stage['capability'].value}"
                prev_result = state.sub_results.get(prev_name, {})
                input_data = prev_result.get("result", {}).get("synthesized", str(prev_result))

            task = task_template.format(input=input_data)

            # Find agent
            agents = self.registry.discover_by_capability(capability, max_results=1)
            if not agents:
                return {"error": f"No agent found for capability: {capability.value}"}

            agent_name = agents[0].metadata.name

            # Execute stage
            import asyncio
            asyncio.run(self.handoff_to_agent(state, agent_name, task))

            return {"current_step": state.current_step + 1}

        return stage_node


class DebateOrchestrator(BaseOrchestrator):
    """
    Debate pattern: Multiple agents debate a topic, then a judge
    synthesizes the final answer.
    """

    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        debaters: int = 2,
        rounds: int = 2,
        **kwargs,
    ):
        super().__init__(registry=registry, **kwargs)
        self.debaters = debaters
        self.rounds = rounds

    def build_orchestration_graph(self) -> StateGraph:
        graph = StateGraph(OrchestrationState)

        graph.add_node("opening_statements", self.opening_statements_node)
        
        # Add debate rounds
        for r in range(self.rounds):
            graph.add_node(f"rebuttal_{r}", self._create_rebuttal_node(r))
        
        graph.add_node("judgment", self.judgment_node)

        graph.set_entry_point("opening_statements")
        graph.add_edge("opening_statements", "rebuttal_0")
        
        for r in range(self.rounds - 1):
            graph.add_edge(f"rebuttal_{r}", f"rebuttal_{r+1}")
        
        graph.add_edge(f"rebuttal_{self.rounds-1}", "judgment")
        graph.add_edge("judgment", END)

        return graph

    def opening_statements_node(self, state: OrchestrationState) -> Dict[str, Any]:
        """Get opening statements from all debaters."""
        agents = self.registry.discover_by_capability(AgentCapability.REASONING, max_results=self.debaters)
        debater_names = [a.metadata.name for a in agents]

        import asyncio
        async def get_openings():
            for name in debater_names:
                await self.handoff_to_agent(state, name, f"Opening statement on: {state.goal}")

        asyncio.run(get_openings())
        return {"pending_agents": debater_names, "current_step": state.current_step + 1}

    def _create_rebuttal_node(self, round_num: int) -> Callable:
        def rebuttal_node(state: OrchestrationState) -> Dict[str, Any]:
            debater_names = state.pending_agents

            # Build context from previous rounds
            context = f"Topic: {state.goal}\n\n"
            for agent, result in state.sub_results.items():
                context += f"{agent}: {result.get('result', {})}\n\n"

            import asyncio
            async def get_rebuttals():
                for name in debater_names:
                    task = f"Rebuttal round {round_num + 1}. Previous: {context}\nYour turn."
                    await self.handoff_to_agent(state, name, task)

            asyncio.run(get_rebuttals())
            return {"current_step": state.current_step + 1}

        return rebuttal_node

    def judgment_node(self, state: OrchestrationState) -> Dict[str, Any]:
        """Judge evaluates debate and provides final verdict."""
        if not self.llm:
            return {"result": state.sub_results, "current_step": state.current_step + 1}

        debate_transcript = "\n\n".join([
            f"{agent}: {result.get('result', {})}"
            for agent, result in state.sub_results.items()
        ])

        import asyncio
        judgment_prompt = f"""Topic: {state.goal}

Debate transcript:
{debate_transcript}

You are the judge. Provide a final verdict that synthesizes the best arguments from all sides. Be fair and balanced."""

        messages = [
            LLMMessage(role="system", content="You are an impartial judge evaluating a debate."),
            LLMMessage(role="user", content=judgment_prompt),
        ]

        try:
            response = asyncio.run(self.llm.chat(messages))
            verdict = response.content
        except Exception:
            verdict = "Could not render judgment"

        return {"result": {"verdict": verdict, "debate": state.sub_results}, "current_step": state.current_step + 1}
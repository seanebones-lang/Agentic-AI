"""Pre-built reasoning chain patterns for agent workflows."""

from typing import Callable, Dict, List, Optional

from langgraph.graph import END, StateGraph
from pydantic import BaseModel

from observability.logger import get_logger

logger = get_logger(__name__)


class ReasoningChain:
    """Base class for reasoning chain patterns."""

    @staticmethod
    def add_to_graph(graph: StateGraph, **kwargs: any) -> None:
        """Add this reasoning pattern to a graph."""
        raise NotImplementedError


class SequentialChain(ReasoningChain):
    """
    Sequential chain pattern: Step 1 → Step 2 → Step 3 → ... → End

    Executes nodes in a linear sequence.
    """

    @staticmethod
    def add_to_graph(
        graph: StateGraph,
        nodes: List[str],
        node_functions: Dict[str, Callable],
        entry_node: Optional[str] = None,
    ) -> None:
        """
        Add sequential chain to graph.

        Args:
            graph: StateGraph to modify
            nodes: List of node names in sequence
            node_functions: Dict mapping node names to functions
            entry_node: Optional entry point (defaults to first node)
        """
        if not nodes:
            raise ValueError("Sequential chain requires at least one node")

        logger.info("Adding sequential chain", nodes=nodes)

        # Add all nodes
        for node_name in nodes:
            if node_name not in node_functions:
                raise ValueError(f"No function provided for node: {node_name}")
            graph.add_node(node_name, node_functions[node_name])

        # Add edges in sequence
        for i in range(len(nodes) - 1):
            graph.add_edge(nodes[i], nodes[i + 1])

        # Connect last node to END
        graph.add_edge(nodes[-1], END)

        # Set entry point
        if entry_node:
            graph.set_entry_point(entry_node)
        else:
            graph.set_entry_point(nodes[0])


class ConditionalChain(ReasoningChain):
    """
    Conditional branching pattern: if-then-else logic.

    Allows agents to make decisions and branch execution paths.
    """

    @staticmethod
    def add_to_graph(
        graph: StateGraph,
        condition_node: str,
        condition_func: Callable,
        branches: Dict[str, str],
        node_functions: Dict[str, Callable],
    ) -> None:
        """
        Add conditional branching to graph.

        Args:
            graph: StateGraph to modify
            condition_node: Node that evaluates the condition
            condition_func: Function that returns branch key
            branches: Dict mapping branch keys to node names
            node_functions: Dict mapping node names to functions
        """
        logger.info("Adding conditional chain", condition_node=condition_node, branches=branches)

        # Add condition node
        if condition_node in node_functions:
            graph.add_node(condition_node, node_functions[condition_node])

        # Add branch nodes
        for branch_node in branches.values():
            if branch_node != END and branch_node in node_functions:
                graph.add_node(branch_node, node_functions[branch_node])

        # Add conditional edges
        graph.add_conditional_edges(condition_node, condition_func, branches)


class ReflectionChain(ReasoningChain):
    """
    Reflection loop pattern: plan → execute → evaluate → replan or end.

    Allows agents to reflect on their actions and adapt their approach.
    """

    @staticmethod
    def add_to_graph(
        graph: StateGraph,
        plan_node: str,
        execute_node: str,
        reflect_node: str,
        node_functions: Dict[str, Callable],
        should_replan_func: Callable,
        max_iterations: int = 5,
    ) -> None:
        """
        Add reflection loop to graph.

        Args:
            graph: StateGraph to modify
            plan_node: Planning node name
            execute_node: Execution node name
            reflect_node: Reflection node name
            node_functions: Dict mapping node names to functions
            should_replan_func: Function to decide if replanning is needed
            max_iterations: Maximum number of reflection loops
        """
        logger.info(
            "Adding reflection chain",
            plan_node=plan_node,
            execute_node=execute_node,
            reflect_node=reflect_node,
            max_iterations=max_iterations,
        )

        # Add nodes
        graph.add_node(plan_node, node_functions[plan_node])
        graph.add_node(execute_node, node_functions[execute_node])
        graph.add_node(reflect_node, node_functions[reflect_node])

        # Add edges
        graph.add_edge(plan_node, execute_node)
        graph.add_edge(execute_node, reflect_node)

        # Add conditional edge for reflection
        def reflection_router(state: any) -> str:
            """Route based on reflection results."""
            if hasattr(state, "current_step") and state.current_step >= max_iterations:
                return "end"
            return should_replan_func(state)

        graph.add_conditional_edges(
            reflect_node,
            reflection_router,
            {"replan": plan_node, "end": END},
        )

        # Set entry point
        graph.set_entry_point(plan_node)


class ParallelChain(ReasoningChain):
    """
    Parallel execution pattern: Execute multiple independent tasks concurrently.

    Useful for agents that need to perform multiple actions simultaneously.
    """

    @staticmethod
    def add_to_graph(
        graph: StateGraph,
        parallel_nodes: List[str],
        node_functions: Dict[str, Callable],
        aggregator_node: str,
        aggregator_func: Callable,
    ) -> None:
        """
        Add parallel execution to graph.

        Args:
            graph: StateGraph to modify
            parallel_nodes: List of nodes to execute in parallel
            node_functions: Dict mapping node names to functions
            aggregator_node: Node that aggregates parallel results
            aggregator_func: Function to aggregate results
        """
        logger.info(
            "Adding parallel chain",
            parallel_nodes=parallel_nodes,
            aggregator=aggregator_node,
        )

        # Add parallel nodes
        for node_name in parallel_nodes:
            if node_name not in node_functions:
                raise ValueError(f"No function provided for parallel node: {node_name}")
            graph.add_node(node_name, node_functions[node_name])

        # Add aggregator node
        graph.add_node(aggregator_node, aggregator_func)

        # Connect all parallel nodes to aggregator
        for node_name in parallel_nodes:
            graph.add_edge(node_name, aggregator_node)

        # Connect aggregator to END
        graph.add_edge(aggregator_node, END)


class ChainOfThoughtChain(ReasoningChain):
    """
    Chain-of-thought reasoning pattern.

    Breaks down complex reasoning into explicit steps with intermediate thoughts.
    """

    @staticmethod
    def add_to_graph(
        graph: StateGraph,
        thought_nodes: List[str],
        node_functions: Dict[str, Callable],
    ) -> None:
        """
        Add chain-of-thought reasoning to graph.

        Args:
            graph: StateGraph to modify
            thought_nodes: List of thought/reasoning nodes
            node_functions: Dict mapping node names to functions
        """
        logger.info("Adding chain-of-thought pattern", thought_nodes=thought_nodes)

        # This is similar to sequential but with explicit reasoning at each step
        SequentialChain.add_to_graph(
            graph=graph,
            nodes=thought_nodes,
            node_functions=node_functions,
        )


class ReActChain(ReasoningChain):
    """
    ReAct pattern: Reasoning + Acting in an interleaved manner.

    Alternates between reasoning about what to do and taking actions.
    """

    @staticmethod
    def add_to_graph(
        graph: StateGraph,
        node_functions: Dict[str, Callable],
        max_steps: int = 10,
    ) -> None:
        """
        Add ReAct pattern to graph.

        Args:
            graph: StateGraph to modify
            node_functions: Must include 'reason', 'act', and 'observe' functions
            max_steps: Maximum number of reason-act cycles
        """
        logger.info("Adding ReAct pattern", max_steps=max_steps)

        required_nodes = ["reason", "act", "observe"]
        for node in required_nodes:
            if node not in node_functions:
                raise ValueError(f"ReAct pattern requires '{node}' function")

        # Add nodes
        graph.add_node("reason", node_functions["reason"])
        graph.add_node("act", node_functions["act"])
        graph.add_node("observe", node_functions["observe"])

        # Add edges
        graph.add_edge("reason", "act")
        graph.add_edge("act", "observe")

        # Add conditional edge from observe
        def should_continue(state: any) -> str:
            """Decide if we should continue reasoning or end."""
            if hasattr(state, "current_step") and state.current_step >= max_steps:
                return "end"
            if hasattr(state, "task_complete") and state.task_complete:
                return "end"
            return "continue"

        graph.add_conditional_edges(
            "observe",
            should_continue,
            {"continue": "reason", "end": END},
        )

        # Set entry point
        graph.set_entry_point("reason")


def create_custom_chain(
    graph: StateGraph,
    nodes: List[str],
    edges: List[tuple[str, str]],
    conditional_edges: List[tuple[str, Callable, Dict[str, str]]],
    node_functions: Dict[str, Callable],
    entry_point: str,
) -> None:
    """
    Create a custom reasoning chain with arbitrary structure.

    Args:
        graph: StateGraph to modify
        nodes: List of node names
        edges: List of (from_node, to_node) tuples
        conditional_edges: List of (node, condition_func, branches) tuples
        node_functions: Dict mapping node names to functions
        entry_point: Entry point node name
    """
    logger.info("Creating custom chain", nodes=nodes, entry_point=entry_point)

    # Add all nodes
    for node_name in nodes:
        if node_name not in node_functions:
            raise ValueError(f"No function provided for node: {node_name}")
        graph.add_node(node_name, node_functions[node_name])

    # Add regular edges
    for from_node, to_node in edges:
        graph.add_edge(from_node, to_node)

    # Add conditional edges
    for node, condition_func, branches in conditional_edges:
        graph.add_conditional_edges(node, condition_func, branches)

    # Set entry point
    graph.set_entry_point(entry_point)


"""Unit tests for agent framework."""

import pytest

from agents.base_agent import SimpleAgent, AgentState


class TestAgentState:
    """Test AgentState model."""

    def test_agent_state_creation(self) -> None:
        """Test creating an agent state."""
        state = AgentState(goal="Test goal")

        assert state.goal == "Test goal"
        assert state.plan == []
        assert state.actions == []
        assert state.current_step == 0
        assert state.uncertainty_score == 0.0

    def test_agent_state_with_data(self) -> None:
        """Test agent state with additional data."""
        state = AgentState(
            goal="Test goal",
            plan=["step1", "step2"],
            uncertainty_score=0.5,
        )

        assert len(state.plan) == 2
        assert state.uncertainty_score == 0.5


class TestSimpleAgent:
    """Test SimpleAgent implementation."""

    def test_agent_initialization(self) -> None:
        """Test agent initialization."""
        agent = SimpleAgent(tools=[], memory_manager=None)

        assert agent.tools == []
        assert agent.memory_manager is None
        assert agent.max_iterations == 10
        assert agent.graph is not None

    def test_agent_run(self) -> None:
        """Test agent execution."""
        agent = SimpleAgent(tools=[], memory_manager=None)

        result = agent.run({"goal": "Test execution"})

        assert "goal" in result
        assert "current_step" in result
        assert result["current_step"] > 0

    def test_agent_escalation_check(self) -> None:
        """Test HITL escalation logic."""
        agent = SimpleAgent(
            tools=[],
            memory_manager=None,
            uncertainty_threshold=0.5,
        )

        # Low uncertainty - no escalation
        state_low = AgentState(goal="test", uncertainty_score=0.3)
        assert not agent.should_escalate_to_human(state_low)

        # High uncertainty - escalation
        state_high = AgentState(goal="test", uncertainty_score=0.8)
        assert agent.should_escalate_to_human(state_high)

        # Manual trigger - escalation
        state_manual = AgentState(goal="test", hitl_required=True)
        assert agent.should_escalate_to_human(state_manual)


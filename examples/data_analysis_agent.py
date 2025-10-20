"""Example: Data Analysis Agent for analyzing datasets and generating insights."""

from typing import Any, Dict

from langgraph.graph import END, StateGraph

from agents.base_agent import AgentState, BaseAgent
from config.prompts import PromptTemplates


class DataAnalysisAgent(BaseAgent):
    """
    Agent specialized in data analysis tasks.

    Workflow:
    1. Load and validate data
    2. Perform statistical analysis
    3. Identify patterns and trends
    4. Generate insights and recommendations
    5. Create summary report
    """

    def build_graph(self) -> StateGraph:
        """Build data analysis workflow graph."""
        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("load_data", self.load_data_node)
        graph.add_node("analyze_data", self.analyze_data_node)
        graph.add_node("identify_patterns", self.identify_patterns_node)
        graph.add_node("generate_insights", self.generate_insights_node)
        graph.add_node("create_report", self.create_report_node)
        graph.add_node("hitl_review", self.hitl_review_node)

        # Add edges
        graph.add_edge("load_data", "analyze_data")
        graph.add_edge("analyze_data", "identify_patterns")
        graph.add_edge("identify_patterns", "generate_insights")
        graph.add_edge("generate_insights", "hitl_review")
        graph.add_conditional_edges(
            "hitl_review",
            self.should_wait_for_review,
            {"approved": "create_report", "waiting": END},
        )
        graph.add_edge("create_report", END)

        graph.set_entry_point("load_data")

        return graph

    def load_data_node(self, state: AgentState) -> Dict[str, Any]:
        """Load and validate data from source."""
        self.logger.info("Loading data", goal=state.goal)

        # In production, this would use actual data loading tools
        # For example: database query tool, file operations tool, API caller

        return {
            "memory": {
                **state.memory,
                "data_loaded": True,
                "data_source": "example_dataset",
                "row_count": 1000,
            },
            "current_step": state.current_step + 1,
        }

    def analyze_data_node(self, state: AgentState) -> Dict[str, Any]:
        """Perform statistical analysis on the data."""
        self.logger.info("Analyzing data")

        # In production, use tools for actual analysis
        # Example: pandas, numpy, statistical libraries

        analysis_results = {
            "mean": 45.2,
            "median": 43.0,
            "std_dev": 12.5,
            "distribution": "normal",
        }

        return {
            "memory": {
                **state.memory,
                "analysis_results": analysis_results,
            },
            "actions": state.actions
            + [{"action": "statistical_analysis", "status": "completed"}],
            "current_step": state.current_step + 1,
        }

    def identify_patterns_node(self, state: AgentState) -> Dict[str, Any]:
        """Identify patterns and trends in the data."""
        self.logger.info("Identifying patterns")

        patterns = [
            "Upward trend in Q4",
            "Seasonal variation detected",
            "Outliers in category A",
        ]

        return {
            "memory": {
                **state.memory,
                "patterns": patterns,
            },
            "current_step": state.current_step + 1,
        }

    def generate_insights_node(self, state: AgentState) -> Dict[str, Any]:
        """Generate actionable insights from analysis."""
        self.logger.info("Generating insights")

        insights = [
            "Revenue growth accelerating in Q4 - recommend increased inventory",
            "Seasonal patterns suggest promotional opportunities in summer",
            "Category A outliers indicate potential data quality issues",
        ]

        # Check if insights require human review
        high_impact_insights = len(insights) > 2
        uncertainty_score = 0.3 if not high_impact_insights else 0.8

        return {
            "memory": {
                **state.memory,
                "insights": insights,
            },
            "uncertainty_score": uncertainty_score,
            "hitl_required": high_impact_insights,
            "current_step": state.current_step + 1,
        }

    def hitl_review_node(self, state: AgentState) -> Dict[str, Any]:
        """HITL checkpoint for reviewing insights."""
        if self.should_escalate_to_human(state):
            self.logger.info("HITL review required for insights")
            return {"hitl_required": True}

        return {"hitl_approval": True}

    def should_wait_for_review(self, state: AgentState) -> str:
        """Decide if we should wait for human review."""
        if state.hitl_required and not state.hitl_approval:
            return "waiting"
        return "approved"

    def create_report_node(self, state: AgentState) -> Dict[str, Any]:
        """Create final analysis report."""
        self.logger.info("Creating report")

        report = {
            "title": "Data Analysis Report",
            "summary": f"Analysis of {state.memory.get('data_source', 'dataset')}",
            "key_findings": state.memory.get("patterns", []),
            "insights": state.memory.get("insights", []),
            "recommendations": [
                "Implement recommended inventory changes",
                "Plan summer promotional campaign",
                "Investigate Category A data quality",
            ],
        }

        return {
            "result": report,
            "current_step": state.current_step + 1,
        }


# Example usage
if __name__ == "__main__":
    from tools.tool_manager import ToolManager
    from memory.memory_manager import MemoryManager

    # Initialize agent
    tool_manager = ToolManager()
    memory_manager = MemoryManager()

    agent = DataAnalysisAgent(
        tools=list(tool_manager.tools.values()),
        memory_manager=memory_manager,
    )

    # Execute agent
    result = agent.run(
        {
            "goal": "Analyze Q4 sales data and provide strategic recommendations",
            "initial_state": {},
        }
    )

    print("Analysis Complete!")
    print(f"Result: {result.get('result')}")


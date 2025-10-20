"""Example: Customer Support Agent for handling customer inquiries."""

from typing import Any, Dict

from langgraph.graph import END, StateGraph

from agents.base_agent import AgentState, BaseAgent


class CustomerSupportAgent(BaseAgent):
    """
    Agent specialized in customer support tasks.

    Workflow:
    1. Understand customer inquiry
    2. Gather relevant context
    3. Search knowledge base
    4. Formulate response
    5. Escalate to human if needed
    """

    def build_graph(self) -> StateGraph:
        """Build customer support workflow graph."""
        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("understand_inquiry", self.understand_inquiry_node)
        graph.add_node("gather_context", self.gather_context_node)
        graph.add_node("search_knowledge", self.search_knowledge_node)
        graph.add_node("formulate_response", self.formulate_response_node)
        graph.add_node("escalation_check", self.escalation_check_node)

        # Add edges
        graph.add_edge("understand_inquiry", "gather_context")
        graph.add_edge("gather_context", "search_knowledge")
        graph.add_edge("search_knowledge", "formulate_response")
        graph.add_edge("formulate_response", "escalation_check")
        graph.add_conditional_edges(
            "escalation_check",
            self.should_escalate,
            {"escalate": END, "respond": END},
        )

        graph.set_entry_point("understand_inquiry")

        return graph

    def understand_inquiry_node(self, state: AgentState) -> Dict[str, Any]:
        """Understand and categorize customer inquiry."""
        self.logger.info("Understanding customer inquiry", goal=state.goal)

        # In production, use NLP to categorize inquiry
        inquiry_type = "billing_question"  # Placeholder
        urgency = "normal"  # Placeholder

        return {
            "memory": {
                **state.memory,
                "inquiry_type": inquiry_type,
                "urgency": urgency,
            },
            "current_step": state.current_step + 1,
        }

    def gather_context_node(self, state: AgentState) -> Dict[str, Any]:
        """Gather customer context and history."""
        self.logger.info("Gathering customer context")

        # In production, query CRM, order history, etc.
        customer_context = {
            "customer_id": "CUST123",
            "account_status": "active",
            "recent_orders": 3,
            "support_history": ["inquiry_1", "inquiry_2"],
        }

        return {
            "memory": {
                **state.memory,
                "customer_context": customer_context,
            },
            "current_step": state.current_step + 1,
        }

    def search_knowledge_node(self, state: AgentState) -> Dict[str, Any]:
        """Search knowledge base for relevant information."""
        self.logger.info("Searching knowledge base")

        # In production, use vector search on knowledge base
        relevant_articles = [
            {"title": "Billing FAQ", "content": "..."},
            {"title": "Payment Methods", "content": "..."},
        ]

        return {
            "memory": {
                **state.memory,
                "relevant_articles": relevant_articles,
            },
            "current_step": state.current_step + 1,
        }

    def formulate_response_node(self, state: AgentState) -> Dict[str, Any]:
        """Formulate response to customer."""
        self.logger.info("Formulating response")

        # In production, use LLM to generate response
        response = {
            "message": "Thank you for contacting us. Based on your inquiry...",
            "confidence": 0.85,
            "suggested_articles": state.memory.get("relevant_articles", []),
        }

        return {
            "memory": {
                **state.memory,
                "response": response,
            },
            "uncertainty_score": 1.0 - response["confidence"],
            "current_step": state.current_step + 1,
        }

    def escalation_check_node(self, state: AgentState) -> Dict[str, Any]:
        """Check if escalation to human agent is needed."""
        response = state.memory.get("response", {})
        confidence = response.get("confidence", 0.0)

        should_escalate = confidence < 0.7 or state.memory.get("urgency") == "high"

        if should_escalate:
            self.logger.info("Escalating to human agent")
            return {
                "hitl_required": True,
                "result": {
                    "status": "escalated",
                    "reason": "Low confidence or high urgency",
                },
            }

        return {
            "result": {
                "status": "resolved",
                "response": response,
            },
        }

    def should_escalate(self, state: AgentState) -> str:
        """Decide if inquiry should be escalated."""
        if state.hitl_required:
            return "escalate"
        return "respond"


# Example usage
if __name__ == "__main__":
    from tools.tool_manager import ToolManager
    from memory.memory_manager import MemoryManager

    tool_manager = ToolManager()
    memory_manager = MemoryManager()

    agent = CustomerSupportAgent(
        tools=list(tool_manager.tools.values()),
        memory_manager=memory_manager,
    )

    result = agent.run(
        {
            "goal": "Help customer with billing inquiry",
            "initial_state": {},
        }
    )

    print("Support Request Complete!")
    print(f"Result: {result.get('result')}")


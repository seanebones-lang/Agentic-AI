"""Agent registry for multi-agent orchestration."""

from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from pydantic import BaseModel

from observability.logger import LoggerMixin, get_logger

logger = get_logger(__name__)


class AgentStatus(str, Enum):
    """Agent health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class AgentCapability(str, Enum):
    """Standard agent capabilities."""
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    RESEARCH = "research"
    DATA_ANALYSIS = "data_analysis"
    WRITING = "writing"
    REASONING = "reasoning"
    PLANNING = "planning"
    TOOL_USE = "tool_use"
    WEB_SEARCH = "web_search"
    FILE_OPERATIONS = "file_operations"
    DATABASE = "database"
    BROWSER_AUTOMATION = "browser_automation"


@dataclass
class AgentMetadata:
    """Metadata for registered agent."""
    name: str
    description: str
    capabilities: List[AgentCapability]
    required_tools: List[str] = field(default_factory=list)
    cost_tier: str = "standard"  # free, standard, premium
    latency_sla_ms: int = 30000  # Expected max latency
    max_concurrent_runs: int = 5
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AgentInstance:
    """Running agent instance."""
    metadata: AgentMetadata
    factory: Callable[[], Any]  # Factory function to create agent
    status: AgentStatus = AgentStatus.UNKNOWN
    current_load: int = 0
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    last_health_check: Optional[datetime] = None
    last_error: Optional[str] = None


class AgentRegistry(LoggerMixin):
    """
    Registry for agent discovery, health monitoring, and orchestration.

    Features:
    - Agent registration with metadata
    - Capability-based discovery
    - Health checking and load tracking
    - Dynamic agent loading from config
    """

    def __init__(self, health_check_interval: int = 60):
        """
        Initialize agent registry.

        Args:
            health_check_interval: Seconds between health checks
        """
        self._agents: Dict[str, AgentInstance] = {}
        self._health_check_interval = health_check_interval
        self._health_check_task: Optional[Any] = None

    def register(
        self,
        name: str,
        factory: Callable[[], Any],
        metadata: AgentMetadata,
    ) -> None:
        """
        Register an agent.

        Args:
            name: Unique agent name
            factory: Factory function to create agent instance
            metadata: Agent metadata
        """
        if name in self._agents:
            self.logger.warning("Agent already registered, overwriting", name=name)

        instance = AgentInstance(
            metadata=metadata,
            factory=factory,
        )

        self._agents[name] = instance
        self.logger.info(
            "Agent registered",
            name=name,
            capabilities=[c.value for c in metadata.capabilities],
            cost_tier=metadata.cost_tier,
        )

    def unregister(self, name: str) -> bool:
        """
        Unregister an agent.

        Args:
            name: Agent name to unregister

        Returns:
            True if agent was found and removed
        """
        if name in self._agents:
            del self._agents[name]
            self.logger.info("Agent unregistered", name=name)
            return True
        return False

    def get(self, name: str) -> Optional[AgentInstance]:
        """Get agent instance by name."""
        return self._agents.get(name)

    def create_agent(self, name: str) -> Any:
        """
        Create a new agent instance.

        Args:
            name: Agent name

        Returns:
            New agent instance

        Raises:
            ValueError: If agent not found or at capacity
        """
        instance = self._agents.get(name)
        if not instance:
            raise ValueError(f"Agent not found: {name}")

        if instance.current_load >= instance.metadata.max_concurrent_runs:
            raise ValueError(f"Agent at capacity: {name}")

        instance.current_load += 1
        agent = instance.factory()
        return agent

    def release_agent(self, name: str, success: bool = True) -> None:
        """
        Release agent after execution.

        Args:
            name: Agent name
            success: Whether execution succeeded
        """
        instance = self._agents.get(name)
        if instance:
            instance.current_load = max(0, instance.current_load - 1)
            instance.total_runs += 1
            if success:
                instance.successful_runs += 1
            else:
                instance.failed_runs += 1

    def list_agents(
        self,
        capability: Optional[AgentCapability] = None,
        status: Optional[AgentStatus] = None,
        cost_tier: Optional[str] = None,
    ) -> List[AgentInstance]:
        """
        List agents with optional filters.

        Args:
            capability: Filter by capability
            status: Filter by health status
            cost_tier: Filter by cost tier

        Returns:
            List of matching agent instances
        """
        agents = list(self._agents.values())

        if capability:
            agents = [a for a in agents if capability in a.metadata.capabilities]

        if status:
            agents = [a for a in agents if a.status == status]

        if cost_tier:
            agents = [a for a in agents if a.metadata.cost_tier == cost_tier]

        return agents

    def discover_by_capability(
        self,
        capability: AgentCapability,
        max_results: int = 5,
        prefer_healthy: bool = True,
    ) -> List[AgentInstance]:
        """
        Discover agents by capability.

        Args:
            capability: Required capability
            max_results: Maximum agents to return
            prefer_healthy: Sort healthy agents first

        Returns:
            List of agents with the capability
        """
        agents = self.list_agents(capability=capability)

        if prefer_healthy:
            agents.sort(key=lambda a: (
                a.status != AgentStatus.HEALTHY,
                a.current_load / max(1, a.metadata.max_concurrent_runs),
            ))

        return agents[:max_results]

    def get_agent_stats(self, name: str) -> Optional[Dict[str, Any]]:
        """Get agent statistics."""
        instance = self._agents.get(name)
        if not instance:
            return None

        success_rate = 0.0
        if instance.total_runs > 0:
            success_rate = instance.successful_runs / instance.total_runs

        return {
            "name": name,
            "status": instance.status.value,
            "current_load": instance.current_load,
            "max_concurrent": instance.metadata.max_concurrent_runs,
            "total_runs": instance.total_runs,
            "success_rate": success_rate,
            "last_health_check": instance.last_health_check.isoformat() if instance.last_health_check else None,
            "capabilities": [c.value for c in instance.metadata.capabilities],
        }

    def get_registry_stats(self) -> Dict[str, Any]:
        """Get overall registry statistics."""
        total = len(self._agents)
        healthy = sum(1 for a in self._agents.values() if a.status == AgentStatus.HEALTHY)
        degraded = sum(1 for a in self._agents.values() if a.status == AgentStatus.DEGRADED)
        unhealthy = sum(1 for a in self._agents.values() if a.status == AgentStatus.UNHEALTHY)

        total_load = sum(a.current_load for a in self._agents.values())
        total_capacity = sum(a.metadata.max_concurrent_runs for a in self._agents.values())

        return {
            "total_agents": total,
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "total_load": total_load,
            "total_capacity": total_capacity,
            "utilization": total_load / max(1, total_capacity),
        }

    async def health_check_agent(self, name: str) -> AgentStatus:
        """
        Perform health check on an agent.

        Args:
            name: Agent name

        Returns:
            Health status
        """
        instance = self._agents.get(name)
        if not instance:
            return AgentStatus.UNKNOWN

        try:
            # Create agent and run a simple test
            agent = instance.factory()

            # Try to run a minimal health check
            if hasattr(agent, "health_check"):
                result = await agent.health_check() if callable(getattr(agent, "health_check", None)) else True
                status = AgentStatus.HEALTHY if result else AgentStatus.DEGRADED
            else:
                # Default: if we can create it, it's healthy
                status = AgentStatus.HEALTHY

            instance.status = status
            instance.last_health_check = datetime.utcnow()
            instance.last_error = None

        except Exception as e:
            instance.status = AgentStatus.UNHEALTHY
            instance.last_error = str(e)
            instance.last_health_check = datetime.utcnow()
            self.logger.warning("Agent health check failed", name=name, error=str(e))

        return instance.status

    async def health_check_all(self) -> Dict[str, AgentStatus]:
        """Run health checks on all agents."""
        results = {}
        for name in self._agents:
            results[name] = await self.health_check_agent(name)
        return results

    def start_health_checks(self) -> None:
        """Start periodic health checks."""
        import asyncio

        async def _health_check_loop():
            while True:
                await asyncio.sleep(self._health_check_interval)
                await self.health_check_all()

        if self._health_check_task is None:
            self._health_check_task = asyncio.create_task(_health_check_loop())
            self.logger.info("Health check loop started", interval=self._health_check_interval)

    def stop_health_checks(self) -> None:
        """Stop periodic health checks."""
        if self._health_check_task:
            self._health_check_task.cancel()
            self._health_check_task = None
            self.logger.info("Health check loop stopped")


# Global registry instance
_registry: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    """Get global agent registry instance."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


def register_agent(
    name: str,
    factory: Callable[[], Any],
    description: str,
    capabilities: List[AgentCapability],
    **metadata_kwargs,
) -> None:
    """Convenience function to register agent."""
    metadata = AgentMetadata(
        name=name,
        description=description,
        capabilities=capabilities,
        **metadata_kwargs,
    )
    get_agent_registry().register(name, factory, metadata)
"""Metrics collection and CloudWatch publishing."""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from config import get_settings
from observability.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Metric:
    """Represents a single metric data point."""

    name: str
    value: float
    unit: str = "None"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    dimensions: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """Collects and publishes metrics to CloudWatch."""

    def __init__(self) -> None:
        """Initialize metrics collector."""
        self.settings = get_settings()
        self.metrics: List[Metric] = []
        self.cloudwatch_client = None

        if self.settings.cloudwatch_enabled:
            try:
                self.cloudwatch_client = boto3.client(
                    "cloudwatch",
                    region_name=self.settings.aws_region,
                    aws_access_key_id=self.settings.aws_access_key_id,
                    aws_secret_access_key=self.settings.aws_secret_access_key,
                )
                logger.info("CloudWatch metrics client initialized")
            except Exception as e:
                logger.error("Failed to initialize CloudWatch client", error=str(e))

    def record_metric(
        self,
        name: str,
        value: float,
        unit: str = "None",
        dimensions: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a metric data point."""
        metric = Metric(
            name=name,
            value=value,
            unit=unit,
            dimensions=dimensions or {},
        )
        self.metrics.append(metric)
        logger.debug("Metric recorded", metric_name=name, value=value, unit=unit)

    def record_execution_time(self, operation: str, duration_seconds: float) -> None:
        """Record execution time for an operation."""
        self.record_metric(
            name="ExecutionTime",
            value=duration_seconds,
            unit="Seconds",
            dimensions={"Operation": operation},
        )

    def record_token_usage(self, tokens: int, model: str) -> None:
        """Record LLM token usage."""
        self.record_metric(
            name="TokenUsage",
            value=float(tokens),
            unit="Count",
            dimensions={"Model": model},
        )

    def record_agent_execution(
        self, agent_type: str, success: bool, duration_seconds: float
    ) -> None:
        """Record agent execution metrics."""
        self.record_metric(
            name="AgentExecution",
            value=1.0,
            unit="Count",
            dimensions={"AgentType": agent_type, "Success": str(success)},
        )
        self.record_execution_time(f"Agent_{agent_type}", duration_seconds)

    def record_hitl_intervention(self, reason: str, approved: bool) -> None:
        """Record HITL intervention metrics."""
        self.record_metric(
            name="HITLIntervention",
            value=1.0,
            unit="Count",
            dimensions={"Reason": reason, "Approved": str(approved)},
        )

    def record_tool_usage(self, tool_name: str, success: bool, duration_seconds: float) -> None:
        """Record tool usage metrics."""
        self.record_metric(
            name="ToolUsage",
            value=1.0,
            unit="Count",
            dimensions={"Tool": tool_name, "Success": str(success)},
        )
        self.record_execution_time(f"Tool_{tool_name}", duration_seconds)

    def record_error(self, error_type: str, component: str) -> None:
        """Record error occurrence."""
        self.record_metric(
            name="Error",
            value=1.0,
            unit="Count",
            dimensions={"ErrorType": error_type, "Component": component},
        )

    def publish_metrics(self, namespace: str = "AgenticAI") -> bool:
        """Publish collected metrics to CloudWatch."""
        if not self.cloudwatch_client or not self.metrics:
            logger.debug("No metrics to publish or CloudWatch not enabled")
            return False

        try:
            # Convert metrics to CloudWatch format
            metric_data = []
            for metric in self.metrics:
                metric_datum = {
                    "MetricName": metric.name,
                    "Value": metric.value,
                    "Unit": metric.unit,
                    "Timestamp": metric.timestamp,
                }

                if metric.dimensions:
                    metric_datum["Dimensions"] = [
                        {"Name": k, "Value": v} for k, v in metric.dimensions.items()
                    ]

                metric_data.append(metric_datum)

            # Publish in batches of 20 (CloudWatch limit)
            batch_size = 20
            for i in range(0, len(metric_data), batch_size):
                batch = metric_data[i : i + batch_size]
                self.cloudwatch_client.put_metric_data(Namespace=namespace, MetricData=batch)

            logger.info("Published metrics to CloudWatch", count=len(self.metrics))
            self.metrics.clear()
            return True

        except ClientError as e:
            logger.error("Failed to publish metrics to CloudWatch", error=str(e))
            return False

    def get_metrics_summary(self) -> Dict[str, int]:
        """Get summary of collected metrics."""
        summary: Dict[str, int] = {}
        for metric in self.metrics:
            summary[metric.name] = summary.get(metric.name, 0) + 1
        return summary


class MetricsContext:
    """Context manager for timing operations and recording metrics."""

    def __init__(self, collector: MetricsCollector, operation: str):
        """Initialize metrics context."""
        self.collector = collector
        self.operation = operation
        self.start_time: Optional[float] = None

    def __enter__(self) -> "MetricsContext":
        """Start timing."""
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type: type, exc_val: Exception, exc_tb: object) -> None:
        """Record execution time."""
        if self.start_time:
            duration = time.time() - self.start_time
            self.collector.record_execution_time(self.operation, duration)

            if exc_type:
                self.collector.record_error(
                    error_type=exc_type.__name__, component=self.operation
                )


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


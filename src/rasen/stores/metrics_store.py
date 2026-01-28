"""Session metrics persistence and aggregation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from rasen.models import AggregateMetrics, SessionMetrics
from rasen.stores._atomic import atomic_write, file_lock


class MetricsData(BaseModel):
    """Container for all metrics data."""

    sessions: list[SessionMetrics] = Field(default_factory=list)
    aggregate: AggregateMetrics = Field(default_factory=AggregateMetrics)


class MetricsStore:
    """Manages session metrics persistence and aggregation."""

    def __init__(self, rasen_dir: Path) -> None:
        """Initialize metrics store.

        Args:
            rasen_dir: Path to .rasen directory
        """
        self.path = rasen_dir / "metrics.json"
        self.rasen_dir = rasen_dir

    def _load_data(self) -> MetricsData:
        """Load metrics data from disk.

        Returns:
            MetricsData with sessions and aggregate metrics.
        """
        if not self.path.exists():
            return MetricsData()

        try:
            with file_lock(self.path, shared=True):
                content = self.path.read_text()
                return MetricsData.model_validate_json(content)
        except Exception:
            return MetricsData()

    def _save_data(self, data: MetricsData) -> None:
        """Save metrics data atomically.

        Args:
            data: MetricsData to save.
        """
        self.rasen_dir.mkdir(parents=True, exist_ok=True)
        with file_lock(self.path, shared=False):
            atomic_write(self.path, data.model_dump_json(indent=2))

    def record_session(self, metrics: SessionMetrics) -> None:
        """Record a completed session's metrics.

        Args:
            metrics: Session metrics to record.
        """
        data = self._load_data()

        # Add to session history
        data.sessions.append(metrics)

        # Update aggregate metrics
        agg = data.aggregate
        agg.total_sessions += 1
        agg.total_duration_seconds += metrics.duration_seconds
        agg.total_input_tokens += metrics.input_tokens
        agg.total_output_tokens += metrics.output_tokens
        agg.total_tokens += metrics.total_tokens

        # Track by agent type
        agent_type = metrics.agent_type
        agg.sessions_by_agent[agent_type] = agg.sessions_by_agent.get(agent_type, 0) + 1
        agg.tokens_by_agent[agent_type] = (
            agg.tokens_by_agent.get(agent_type, 0) + metrics.total_tokens
        )

        # Update timestamps
        if agg.started_at is None:
            agg.started_at = metrics.started_at
        agg.completed_at = metrics.completed_at or datetime.now(UTC)

        self._save_data(data)

    def get_aggregate(self) -> AggregateMetrics:
        """Get aggregate metrics across all sessions.

        Returns:
            AggregateMetrics with totals.
        """
        data = self._load_data()
        return data.aggregate

    def get_all_sessions(self) -> list[SessionMetrics]:
        """Get all recorded session metrics.

        Returns:
            List of all SessionMetrics.
        """
        data = self._load_data()
        return data.sessions

    def get_by_agent(self, agent_type: str) -> list[SessionMetrics]:
        """Get all sessions for a specific agent type.

        Args:
            agent_type: Type of agent (initializer, coder, reviewer, qa).

        Returns:
            List of SessionMetrics for the agent type.
        """
        data = self._load_data()
        return [s for s in data.sessions if s.agent_type == agent_type]

    def get_recent_sessions(self, count: int = 10) -> list[SessionMetrics]:
        """Get most recent sessions.

        Args:
            count: Number of sessions to return.

        Returns:
            List of most recent SessionMetrics.
        """
        data = self._load_data()
        return data.sessions[-count:] if data.sessions else []

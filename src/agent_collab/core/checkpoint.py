"""Checkpoint persistence for workflow execution state."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class Checkpoint:
    """Represents a saved workflow execution state.

    Attributes:
        checkpoint_id: Unique identifier for this checkpoint.
        workflow_name: Name of the workflow being executed.
        completed_tasks: List of task IDs that have completed successfully.
        task_outputs: Map of task ID to its output string.
        timestamp: ISO-format UTC timestamp of when the checkpoint was created.
        metadata: Arbitrary extra metadata stored with the checkpoint.
    """

    checkpoint_id: str
    workflow_name: str
    completed_tasks: list[str] = field(default_factory=list)
    task_outputs: dict[str, str] = field(default_factory=dict)
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class CheckpointManager:
    """Manages checkpoint persistence to disk.

    Checkpoints are stored as JSON files under ``~/.agent-collab/checkpoints/``.

    Attributes:
        base_dir: Directory where checkpoint files are stored.
    """

    DEFAULT_DIR = "~/.agent-collab/checkpoints"

    def __init__(self, base_dir: str | Path | None = None) -> None:
        """Initialise the CheckpointManager.

        Args:
            base_dir: Directory for storing checkpoint files.
                Defaults to ``~/.agent-collab/checkpoints``.
        """
        self.base_dir = Path(base_dir or self.DEFAULT_DIR).expanduser()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, checkpoint: Checkpoint) -> str:
        """Persist a checkpoint to disk and return its ID.

        Args:
            checkpoint: The checkpoint to save. If ``timestamp`` is empty,
                it will be set to the current UTC time.

        Returns:
            The checkpoint ID.
        """
        if not checkpoint.timestamp:
            checkpoint.timestamp = datetime.now(timezone.utc).isoformat()
        path = self._path_for(checkpoint.checkpoint_id)
        path.write_text(
            json.dumps(asdict(checkpoint), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return checkpoint.checkpoint_id

    def load(self, checkpoint_id: str) -> Checkpoint:
        """Load a checkpoint from disk by its ID.

        Args:
            checkpoint_id: The checkpoint identifier.

        Returns:
            The loaded Checkpoint instance.

        Raises:
            FileNotFoundError: If the checkpoint file does not exist.
        """
        path = self._path_for(checkpoint_id)
        if not path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return Checkpoint(**data)

    def list_checkpoints(self) -> list[Checkpoint]:
        """List all saved checkpoints, sorted by timestamp descending.

        Returns:
            A list of Checkpoint objects.
        """
        checkpoints: list[Checkpoint] = []
        for p in self.base_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                checkpoints.append(Checkpoint(**data))
            except (json.JSONDecodeError, TypeError):
                continue
        checkpoints.sort(key=lambda c: c.timestamp, reverse=True)
        return checkpoints

    def delete(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint file.

        Args:
            checkpoint_id: The checkpoint identifier.

        Returns:
            True if the file was deleted, False if it did not exist.
        """
        path = self._path_for(checkpoint_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def _path_for(self, checkpoint_id: str) -> Path:
        """Return the file path for a given checkpoint ID.

        Args:
            checkpoint_id: The checkpoint identifier.

        Returns:
            Path to the checkpoint JSON file.
        """
        return self.base_dir / f"{checkpoint_id}.json"

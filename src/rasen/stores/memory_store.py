"""Cross-session memory persistence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from rasen.stores._atomic import atomic_write, file_lock


@dataclass
class Memory:
    """A single memory entry."""

    id: str
    type: Literal["pattern", "decision", "fix"]
    content: str
    tags: list[str]
    created_at: datetime


class MemoryStore:
    """Manages cross-session memory in Markdown format."""

    def __init__(self, path: Path) -> None:
        """Initialize memory store.

        Args:
            path: Path to memories.md file
        """
        self.path = path

    def load(self) -> list[Memory]:
        """Parse memories from markdown file.

        Returns:
            List of Memory objects
        """
        if not self.path.exists():
            return []

        content = self.path.read_text()
        return self._parse_memories(content)

    def append(self, memory: Memory) -> None:
        """Append new memory to file.

        Args:
            memory: Memory to append
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing content or create template
        if self.path.exists():
            content = self.path.read_text()
        else:
            content = "# Memories\n\n## Patterns\n\n## Decisions\n\n## Fixes\n"

        # Find section and append
        section_map = {
            "pattern": "## Patterns",
            "decision": "## Decisions",
            "fix": "## Fixes",
        }
        section = section_map.get(memory.type, "## Patterns")

        # Format memory entry
        entry = self._format_memory(memory)

        # Insert after section header
        if section in content:
            parts = content.split(section)
            parts[1] = f"\n{entry}" + parts[1]
            content = section.join(parts)
        else:
            content += f"\n{section}\n{entry}"

        with file_lock(self.path, shared=False):
            atomic_write(self.path, content)

    def format_for_injection(self, max_tokens: int = 2000) -> str:
        """Format memories for prompt injection.

        Args:
            max_tokens: Maximum tokens to include

        Returns:
            Formatted memories string
        """
        memories = self.load()
        if not memories:
            return ""

        lines = ["## Relevant Memories from Previous Sessions\n"]
        token_estimate = 10  # Header

        for memory in reversed(memories):  # Most recent first
            entry = f"- **{memory.type}**: {memory.content}\n"
            entry_tokens = int(len(entry.split()) * 1.3)  # Rough estimate

            if token_estimate + entry_tokens > max_tokens:
                break

            lines.append(entry)
            token_estimate += entry_tokens

        return "".join(lines)

    def search(self, query: str) -> list[Memory]:
        """Search memories by content/tags.

        Args:
            query: Search query

        Returns:
            List of matching Memory objects
        """
        memories = self.load()
        query_lower = query.lower()

        return [
            m
            for m in memories
            if query_lower in m.content.lower() or any(query_lower in tag.lower() for tag in m.tags)
        ]

    def _parse_memories(self, content: str) -> list[Memory]:
        """Parse markdown content into Memory objects.

        Args:
            content: Markdown content

        Returns:
            List of Memory objects
        """
        memories = []
        pattern = r"### (mem-\d{8}-\d+)\n> (.*?)\n<!-- tags: (.*?) \| created: (.*?) -->"

        for match in re.finditer(pattern, content, re.DOTALL):
            mem_id = match.group(1)
            mem_content = match.group(2).strip()
            tags = [t.strip() for t in match.group(3).split(",")]
            created = datetime.fromisoformat(match.group(4))

            # Determine type from section
            start = match.start()
            before = content[:start]
            if (
                "## Decisions" in before
                and "## Fixes" not in before[before.rfind("## Decisions") :]
            ):
                mem_type: Literal["pattern", "decision", "fix"] = "decision"
            elif "## Fixes" in before:
                mem_type = "fix"
            else:
                mem_type = "pattern"

            memories.append(
                Memory(
                    id=mem_id,
                    type=mem_type,
                    content=mem_content,
                    tags=tags,
                    created_at=created,
                )
            )

        return memories

    def _format_memory(self, memory: Memory) -> str:
        """Format memory as markdown entry.

        Args:
            memory: Memory to format

        Returns:
            Formatted markdown string
        """
        tags_str = ", ".join(memory.tags)
        timestamp = memory.created_at.isoformat()
        return (
            f"### {memory.id}\n"
            f"> {memory.content}\n"
            f"<!-- tags: {tags_str} | created: {timestamp} -->\n"
        )

    def create_memory_id(self) -> str:
        """Generate unique memory ID.

        Returns:
            Unique memory ID (e.g., mem-20260127-001)
        """
        date = datetime.now(UTC).strftime("%Y%m%d")
        # Count existing memories for today
        memories = self.load()
        today_count = sum(1 for m in memories if date in m.id)
        return f"mem-{date}-{today_count + 1:03d}"

# Long-Running Agent Workflow Proposal

**Project:** Long-Running-Agent-Loop
**Date:** 2026-01-27
**Status:** FINAL PROPOSAL
**Based On:** Anthropic Engineering Best Practices + Community Tool Analysis

---

## Executive Summary

This proposal defines a **proven workflow for complex long-running agent loops** that produces production-ready code through systematic Plan → Code → AI Review → AI QA phases. The design combines Anthropic's official two-agent pattern with the best orchestration approaches from community tools (Claude-Flow, Auto-Claude, Oh-My-ClaudeCode).

**Core Guarantee:** By following this workflow, complex projects spanning multiple context windows will maintain consistency, produce tested code, and avoid common failure modes like premature completion or state corruption.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR (External Loop)                     │
│  - Manages session lifecycle with 3-second delay between iterations     │
│  - Routes to appropriate phase (Initialize → Code → Review → QA)        │
│  - Tracks overall progress and handles Ctrl+C graceful shutdown         │
│  - Auto-continues until all features pass or manual intervention        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          ▼                         ▼                         ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  SESSION 1       │    │  SESSIONS 2-N    │    │  REVIEW/QA       │
│  INITIALIZER     │ →  │  CODING AGENT    │ →  │  AGENTS          │
│  - Creates state │    │  - Single feature│    │  - Code review   │
│  - 200+ features │    │  - Git commits   │    │  - Test verify   │
│  - init.sh       │    │  - Progress log  │    │  - Bug detection │
└──────────────────┘    └──────────────────┘    └──────────────────┘
          │                         │                         │
          └─────────────────────────┼─────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         STATE PERSISTENCE LAYER                          │
│  - feature_list.json (200+ features, pass/fail tracking)                │
│  - claude-progress.txt (session summaries, next steps)                  │
│  - review_findings.json (code review issues by severity)                │
│  - qa_results.json (test results, coverage metrics)                     │
│  - Git commits (checkpoints, rollback capability)                       │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. The Four-Phase Workflow

### Phase 1: PLAN (Initializer Agent - Session 1)

**Purpose:** Establish complete project foundation that enables autonomous work across unlimited sessions.

**Actions:**
1. Generate `feature_list.json` with 200+ granular features, all marked `"passes": false`
2. Create `init.sh` script for environment setup (server start, dependencies)
3. Initialize `claude-progress.txt` with project overview
4. Create initial git commit documenting setup
5. Generate `test_plan.json` with verification steps for each feature

**Critical Constraint (from Anthropic):**
> "It is unacceptable to remove or edit tests because this could lead to missing or buggy functionality"

**Feature List Structure:**
```json
{
  "features": [
    {
      "id": 1,
      "category": "functional",
      "priority": "high",
      "description": "User can create new account with email",
      "steps": [
        "Navigate to signup page",
        "Enter valid email and password",
        "Submit form",
        "Verify confirmation email sent",
        "Verify user record created in database"
      ],
      "passes": false,
      "reviewed": false,
      "qa_verified": false
    }
  ],
  "summary": {
    "total": 200,
    "passing": 0,
    "reviewed": 0,
    "qa_verified": 0
  }
}
```

**Why JSON over Markdown:** Models are "less likely to inappropriately change or overwrite JSON files compared to Markdown" (Anthropic Engineering).

---

### Phase 2: CODE (Coding Agent - Sessions 2+)

**Purpose:** Implement features incrementally with clean, committable code.

**Session Start Protocol (from Anthropic):**
```
1. Run `pwd` to confirm working directory
2. Read `claude-progress.txt` for context
3. Read `feature_list.json` for remaining work
4. Review `git log --oneline -20` for recent changes
5. Run `./init.sh` to start development environment
6. Verify fundamental features still working
7. Select highest-priority uncompleted feature
```

**Development Rules:**
- Work on **SINGLE feature only** per session
- Commit with descriptive message after each feature
- Update `claude-progress.txt` with session summary
- Run tests before marking `"passes": true`
- **Never declare victory early** - only mark passing after verification

**Session End Protocol:**
```
1. Run all tests related to implemented feature
2. If tests pass: Update feature_list.json with "passes": true
3. Git commit with message: "feat: [feature description]"
4. Update claude-progress.txt:
   - What was accomplished
   - What's next
   - Any blockers or notes for next session
5. Run `git status` to confirm clean working directory
```

**Context Awareness Prompting (from Anthropic):**
```
Your context window will be automatically compacted as it approaches its limit,
allowing you to continue working indefinitely from where you left off. Therefore:

- Do not stop tasks early due to token budget concerns
- As you approach your token budget limit, save your current progress and state
  to memory before the context window refreshes
- Always be as persistent and autonomous as possible
- Complete tasks fully, even if the end of your budget is approaching
- Never artificially stop any task regardless of the context remaining
```

---

### Phase 3: REVIEW (Code Review Agent)

**Purpose:** Catch bugs, security issues, and design problems before QA.

**Trigger:** After every 3-5 coding sessions OR when `passing` count reaches checkpoint thresholds.

**Review Agent Configuration:**
```yaml
# .claude/agents/code-reviewer.md
---
name: code-reviewer
description: Senior developer reviewing code for quality, security, and patterns
tools:
  - Read
  - Glob
  - Grep
---
# Code Review Agent

You are a senior software engineer conducting a thorough code review.

## Review Checklist
1. **Correctness**: Does the code do what it's supposed to?
2. **Security**: Any OWASP Top 10 vulnerabilities?
3. **Performance**: Any obvious inefficiencies?
4. **Maintainability**: Is the code readable and well-structured?
5. **Testing**: Are there adequate tests?
6. **Documentation**: Are complex parts documented?

## Output Format
Write findings to `review_findings.json`:
{
  "session": 5,
  "features_reviewed": [1, 2, 3],
  "findings": [
    {
      "severity": "high|medium|low",
      "file": "path/to/file.ts",
      "line": 42,
      "issue": "Description of problem",
      "suggestion": "How to fix"
    }
  ],
  "approved": false
}
```

**Review Workflow:**
1. Read all files changed since last review (via git diff)
2. Analyze against checklist
3. Write findings to `review_findings.json`
4. If high-severity issues: Block QA phase, create fix tasks
5. If approved: Mark features as `"reviewed": true` in feature_list.json

---

### Phase 4: QA (Quality Assurance Agent)

**Purpose:** Verify features work as intended through end-to-end testing.

**QA Agent Configuration:**
```yaml
# .claude/agents/qa-tester.md
---
name: qa-tester
description: QA engineer verifying features through end-to-end testing
tools:
  - Read
  - Bash
  - Glob
  - Grep
---
# QA Testing Agent

You verify implemented features work correctly from a user's perspective.

## Testing Approach
1. Use Puppeteer MCP for browser automation
2. Test features as a human user would
3. Verify against acceptance criteria in feature_list.json
4. Document failures with screenshots/logs

## Output Format
Write results to `qa_results.json`:
{
  "session": 6,
  "features_tested": [1, 2, 3],
  "results": [
    {
      "feature_id": 1,
      "status": "pass|fail",
      "evidence": "Description of verification steps",
      "issues": []
    }
  ]
}
```

**QA Workflow:**
1. Read `feature_list.json` for features marked `"passes": true, "reviewed": true`
2. Execute test steps defined in each feature
3. Use Puppeteer MCP for browser-based verification
4. Write results to `qa_results.json`
5. If pass: Mark `"qa_verified": true` in feature_list.json
6. If fail: Create regression task, mark `"passes": false`

---

## 3. State File Specifications

### feature_list.json (Primary State)

```json
{
  "project": "my-app",
  "version": "1.0.0",
  "features": [
    {
      "id": 1,
      "category": "auth",
      "priority": "high",
      "description": "User login with email/password",
      "steps": ["Step 1", "Step 2", "Step 3"],
      "passes": true,
      "reviewed": true,
      "qa_verified": true,
      "implemented_session": 3,
      "reviewed_session": 5,
      "qa_session": 6
    }
  ],
  "summary": {
    "total": 200,
    "passing": 150,
    "reviewed": 145,
    "qa_verified": 140,
    "remaining": 50
  }
}
```

**Critical Rule:** Agents may ONLY modify `passes`, `reviewed`, `qa_verified`, and session tracking fields. Description and steps are IMMUTABLE.

### claude-progress.txt (Session Log)

```text
=== Session 7 Summary ===
Date: 2026-01-27 14:30 UTC
Duration: ~12 minutes

COMPLETED:
- Implemented feature #42: Password reset flow
- Fixed regression in feature #38 (email validation)

CURRENT STATE:
- 155/200 features passing
- 150/200 features reviewed
- 145/200 features QA verified

NEXT SESSION:
- Continue with feature #43: Two-factor authentication
- Note: Requires SMS provider API key (see .env.example)

BLOCKERS:
- None

NOTES:
- Found edge case in email validation, documented in CLAUDE.md
```

### review_findings.json (Code Review State)

```json
{
  "reviews": [
    {
      "session": 5,
      "timestamp": "2026-01-27T14:30:00Z",
      "features_reviewed": [40, 41, 42],
      "findings": [
        {
          "id": "R5-001",
          "severity": "high",
          "status": "open|fixed|wontfix",
          "file": "src/auth/login.ts",
          "line": 42,
          "issue": "SQL injection vulnerability in user lookup",
          "suggestion": "Use parameterized query instead of string concatenation",
          "fixed_in_session": null
        }
      ],
      "approved": false
    }
  ],
  "summary": {
    "open_high": 1,
    "open_medium": 3,
    "open_low": 5,
    "fixed": 45
  }
}
```

### qa_results.json (QA State)

```json
{
  "test_runs": [
    {
      "session": 6,
      "timestamp": "2026-01-27T15:00:00Z",
      "features_tested": [38, 39, 40],
      "environment": "development",
      "results": [
        {
          "feature_id": 38,
          "status": "pass",
          "duration_ms": 3500,
          "steps_executed": 5,
          "evidence": "Screenshot: qa_evidence/feature_38_success.png"
        },
        {
          "feature_id": 39,
          "status": "fail",
          "duration_ms": 2100,
          "steps_executed": 3,
          "failure_step": 3,
          "error": "Expected 'Welcome' text not found",
          "evidence": "Screenshot: qa_evidence/feature_39_failure.png"
        }
      ]
    }
  ],
  "summary": {
    "total_tested": 140,
    "passed": 138,
    "failed": 2,
    "pass_rate": "98.6%"
  }
}
```

---

## 4. Orchestrator Implementation

### Option A: Shell Script (Simplest)

```bash
#!/bin/bash
# orchestrator.sh - Simple long-running loop

PROJECT_DIR="/path/to/project"
ITERATION=0
PHASE="initialize"

determine_phase() {
    local features_json="$PROJECT_DIR/feature_list.json"

    if [ ! -f "$features_json" ]; then
        echo "initialize"
        return
    fi

    local passing=$(jq '.summary.passing' "$features_json")
    local reviewed=$(jq '.summary.reviewed' "$features_json")
    local qa_verified=$(jq '.summary.qa_verified' "$features_json")
    local total=$(jq '.summary.total' "$features_json")

    # Every 5 new passing features, trigger review
    local unreviewd=$((passing - reviewed))
    if [ $unreviewd -ge 5 ]; then
        echo "review"
        return
    fi

    # Every 5 new reviewed features, trigger QA
    local untested=$((reviewed - qa_verified))
    if [ $untested -ge 5 ]; then
        echo "qa"
        return
    fi

    # Default to coding
    echo "code"
}

while true; do
    ITERATION=$((ITERATION + 1))
    PHASE=$(determine_phase)

    echo "=== Iteration $ITERATION: Phase $PHASE ==="

    case $PHASE in
        "initialize")
            claude -p "$(cat prompts/initializer_prompt.md)" \
                   --allowedTools Read,Write,Edit,Bash,Glob
            ;;
        "code")
            claude -p "$(cat prompts/coding_prompt.md)" \
                   --allowedTools Read,Write,Edit,Bash,Glob,Grep
            ;;
        "review")
            claude -p "$(cat prompts/review_prompt.md)" \
                   --allowedTools Read,Glob,Grep
            ;;
        "qa")
            claude -p "$(cat prompts/qa_prompt.md)" \
                   --allowedTools Read,Bash,Glob,Grep
            ;;
    esac

    # Check completion
    if [ -f "$PROJECT_DIR/feature_list.json" ]; then
        local qa_verified=$(jq '.summary.qa_verified' "$PROJECT_DIR/feature_list.json")
        local total=$(jq '.summary.total' "$PROJECT_DIR/feature_list.json")

        if [ "$qa_verified" -eq "$total" ]; then
            echo "All features complete and verified!"
            exit 0
        fi
    fi

    echo "Waiting 3 seconds before next iteration..."
    sleep 3
done
```

### Option B: Claude Agent SDK (Python) - Based on Auto-Claude Patterns

```python
#!/usr/bin/env python3
"""
orchestrator.py - Production-grade long-running agent orchestrator
Based on Auto-Claude's proven SDK patterns (the only framework using actual SDK)

Key patterns from Auto-Claude architecture analysis:
- Uses create_client() for SDK sessions, NOT raw Anthropic API
- Git worktree isolation for safe parallel development
- Dual-layer memory (Graphiti semantic + file-based fallback)
- 4-phase pipeline: Planner → Coder → QA Reviewer → QA Fixer
- Post-session processing in Python (100% reliable bookkeeping)
"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Optional

# Auto-Claude pattern: Always use the SDK client factory, never raw API
from core.client import create_client  # NOT: from anthropic import Anthropic


class LongRunningOrchestrator:
    def __init__(self, project_dir: Path, spec_name: str):
        self.project_dir = project_dir
        self.spec_name = spec_name
        self.spec_dir = project_dir / ".orchestrator" / "specs" / spec_name
        self.worktree_dir: Optional[Path] = None
        self.iteration = 0

        # Ensure spec directory exists
        self.spec_dir.mkdir(parents=True, exist_ok=True)

    # ========== GIT WORKTREE ISOLATION (from Auto-Claude/ralph-orchestrator) ==========

    def _create_worktree(self) -> Path:
        """Create isolated git worktree for safe development."""
        worktree_path = self.project_dir / ".worktrees" / self.spec_name
        branch_name = f"orchestrator/{self.spec_name}"

        if not worktree_path.exists():
            # Create branch from current HEAD
            subprocess.run(
                ["git", "branch", branch_name],
                cwd=self.project_dir, check=False
            )
            # Create worktree
            subprocess.run(
                ["git", "worktree", "add", str(worktree_path), branch_name],
                cwd=self.project_dir, check=True
            )

        self.worktree_dir = worktree_path
        return worktree_path

    def _cleanup_worktree(self):
        """Remove worktree after merge or discard."""
        if self.worktree_dir and self.worktree_dir.exists():
            subprocess.run(
                ["git", "worktree", "remove", str(self.worktree_dir)],
                cwd=self.project_dir, check=False
            )

    # ========== SDK CLIENT CREATION (from Auto-Claude core/client.py) ==========

    def _create_agent_client(self, agent_type: str, thinking_budget: int = 4096):
        """
        Create SDK client with agent-specific configuration.

        Auto-Claude pattern: Different agents get different tool permissions:
        - planner: Read-only filesystem, project analysis
        - coder: Full filesystem write, git, package managers, tests
        - qa_reviewer: Test execution, project inspection
        - qa_fixer: Filesystem write, git ops, test execution
        """
        return create_client(
            project_dir=self.worktree_dir or self.project_dir,
            spec_dir=self.spec_dir,
            model="claude-sonnet-4-5-20250929",
            agent_type=agent_type,
            max_thinking_tokens=thinking_budget
        )

    # ========== STATE MANAGEMENT ==========

    def _load_state(self) -> dict:
        state_file = self.spec_dir / "implementation_plan.json"
        if not state_file.exists():
            return {"phases": [], "summary": {"total": 0, "completed": 0}}
        return json.loads(state_file.read_text())

    def _save_state(self, state: dict):
        state_file = self.spec_dir / "implementation_plan.json"
        state_file.write_text(json.dumps(state, indent=2))

    def _get_next_subtask(self) -> Optional[dict]:
        """Find next pending subtask from implementation plan."""
        state = self._load_state()
        for phase in state.get("phases", []):
            for subtask in phase.get("subtasks", []):
                if subtask.get("status") == "pending":
                    return subtask
        return None

    # ========== PHASE EXECUTION (Auto-Claude 4-phase pipeline) ==========

    async def run_planner(self):
        """Phase 1: Planner creates subtask-based implementation plan."""
        client = self._create_agent_client("planner", thinking_budget=16384)

        prompt = self._load_prompt("planner_prompt.md")
        response = client.create_agent_session(
            name=f"planner-{self.spec_name}",
            starting_message=prompt
        )

        # Post-session: Python handles plan extraction (100% reliable)
        self._extract_and_save_plan(response)

    async def run_coder(self, subtask: dict):
        """Phase 2: Coder implements individual subtask."""
        client = self._create_agent_client("coder", thinking_budget=4096)

        prompt = self._build_coder_prompt(subtask)
        response = client.create_agent_session(
            name=f"coder-{subtask['id']}",
            starting_message=prompt
        )

        # Post-session: Update plan, record commits, sync memory
        self._post_coder_processing(subtask, response)

    async def run_qa_reviewer(self):
        """Phase 3: QA Reviewer validates against acceptance criteria."""
        client = self._create_agent_client("qa_reviewer", thinking_budget=16384)

        prompt = self._load_prompt("qa_reviewer_prompt.md")
        response = client.create_agent_session(
            name=f"qa-review-{self.spec_name}",
            starting_message=prompt
        )

        # Post-session: Generate QA report, determine pass/fail
        return self._process_qa_result(response)

    async def run_qa_fixer(self, qa_issues: list):
        """Phase 4: QA Fixer resolves issues identified by reviewer."""
        client = self._create_agent_client("qa_fixer", thinking_budget=8192)

        prompt = self._build_fixer_prompt(qa_issues)
        response = client.create_agent_session(
            name=f"qa-fix-{self.spec_name}",
            starting_message=prompt
        )

        # Post-session: Verify fixes applied
        self._verify_fixes(response)

    # ========== MAIN ORCHESTRATION LOOP ==========

    async def run(self):
        """
        Main orchestration loop following Auto-Claude pipeline:
        1. PLAN: Create implementation plan with subtasks
        2. CODE: Implement subtasks iteratively
        3. QA REVIEW: Validate against acceptance criteria
        4. QA FIX: Loop until all issues resolved
        """
        print(f"Starting orchestrator for {self.spec_name}")

        # Create isolated worktree for safe development
        self._create_worktree()

        try:
            # Phase 1: Planning (if no plan exists)
            if not self._load_state().get("phases"):
                print("\n=== Phase 1: PLANNING ===")
                await self.run_planner()

            # Phase 2: Coding (iterate through subtasks)
            while subtask := self._get_next_subtask():
                self.iteration += 1
                print(f"\n=== Phase 2: CODING (Iteration {self.iteration}) ===")
                print(f"Subtask: {subtask['id']} - {subtask['description'][:50]}...")
                await self.run_coder(subtask)

                # Anthropic-recommended delay between sessions
                await asyncio.sleep(3)

            # Phase 3 & 4: QA Loop (review → fix → review until pass)
            qa_passed = False
            while not qa_passed:
                print("\n=== Phase 3: QA REVIEW ===")
                qa_result = await self.run_qa_reviewer()

                if qa_result["status"] == "pass":
                    qa_passed = True
                    print("✓ QA PASSED")
                else:
                    print(f"✗ QA FAILED: {len(qa_result['issues'])} issues")
                    print("\n=== Phase 4: QA FIX ===")
                    await self.run_qa_fixer(qa_result["issues"])
                    await asyncio.sleep(3)

            print("\n" + "="*60)
            print("ALL PHASES COMPLETE - Ready for merge!")
            print(f"Worktree: {self.worktree_dir}")
            print("="*60)

        except Exception as e:
            print(f"Error: {e}")
            # State is preserved in spec_dir for recovery
            raise

    # ========== HELPER METHODS ==========

    def _load_prompt(self, filename: str) -> str:
        return (self.project_dir / "prompts" / filename).read_text()

    def _build_coder_prompt(self, subtask: dict) -> str:
        return f"""
Implement this subtask:
ID: {subtask['id']}
Description: {subtask['description']}

Follow the implementation plan. Commit with message: "feat: {subtask['id']}"
"""

    def _build_fixer_prompt(self, issues: list) -> str:
        issues_text = "\n".join([f"- {i['description']}" for i in issues])
        return f"Fix these QA issues:\n{issues_text}"

    def _extract_and_save_plan(self, response):
        # Extract plan from response and save to implementation_plan.json
        pass  # Implementation depends on response format

    def _post_coder_processing(self, subtask: dict, response):
        # Update subtask status, record commits, sync memory
        state = self._load_state()
        for phase in state["phases"]:
            for st in phase["subtasks"]:
                if st["id"] == subtask["id"]:
                    st["status"] = "completed"
        self._save_state(state)

    def _process_qa_result(self, response) -> dict:
        # Parse QA response into structured result
        return {"status": "pass", "issues": []}  # Simplified

    def _verify_fixes(self, response):
        # Verify fixes were applied correctly
        pass


if __name__ == "__main__":
    import sys
    project_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    spec_name = sys.argv[2] if len(sys.argv) > 2 else "default"
    orchestrator = LongRunningOrchestrator(project_dir, spec_name)
    asyncio.run(orchestrator.run())
```

### Option C: Claude Code Hooks (Native)

```json
// .claude/settings.json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": {
          "tool_name": "Write",
          "file_pattern": "*.ts"
        },
        "command": "npm run lint --fix ${file}"
      }
    ],
    "Stop": [
      {
        "command": "python scripts/update_progress.py",
        "description": "Update progress tracking on session end"
      },
      {
        "command": "python scripts/determine_next_phase.py",
        "description": "Determine if review/QA needed"
      }
    ]
  }
}
```

---

## 5. Prompt Templates

### initializer_prompt.md

```markdown
# Initializer Agent Prompt

You are setting up a new project for long-running autonomous development.

## Your Task
1. Analyze the project specification in `app_spec.txt`
2. Create `feature_list.json` with 200+ granular features covering ALL functionality
3. Create `init.sh` script that sets up the development environment
4. Create `claude-progress.txt` with project overview
5. Initialize git repository with first commit

## Feature List Requirements
- Each feature must be independently testable
- Include verification steps that can be automated
- Categorize by: auth, data, ui, api, integration, security
- Prioritize: high, medium, low
- ALL features start with `"passes": false`

## Critical Rules
- Do NOT start implementing features
- Do NOT mark any features as passing
- Do NOT skip any functionality from the spec
- Be exhaustive - 200+ features minimum

## Output
When complete, confirm:
- Number of features created
- Categories covered
- Git commit hash
```

### coding_prompt.md

```markdown
# Coding Agent Prompt

You are continuing development on an autonomous coding project.

## Session Start Protocol
1. Run `pwd` to confirm working directory
2. Read `claude-progress.txt` for context from previous sessions
3. Read `feature_list.json` to see what's done and what's remaining
4. Run `git log --oneline -10` to see recent changes
5. Run `./init.sh` to start development environment
6. Verify fundamental features still working

## Development Rules
- Work on ONE feature only per session
- Select the highest-priority uncompleted feature
- Write clean, production-ready code
- Include appropriate error handling
- Write tests for your implementation
- Commit with descriptive message

## Testing Requirements
- Run tests before marking feature as passing
- Use Puppeteer MCP for UI verification when applicable
- Only mark `"passes": true` after verification

## Session End Protocol
1. Commit all changes with message: `feat: [feature description]`
2. Update `feature_list.json` - set `"passes": true` for completed feature
3. Update `claude-progress.txt` with:
   - What you accomplished
   - What should be done next
   - Any blockers or notes
4. Ensure working directory is clean (`git status`)

## Critical Rules
- NEVER mark a feature passing without verification
- NEVER remove or edit test descriptions in feature_list.json
- NEVER declare the project "complete" early
- NEVER leave uncommitted work at session end

## Context Management
Your context window will be automatically compacted. Do not stop work early due to token concerns. Save progress before context refreshes.
```

### review_prompt.md

```markdown
# Code Review Agent Prompt

You are a senior software engineer conducting a thorough code review.

## Your Task
1. Read `feature_list.json` to identify features marked `"passes": true` but `"reviewed": false`
2. Use `git diff` to see code changes for those features
3. Review against the checklist below
4. Write findings to `review_findings.json`
5. Update `feature_list.json` with `"reviewed": true` for approved features

## Review Checklist
1. **Correctness**: Does the code implement the feature correctly?
2. **Security**: Any injection, XSS, CSRF, or auth bypass vulnerabilities?
3. **Performance**: Any N+1 queries, memory leaks, or inefficiencies?
4. **Error Handling**: Are errors caught and handled appropriately?
5. **Testing**: Are there adequate unit and integration tests?
6. **Code Style**: Does it follow project conventions?

## Findings Format
Write to `review_findings.json`:
```json
{
  "findings": [{
    "severity": "high|medium|low",
    "file": "path/to/file",
    "line": 42,
    "issue": "Description",
    "suggestion": "How to fix"
  }]
}
```

## Critical Rules
- High severity findings BLOCK the feature from being marked reviewed
- Create tasks in claude-progress.txt for any fixes needed
- Be thorough but fair - false positives waste time
```

### qa_prompt.md

```markdown
# QA Testing Agent Prompt

You are a QA engineer verifying features work correctly end-to-end.

## Your Task
1. Read `feature_list.json` to identify features marked `"reviewed": true` but `"qa_verified": false`
2. For each feature, execute the verification steps
3. Use Puppeteer MCP for browser-based testing
4. Write results to `qa_results.json`
5. Update `feature_list.json` with `"qa_verified": true` for passing features

## Testing Approach
- Test as a real user would
- Follow the exact steps defined in each feature
- Take screenshots as evidence
- Document any unexpected behavior

## Results Format
Write to `qa_results.json`:
```json
{
  "results": [{
    "feature_id": 1,
    "status": "pass|fail",
    "evidence": "Description or screenshot path",
    "issues": []
  }]
}
```

## Critical Rules
- If a feature fails QA, set `"passes": false` in feature_list.json
- Document EXACTLY what failed and why
- A feature must pass ALL verification steps to be marked verified
```

---

## 6. Project Structure

```
my-project/
├── .claude/
│   ├── agents/
│   │   ├── code-reviewer.md
│   │   └── qa-tester.md
│   ├── settings.json          # Hooks configuration
│   └── CLAUDE.md              # Project context
├── prompts/
│   ├── initializer_prompt.md
│   ├── coding_prompt.md
│   ├── review_prompt.md
│   └── qa_prompt.md
├── scripts/
│   ├── orchestrator.sh        # OR orchestrator.py
│   ├── update_progress.py
│   └── determine_next_phase.py
├── qa_evidence/               # Screenshots from QA
├── feature_list.json          # Primary state (IMMUTABLE structure)
├── claude-progress.txt        # Session logs
├── review_findings.json       # Code review state
├── qa_results.json            # QA verification state
├── init.sh                    # Environment setup
├── app_spec.txt               # Project specification
└── [application code]
```

---

## 7. Key Principles (from Anthropic + Community)

### State Management
| Principle | Implementation |
|-----------|----------------|
| JSON over Markdown | Feature lists, review findings, QA results all in JSON |
| Git as checkpoint | Every feature = one commit, enables rollback |
| Immutable structure | Agents can only modify status fields, not descriptions |
| Strongly-worded instructions | "It is unacceptable to remove or edit tests" |

### Session Management
| Principle | Implementation |
|-----------|----------------|
| Fresh context preferred | Start new context over compaction when possible |
| Orientation protocol | pwd → progress → features → git log → init.sh |
| Single feature per session | Prevents premature completion |
| Clean state at end | All work committed, progress updated |

### Quality Gates
| Gate | Trigger | Action |
|------|---------|--------|
| Code Review | Every 5 passing features | Block if high-severity issues |
| QA Verification | Every 5 reviewed features | Regression = feature back to failing |
| Completion Check | After QA | Only complete when qa_verified == total |

### Failure Recovery
| Failure Mode | Prevention |
|--------------|------------|
| Declares victory early | 200+ feature list, completion check |
| Leaves buggy code | Review + QA phases mandatory |
| Corrupts state | JSON format, immutable structure |
| Loses context | Session logs, git history |

---

## 8. Implementation Checklist

### Phase 1: Setup
- [ ] Create `.claude/` directory structure
- [ ] Write agent definitions (code-reviewer.md, qa-tester.md)
- [ ] Create prompt templates (all four)
- [ ] Configure hooks in settings.json
- [ ] Create orchestrator script (shell or Python)
- [ ] Write CLAUDE.md with project context

### Phase 2: Initialization
- [ ] Create app_spec.txt with full requirements
- [ ] Run initializer agent
- [ ] Verify feature_list.json has 200+ features
- [ ] Verify init.sh works correctly
- [ ] Confirm git repository initialized

### Phase 3: Execution
- [ ] Start orchestrator loop
- [ ] Monitor progress in claude-progress.txt
- [ ] Check review_findings.json for issues
- [ ] Verify QA results in qa_results.json
- [ ] Handle any manual interventions

### Phase 4: Completion
- [ ] All features passing
- [ ] All features reviewed
- [ ] All features QA verified
- [ ] Final code review by human
- [ ] Merge to main branch

---

## 9. Tool Comparison Summary (Updated from Architecture Analysis)

### Agent Execution Methods

| Tool | Execution Method | Key Pattern |
|------|------------------|-------------|
| **Auto-Claude** | **Claude Agent SDK** (`create_client()`) | Only SDK-based framework |
| **claude-flow** | Claude Code Task tool | Swarm orchestration via subagents |
| **ralph-orchestrator** | Claude CLI via PTY | Hat-based pub/sub routing |
| **ralph-claude-code** | Claude CLI with `--continue` | Single-agent loop with circuit breaker |

### Detailed Comparison

| Tool | Best For | Agent Model | Memory System | Parallel Execution | Quality Gates |
|------|----------|-------------|---------------|-------------------|---------------|
| **Auto-Claude** | Full pipeline automation | Multi-agent (Planner→Coder→QA) | Graphiti semantic + file-based | Git worktrees + subagent spawning | 4-phase QA loop |
| **claude-flow** | Multi-agent swarms | 60+ specialized agents | HNSW vector search (150x-12,500x faster) | 15-agent hierarchical mesh | Hook-based (27 hooks) |
| **ralph-orchestrator** | Event-driven workflows | Hat-based personas | Markdown memories + JSONL events | Git worktrees with merge queue | Backpressure gates (tests/lint/build) |
| **ralph-claude-code** | Simple autonomous loops | Single agent per iteration | JSON state files | None (single agent) | Circuit breaker + rate limiting |
| **Shell Script** | Quick prototypes | Single CLI invocation | File-based state | None | Manual |
| **Claude Code Hooks** | Native integration | Built-in agents | Claude Code memory | Task tool parallelism | Hook-based |

### Key Architectural Patterns Discovered

**1. Git Worktree Isolation (Auto-Claude, ralph-orchestrator)**
```
main (protected)
  └── feature-branch
      └── .worktrees/feature/  ← Isolated working directory
```
- Prevents main branch corruption during autonomous work
- Enables parallel development on multiple features
- User explicitly merges only after verification

**2. Circuit Breaker Pattern (ralph-claude-code)**
```
CLOSED → Normal operation
  ↓ (3 loops with no progress)
OPEN → Stop execution
  ↓ (after cooldown)
HALF_OPEN → Probe with single loop
  ↓ (if successful)
CLOSED
```
- Prevents runaway loops and wasted API costs
- Detects stagnation via error repetition, output decline

**3. Dual-Condition Exit Gate (ralph-claude-code)**
```
Exit ONLY when:
  completion_indicators >= 2  AND  EXIT_SIGNAL == true
```
- Prevents false exits when agent says "done" casually
- Requires explicit agent confirmation of completion

**4. Semantic Memory (Auto-Claude with Graphiti)**
- Cross-session learning via knowledge graph
- Pattern discovery for similar future tasks
- File-based fallback for zero-dependency mode

### Recommendations by Use Case

| Use Case | Recommended Tool | Reason |
|----------|------------------|--------|
| **Production SDK integration** | Auto-Claude | Only one using actual Claude Agent SDK |
| **Complex multi-agent tasks** | claude-flow | 60+ agents, swarm topologies, consensus algorithms |
| **Event-driven Rust projects** | ralph-orchestrator | Hat-based routing, git worktrees, backpressure |
| **Simple autonomous loops** | ralph-claude-code | Lightweight bash, circuit breaker, session continuity |
| **Quick prototypes** | Shell Script + Claude CLI | Minimal setup, immediate results |
| **Native Claude Code** | Hooks + Task tool | Built-in, no external dependencies |

**Critical Insight:** Only **Auto-Claude** uses the Claude Agent SDK. All others use CLI invocation (with varying levels of sophistication).

### For Daily Coding Tasks (Recommended Stack)

| Complexity | Approach | Setup Time |
|------------|----------|------------|
| **Simple fix** | Direct `claude -p` | 0 min |
| **Single feature** | Shell script + JSON state | 10 min |
| **Multi-feature project** | Python orchestrator + worktrees | 30 min |
| **Full autonomous pipeline** | Auto-Claude (SDK) | 1+ hour |

**Start simple, graduate as needed.** Most daily tasks need only the shell script approach.

---

## 10. Production Patterns from Framework Analysis

Based on deep analysis of Auto-Claude (SDK-based) and ralph-orchestrator (CLI-based), here are the **essential patterns for daily coding tasks**:

### Pattern 1: Post-Session Python Bookkeeping (Critical)

**Don't rely on agents to update state.** Python handles bookkeeping after every session:

```python
# After EVERY agent session (100% reliable)
def post_session_processing(spec_dir, subtask_id, commit_before):
    # 1. Check what actually happened
    plan = load_json(spec_dir / "implementation_plan.json")
    subtask = find_subtask(plan, subtask_id)

    # 2. Track commits (did agent actually commit?)
    commit_after = run("git rev-parse HEAD")
    new_commits = commit_after != commit_before

    # 3. Record attempt for recovery
    record_attempt(subtask_id, success=subtask["status"] == "completed")

    # 4. Save good commit for rollback
    if new_commits and subtask["status"] == "completed":
        record_good_commit(commit_after, subtask_id)

    # 5. Extract insights from session (what worked, what failed)
    insights = extract_session_insights(spec_dir)
    save_to_memory(insights)
```

**Why this matters:** Agents sometimes claim success without committing, or update state incorrectly. Python verification catches this.

### Pattern 2: Git Worktree Isolation

**Never let agents touch main branch directly:**

```
main (protected)
└── feature/{task-name}     ← working branch
    └── .worktrees/{task}/  ← isolated directory
```

```bash
# Create isolated workspace
git worktree add -b feature/auth .worktrees/auth

# Agent works in isolation
cd .worktrees/auth
# ... agent does work ...

# User reviews and merges explicitly
git checkout main
git merge feature/auth
git worktree remove .worktrees/auth
```

**Benefits:**
- Main branch never corrupted by half-done work
- Easy rollback: just delete worktree
- Parallel tasks possible in separate worktrees

### Pattern 3: Recovery Manager

**Track attempts and enable recovery from failures:**

```python
# attempt_history.json
{
    "subtasks": {
        "auth-001": {
            "attempts": [
                {"session": 1, "success": false, "approach": "JWT tokens"},
                {"session": 2, "success": true, "approach": "Session cookies"}
            ]
        }
    }
}

# build_commits.json
{
    "commits": [
        {"hash": "abc123", "subtask_id": "auth-001", "session": 2}
    ],
    "last_good_commit": "abc123"
}
```

**Recovery logic:**
```python
def get_recovery_context(subtask_id):
    history = load_attempt_history()
    attempts = history["subtasks"].get(subtask_id, {}).get("attempts", [])

    if len(attempts) > 0:
        failed_approaches = [a["approach"] for a in attempts if not a["success"]]
        return f"Previous approaches that FAILED: {failed_approaches}. Try something different."
    return ""
```

### Pattern 4: Backpressure Gates (Quality Enforcement)

**Block progression until quality checks pass:**

```python
def validate_completion(output: str) -> bool:
    """Agent must prove tests/lint/build pass before marking done."""

    # Look for evidence in output
    tests_pass = "tests: pass" in output.lower()
    lint_pass = "lint: pass" in output.lower()

    if not (tests_pass and lint_pass):
        # Reject completion, force agent to fix
        return False
    return True

# In orchestrator loop
if agent_claims_done:
    if not validate_completion(output):
        # Synthesize "blocked" event instead of "done"
        next_prompt = "Completion rejected. Run tests and lint, fix issues, then try again."
```

### Pattern 5: Dual-Condition Exit Gate

**Prevent false completion (from ralph-claude-code):**

```python
def should_exit(completion_indicators: int, explicit_exit_signal: bool) -> bool:
    """
    Require BOTH conditions:
    1. Multiple completion indicators (agent said "done" multiple times)
    2. Explicit EXIT_SIGNAL (agent specifically confirmed completion)

    This prevents false exits when agent casually says "done" mid-task.
    """
    return completion_indicators >= 2 and explicit_exit_signal
```

### Pattern 6: Memory Injection (Minimal)

**File-based memory for cross-session context:**

```markdown
<!-- .agent/memories.md -->
# Session Memories

## Patterns
- Use barrel exports for clean imports
- Prefer async/await over callbacks

## Gotchas
- Auth middleware must run before route handlers
- Database connection pool max = 10

## Decisions
- Chose SQLite over PostgreSQL for simplicity
```

**Injection:**
```python
def build_prompt(base_prompt: str, memories_path: Path) -> str:
    if memories_path.exists():
        memories = memories_path.read_text()
        return f"## Context from Previous Sessions\n{memories}\n\n{base_prompt}"
    return base_prompt
```

### Pattern 7: Single Feature Per Session

**Prevent scope creep and premature completion:**

```python
# In coding prompt
CODING_PROMPT = """
## Critical Rules
- Work on ONE feature only: {feature_description}
- Do NOT start other features
- Do NOT declare project "complete"
- Commit this single feature when done
- Update progress file with what's next
"""
```

### Pattern 8: Task Thrashing Detection (from ralph-orchestrator)

**Detect when agent is stuck on same task:**

```python
task_block_counts = {}  # Track blocks per task

def check_thrashing(task_id: str, blocked: bool) -> bool:
    if blocked:
        task_block_counts[task_id] = task_block_counts.get(task_id, 0) + 1

        if task_block_counts[task_id] >= 3:
            # Task abandoned after 3 consecutive blocks
            return True  # Signal to skip or escalate
    else:
        task_block_counts[task_id] = 0  # Reset on success

    return False
```

### Pattern 9: Event-Based Workflow (from ralph-orchestrator)

**Use events instead of rigid phases:**

```xml
<!-- Agent outputs events in response -->
<event topic="build.done">tests: pass, lint: pass. Implemented auth module.</event>
<event topic="build.blocked">TypeScript errors in auth.ts line 42</event>
```

```python
# Orchestrator routes based on events
def process_output(output: str):
    events = parse_events(output)  # Extract <event> tags

    for event in events:
        if event.topic == "build.done":
            if validate_backpressure(event.payload):
                mark_subtask_complete()
            else:
                # Reject - force agent to fix
                next_prompt = "Completion rejected. Fix failing checks."

        elif event.topic == "build.blocked":
            record_block(current_task)
            if check_thrashing(current_task):
                escalate_to_human()
```

### Pattern 10: Markdown Memories (from ralph-orchestrator)

**Simple, human-readable memory format:**

```markdown
<!-- .agent/memories.md -->
# Memories

## Patterns
### mem-20250127-a1b2
> Use barrel exports for clean imports
<!-- tags: typescript, imports | created: 2025-01-27 -->

## Decisions
### mem-20250127-c3d4
> Chose async/await over callback chains for readability
<!-- tags: architecture | created: 2025-01-27 -->

## Fixes
### mem-20250127-e5f6
> Fixed race condition by adding mutex lock around shared state
<!-- tags: concurrency, bug | created: 2025-01-27 -->
```

**Benefits over JSON:**
- Human-readable and editable
- Git-friendly diffs
- Agent can append naturally
- Easy to review and curate

---

## 11. Minimal Production Workflow (Daily Use)

For daily coding tasks, use this **simplified 3-phase workflow**:

### Phase 1: PLAN (Once per task)
```bash
# Create task spec
claude -p "Read the requirements in task.md. Create implementation_plan.json
with subtasks. Each subtask should be independently testable."
```

### Phase 2: CODE (Loop until done)
```bash
#!/bin/bash
# simple_orchestrator.sh

while true; do
    # Get next subtask
    SUBTASK=$(jq -r '.subtasks[] | select(.status=="pending") | .id' implementation_plan.json | head -1)

    if [ -z "$SUBTASK" ]; then
        echo "All subtasks complete!"
        break
    fi

    # Record commit before
    COMMIT_BEFORE=$(git rev-parse HEAD)

    # Run coding session
    claude -p "Work on subtask: $SUBTASK. Run tests. Commit when done."

    # Post-session verification (the critical pattern)
    COMMIT_AFTER=$(git rev-parse HEAD)
    if [ "$COMMIT_BEFORE" != "$COMMIT_AFTER" ]; then
        # Agent made commits - verify tests pass
        if npm test; then
            jq ".subtasks[] | select(.id==\"$SUBTASK\") | .status = \"completed\"" \
                implementation_plan.json > tmp.json && mv tmp.json implementation_plan.json
        fi
    fi

    sleep 3
done
```

### Phase 3: REVIEW (After coding complete)
```bash
# Quick review of all changes
claude -p "Review the git diff since $START_COMMIT. Check for bugs, security
issues, and missing tests. Write findings to review.md."
```

---

## 12. Expected Outcomes

With this workflow properly implemented:

1. **Consistency**: Each session knows exactly what to do
2. **Quality**: Code review catches bugs before QA
3. **Verification**: QA confirms features work as intended
4. **Traceability**: Full history of what was done and when
5. **Recovery**: Git checkpoints enable rollback
6. **Completion**: Clear criteria for when project is done

**Timing Expectations (from Anthropic):**
- Initialization session: Several minutes (200 feature generation)
- Coding sessions: 5-15 minutes each
- Full application (200 features): Many hours across multiple sessions

---

## Conclusion

This workflow guarantees success for complex long-running loops by combining:

1. **Anthropic's two-agent pattern** (Initializer + Coding Agent)
2. **Extended review/QA phases** for quality assurance
3. **Structured state management** (JSON, not Markdown)
4. **Git-based checkpoints** for recovery
5. **Single-feature-per-session** discipline
6. **Strongly-worded instructions** preventing state corruption

The key insight is treating AI coding sessions like human engineering shifts: clear handoffs, documented progress, and systematic verification prevent the context loss that derails long-running autonomous work.

---

## References

- [Anthropic: Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Anthropic: Claude Code Best Practices](https://www.anthropic.com/engineering/claude-code-best-practices)
- [Anthropic: Building Agents with Claude Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)
- [Claude Code Documentation](https://code.claude.com/docs/en/)
- [Claude-Flow](https://github.com/ruvnet/claude-flow)
- [Auto-Claude](https://github.com/auto-claude/auto-claude)
- [Continuous Claude](https://github.com/AnandChowdhary/continuous-claude)

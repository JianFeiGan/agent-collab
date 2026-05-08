# AgentCollab — Twitter/X Posts

## 1. Announcement Tweet

```
Introducing AgentCollab — multi-agent orchestration for AI coding assistants.

Stop manually switching between Claude Code, Codex, and Aider. Define workflows in YAML, let them run in parallel.

✅ DAG-based scheduling
✅ File locking (no conflicts)
✅ Async execution

pip install agent-collab

github.com/user/agent-collab
```

## 2. Feature Highlight Tweet

```
Your AI coding agents shouldn't step on each other's toes.

AgentCollab adds file-level locking to multi-agent workflows:

🔒 Agent A writes backend/ → locked
🔒 Agent B writes frontend/ → runs in parallel
🔒 Agent C reviews both → waits for A & B

One YAML file. Zero conflicts.

github.com/user/agent-collab
```

## 3. Technical Deep-Dive Tweet

```
How AgentCollab schedules multi-agent workflows:

1. Parse YAML → Pydantic models (validates everything)
2. Build DAG → Kahn's algorithm for topological sort
3. Group into parallel levels (independent tasks batch together)
4. Execute with asyncio.Semaphore (bounded concurrency)
5. Lock files with fcntl (OS-level exclusivity)
6. Merge via git branches (--no-ff preserves history)

51 tests. Zero magic.

github.com/user/agent-collab
```

## 4. Comparison Tweet (vs Manual Agent Switching)

```
Before AgentCollab:
→ Write prompt for Claude Code
→ Copy output context
→ Switch to Codex
→ Paste context, write new prompt
→ Handle file conflicts manually
→ Merge outputs by hand
→ Repeat for every feature

After AgentCollab:
→ Write one YAML file
→ `agent-collab run workflow.yaml`
→ Get coffee

The difference is automation, not better prompting.
```

## 5. Call-to-Action Tweet

```
If you use multiple AI coding assistants (Claude Code, Codex, Aider), you need a way to make them work together.

AgentCollab is open-source (MIT), Python 3.11+, and ships with:
- 3 built-in agent adapters
- 51 passing tests
- Example workflows for fullstack apps, code review, and refactoring

Star it. Try it. PR welcome.

github.com/user/agent-collab
```

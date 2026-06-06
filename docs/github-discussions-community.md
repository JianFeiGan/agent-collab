# GitHub Discussions Community Setup

AgentCollab uses GitHub Discussions for open-ended community conversations that do not need the tighter triage workflow of GitHub Issues.

Repository: <https://github.com/JianFeiGan/agent-collab/discussions>

## Goals

- Help new users pick the right agent orchestration pattern.
- Collect workflow examples from real projects.
- Discuss roadmap items before they become implementation issues.
- Keep Issues focused on actionable bugs, tasks, and pull requests.

## Category Plan

| Category | Purpose | When to use | Maintainer action |
| --- | --- | --- | --- |
| Announcements | Release notes, roadmap updates, community milestones | Maintainers only | Pin important releases and link to CHANGELOG |
| Q&A | Usage questions, setup help, troubleshooting | User cannot tell whether behavior is a bug | Mark accepted answers and convert reproducible bugs to Issues |
| Ideas | Feature proposals and design discussions | Proposal needs validation before implementation | Summarize decisions and create an Issue when scope is clear |
| Show and Tell | Example workflows, demos, integrations | Community wants to share how they use AgentCollab | Label notable examples and link from docs/examples when useful |
| General | Community introductions and broad discussion | Topic does not fit another category | Redirect to better category when needed |

## Discussion Templates

Templates live in `.github/DISCUSSION_TEMPLATE/`:

- `question.yml` — troubleshooting and usage questions.
- `idea.yml` — feature proposals and design feedback.
- `show-and-tell.yml` — workflow examples and demos.

Each template asks for enough context to make discussions actionable while staying lighter than a formal bug report.

## Moderation Workflow

1. **Triage daily** during active development weeks.
2. **Answer or route** every new Q&A discussion:
   - answer directly when documentation is enough;
   - request reproduction details when behavior may be a bug;
   - convert to an Issue when there is a clear, actionable defect or task.
3. **Keep Ideas open** until there is a clear decision:
   - accepted ideas get a linked Issue or roadmap entry;
   - declined ideas receive a short rationale;
   - duplicates are linked to the canonical discussion.
4. **Promote Show and Tell posts** by linking good examples from README, docs, or example workflows.
5. **Close stale discussions** only after a maintainer response and at least 14 days without follow-up.

## Labels and Cross-Linking

Use Issues/PR labels for implementation tracking, not for open-ended discussion state. Recommended mapping:

| Discussion signal | Follow-up label when converted to Issue |
| --- | --- |
| Confirmed bug from Q&A | `bug` |
| Accepted feature proposal | `enhancement` |
| Documentation gap | `documentation` |
| Good first contribution opportunity | `good first issue` |
| Needs more design work | `needs discussion` |

When creating an Issue from a Discussion, include:

- original Discussion URL;
- concise problem statement;
- proposed acceptance criteria;
- affected docs/tests if known.

## Launch Checklist

- [x] Enable GitHub Discussions for the repository.
- [x] Add community setup documentation.
- [x] Add discussion starter templates.
- [x] Link Discussions from existing documentation where relevant.
- [ ] Pin an Announcements post for the first community welcome message.
- [ ] Review new discussions during the first week after launch.

## Welcome Post Draft

Title: `Welcome to AgentCollab Discussions`

```markdown
Welcome to the AgentCollab community!

AgentCollab helps Claude Code, Codex, Aider, and other AI coding tools collaborate safely through YAML workflows, scheduling, file locks, and merge orchestration.

Use Discussions for:
- setup and usage questions;
- workflow design help;
- feature ideas;
- sharing real-world examples.

If you found a reproducible bug, please open an Issue instead and include logs, workflow YAML, and AgentCollab version.
```

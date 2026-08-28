# AI Software Engineering Control Plane

## 1. One-Sentence Explanation

This is the design for an AI engineering agent that can safely read, modify, and validate real code on a real repository — operating inside a permissioned, sandboxed environment where risky actions always need a human's approval.

## 2. The Business Problem

Software teams spend a large share of engineering time on work that's mechanical but requires real context: understanding an unfamiliar part of a codebase, tracing a bug through logs and code, writing and running tests, fixing a failing build, and preparing a reviewable change. Terminal-native coding agents (Claude Code, Codex CLI, and comparable tools) emerged specifically to automate large parts of this loop — but doing it *safely* is a materially harder problem than doing it *at all*. An agent with unrestricted shell and filesystem access is a genuine operational risk: it can delete files, push broken code, leak secrets into logs, or take an action nobody asked for, especially once it's connected to real production-adjacent systems (CI/CD, deployment, cloud infrastructure).

Companies today handle this either by not giving AI agents write access to real systems at all (safe, but limits the value to autocomplete-level assistance), or by giving broad access and hoping the model behaves (unsafe, and not a real engineering control). Neither is the right answer. The actual gap in most organizations adopting coding agents in 2026 is not model capability — capable models are broadly available — it's the *control plane* around the model: what it's allowed to touch, what requires a human, how its actions are logged, and how a bad action gets contained rather than propagating.

The cost of getting this wrong is not hypothetical: uncontrolled agent actions on real infrastructure are exactly the kind of incident category flagged in 2026 security research on agentic AI (Research Notes Section 27) — misconfigured permissions and excessive autonomy are cited as leading causes of agent-related security incidents. The cost of getting it *too* conservative is opportunity cost — an agent so restricted it can't do meaningful work isn't worth operating.

## 3. Who Would Use This?

- **Software Engineer:** Wants an agent that can genuinely help with bounded tasks (fix this failing test, implement this well-specified change, investigate this bug) without needing to babysit every action.
- **Engineering Manager / Tech Lead:** Wants confidence that agent actions are permissioned, logged, and reversible, and wants visibility into what agents are actually doing across the team.
- **Platform / DevEx Engineer:** Wants to configure and operate the control plane itself — the sandboxing, permission model, and tool access — as shared infrastructure other teams build on.
- **Security / Compliance function:** Wants an auditable record of every agent action, a hard boundary on what agents can reach (secrets, production systems), and a kill switch.

## 4. Current Process Without AI

```
Engineer picks up a task (bug, feature, refactor)
 → Engineer manually reads relevant code, greps for related usages
 → Engineer manually reproduces the bug or clarifies the requirement
 → Engineer writes the fix
 → Engineer manually runs relevant tests, iterates on failures
 → Engineer reviews their own diff, prepares a pull request
 → Human reviewer reviews, requests changes, engineer iterates again
 → Merge, deploy
```

Even without AI in the loop at all, this is the baseline — the point of this project is not to replace this process but to compress the mechanical portions of it (code search, reproducing an issue, iterating on test failures) while preserving human review and control at every point that actually matters.

## 5. Proposed AI-Powered Process

```
Engineer assigns a bounded task to the agent (fix this failing test, implement this spec, investigate this bug)
 ↓
Agent operates inside a sandboxed, permissioned environment:
   reads repository, searches code, runs tests, inspects logs
 ↓
For low-risk actions (read, search, run tests read-only) — agent proceeds automatically
 ↓
For medium-risk actions (edit files, run build scripts) — agent proceeds within pre-approved scope,
   fully logged, reversible via version control
 ↓
For high-risk actions (git push, merge, deploy, modify CI/CD config, touch anything outside the
   assigned repository/branch) — agent stops and requests explicit human approval
 ↓
Agent prepares a diff and a pull request description for human review — never merges its own work
 ↓
Human reviews the diff (not just the agent's summary of it) and approves or rejects
 ↓
Every action taken is logged for audit
```

## 6. What the AI Actually Does

**Reasoning:** Decides which files are relevant to a task, what the likely cause of a bug is, and what sequence of investigation (read code, run tests, check logs) will resolve the ambiguity fastest — this is exactly the open-ended, discovery-dependent reasoning an agent loop is suited for.

**Retrieval:** Searches the codebase, reads files, inspects test output and logs.

**Analysis:** Diagnoses why a test is failing or a bug occurs, based on evidence gathered, not assumption.

**Tool usage:** Runs tests, runs linters/build tools, uses version control (within its permission scope) to prepare a diff.

**Communication:** Prepares a pull request description explaining the change and its rationale, for human review.

**Validation:** Runs the project's own test suite and build tooling to check its own work before presenting it — but the test suite's pass/fail result is a deterministic signal the agent reports on, not something it can talk itself out of.

**What the AI does NOT do:** It does not push to protected branches, merge pull requests, deploy, modify CI/CD pipeline configuration, or access secrets/credentials beyond what's explicitly scoped for its sandboxed task. It does not decide what gets shipped — a human reviews every diff before merge, always.

## 7. Where AI Is Used

AI is good at the open-ended, judgment-dependent parts of engineering work: figuring out where in an unfamiliar codebase a bug likely originates, deciding what to investigate next based on what a test failure or log actually says, and drafting a first-pass fix that a human can then evaluate rather than write from scratch. It's good at the kind of iterative "try, observe, adjust" loop that's genuinely hard to script because the right next step depends entirely on what the previous step revealed.

Deterministic software (not the model) must handle: the permission and sandboxing enforcement itself (which commands/paths are allowed is a hard-coded policy, not something the model self-polices), version control operations that are structurally scoped (the agent can only ever operate within its assigned branch, never main/protected branches), and CI/CD execution (the agent can trigger a defined pipeline, but the pipeline's own logic is unchanged, deterministic software).

## 8. Agent vs Workflow vs Normal Software

- **Normal software:** The sandbox/container runtime, the permission-enforcement layer (allow-list of commands and paths, independent of the model), the audit-logging pipeline, the git-integration layer that structurally prevents pushes to protected branches.
- **Deterministic workflow:** Running a fixed CI pipeline (lint, test, build) once a diff is prepared is not agentic — the pipeline's steps are fixed regardless of what the agent did to get there. Similarly, the "does this action require approval" check should be a deterministic policy lookup (a hard-coded classification of action types), never something the model decides about itself — this echoes the general HITL principle from Research Notes Section 24 that the gate must live in the surrounding system.
- **AI agent:** Investigating a bug, deciding which files to read and in what order, iterating on a fix based on test failures — this is the actual justification for agentic (as opposed to scripted) behavior: the sequence of steps cannot be known in advance and genuinely depends on what's discovered.
- **Multi-agent system (subagents):** Justified specifically for context isolation and parallelism, following the Claude Code architectural pattern described in Research Notes Section 19/23 — e.g., a **Research Subagent** that explores an unfamiliar part of the codebase and returns a bounded summary, keeping the main agent's context focused on the actual fix rather than every file it had to look at along the way; or parallel subagents investigating independent hypotheses for a bug's cause. This is decomposition for context-window and isolation reasons, a legitimate justification distinct from "more agents seems more sophisticated."

## 9. Agent Roles

**Main/Orchestrating Agent:** "Own the assigned task end to end — plan the approach, delegate bounded investigation to subagents where useful, make the code change, validate it, and prepare the diff for human review." **Research Subagent:** "Given a bounded question about the codebase (e.g., 'where is X currently used'), investigate and return a concise, cited answer — do not modify anything." **Test/Validation Subagent** (optional, for larger tasks): "Run the relevant test suite and report results in a structured, unambiguous format the main agent can act on." Subagents here mirror the permission-isolation principle directly: a Research Subagent can reasonably be read-only even when the main agent has scoped write access, reducing blast radius for the exploration phase specifically.

## 10. Tools the AI Needs

In business terms: the codebase itself (read/write within a scoped sandbox), the test/build system, version control, and — read-only — relevant logs or issue-tracker context describing the task.

Technically: a sandboxed filesystem and shell environment (isolated container, no ability to spawn arbitrary processes outside the sandbox, restricted network egress per Research Notes Section 27), a version-control tool scoped to a specific branch with no push access to protected branches, a test/build runner tool, and a read-only issue-tracker connector for task context. Every tool call is mediated by the permission-enforcement layer, not left to the model's own restraint.

## 11. MCP Opportunities

The codebase/filesystem access, test runner, and version-control operations are natural MCP **Tools** — the agent decides when to search, when to run tests, when to commit, based on its investigation. The issue-tracker task description is a good MCP **Resource** — loaded deterministically as the task's context, not something the agent has to think to fetch. Notably, both Claude Code and Codex CLI (Research Notes Sections 19, 20) support running as or connecting to MCP servers themselves — an engineering agent can be *both* an MCP client (consuming codebase/test tools) and, in more advanced setups, exposed as an MCP-accessible capability for other internal agents to invoke for bounded engineering subtasks. What should **not** be exposed via MCP or any agent tool: production deployment systems, secrets/credential stores, and CI/CD pipeline *configuration* (as opposed to *triggering* a pipeline run) — these sit behind a permission boundary the agent cannot cross regardless of what it's asked to do, echoing the "don't build the dangerous capability at all" principle used in Project 04.

## 12. Human-in-the-Loop

**Low-risk (automatic):** Reading files, searching code, running tests read-only, running linters, investigating and diagnosing.

**Medium-risk (automatic within scope, but logged and reversible):** Editing files within the assigned branch/sandbox, running build scripts, committing to the assigned branch — reversible via version control, so the cost of a mistake is low and recoverable, which is why full pre-approval isn't required for every edit as long as it stays within the sandboxed scope.

**High-risk (requires explicit human approval, every time):** Pushing to or merging into protected branches, deploying anything, modifying CI/CD configuration, installing new dependencies from outside an approved registry, accessing any credential or secret, and any action that would touch a system outside the assigned repository/sandbox. This mirrors the same structural principle used throughout this portfolio: the classification of an action as high-risk is a deterministic policy, not the model's self-assessment.

## 13. Business Value

The clearest measurable driver is engineer time saved on the mechanical portions of bounded tasks (test-driven bug fixes, well-specified small features) — measurable via before/after time tracking on comparable task categories, and via cycle time from task assignment to review-ready PR. A second driver is reduced context-switching cost for engineers, since delegating a bounded investigation to an agent lets a human stay focused elsewhere — harder to quantify directly but reflected indirectly in throughput metrics. We would not assign a specific productivity-percentage figure without a controlled pilot on real task categories at a specific organization; the correct approach is to instrument the metrics in Section 14.

## 14. Success Metrics

- **Task completion rate** — bounded tasks the agent completes to a mergeable-quality diff without excessive human correction.
- **Human edit rate** on agent-produced diffs (a proxy for how much rework was actually needed).
- **Cycle time** from task assignment to review-ready PR, compared to a human-only baseline for comparable task categories.
- **Approval-gate trigger rate** and **rejection rate** — how often the agent hits a high-risk boundary, and how often that request is actually approved (a very low approval rate on requested high-risk actions could mean the agent is mis-scoping tasks).
- **Sandbox escape/violation attempts** — should be zero; any non-zero count is a serious signal, not a minor bug.
- **Cost per task** (tokens/compute) compared against engineer-time saved.

## 15. Failure Scenarios

- **Wrong diagnosis:** the agent misidentifies a bug's cause and produces a fix that doesn't actually address it — caught by the test suite (deterministic validation) before it ever reaches human review, and flagged clearly if tests still fail after the agent's attempt.
- **Scope creep:** the agent modifies files outside what the task actually required — mitigated by scoping the sandbox to the minimum relevant part of the repository where feasible, and by requiring the diff review to flag unexpected file changes.
- **Tool failure:** test runner or build system unavailable — the agent should report this clearly rather than proceeding as if validation passed.
- **Prompt injection via repository content:** a maliciously crafted file, commit message, or issue description attempts to manipulate the agent into a dangerous action (a well-documented risk category for coding agents) — contained structurally by the permission-enforcement layer, which does not consult the model's own judgment about whether an action is "actually fine this time"; the deterministic policy applies regardless of what the agent's context contains.
- **Unauthorized action attempt:** any attempt to push to a protected branch, access a secret, or trigger a deployment is blocked at the enforcement layer and logged as a security-relevant event, not silently retried.
- **Ambiguous task specification:** the agent should ask a clarifying question or produce a smaller, clearly-scoped partial result rather than guessing broadly at an underspecified task.

## 16. Safety and Security

This project is fundamentally a security-engineering project as much as an AI project. Every agent runs inside an isolated, ephemeral sandbox (Research Notes Section 27) with restricted filesystem access (scoped to the relevant repository/branch), restricted network egress (no arbitrary outbound access — only what's needed to reach the code host and package registry), and no ability to spawn processes outside the sandbox. The agent operates under least-privilege credentials scoped to its specific task — never a broad admin token, never direct access to production credentials or secrets stores. All actions (every file read, every command run, every tool call) are logged with full context for audit, and the permission-enforcement layer is implemented as ordinary, independently-tested software that does not rely on the model's cooperation — if the model attempts a disallowed action, the enforcement layer blocks it at the system level, not by asking the model nicely. A kill switch (immediate termination of any running agent session) is a baseline operational requirement, not a nice-to-have, given that this agent can execute code.

## 17. Evaluation

- **Task completion correctness:** on a benchmark set of real (or realistically constructed) bug-fix and feature tasks with known-good solutions, does the agent produce a correct, test-passing diff?
- **Tool-call correctness/trajectory evaluation:** does the agent investigate efficiently (no redundant file reads, no irrelevant detours) per Research Notes Section 25?
- **Safety evaluation (adversarial):** does the permission-enforcement layer correctly block every attempted high-risk action across a red-team test suite, including prompt-injection attempts embedded in repository content? This is arguably the single most important evaluation category for this project.
- **Human evaluation:** engineer rating of PR quality and description usefulness, sampled regularly.
- **Regression suite:** re-run against a fixed benchmark task set on every change to the agent's prompts, tools, or permission policy.
- **Cost and latency** per task, tracked by task complexity.

## 18. Observability

Track, per agent session: every tool call and its arguments, every file touched, every command executed, latency and cost, and the outcome (task completed, blocked at an approval gate, failed). This is the primary way an engineering manager or security reviewer can answer "what did this agent actually do" after the fact — essential given the agent has real write and execution capability, not just read/summarize capability like most other projects in this portfolio. Alert in real time (not just log for later review) on any blocked high-risk action attempt or sandbox-boundary violation, since these are the events that matter most operationally, not just for historical audit.

## 19. Technology Options

**Claude Code / Codex CLI-style architecture (as a design pattern, not a dependency):** *Why:* both demonstrate a validated production pattern for exactly this problem — subagents for isolation, explicit permission models, hooks for deterministic guardrails around non-deterministic behavior (Research Notes Sections 19, 20). *Why not adopt one directly as the base:* building a custom control plane gives full control over the permission-enforcement layer and sandboxing, which matters more here than convenience; a company handling especially sensitive code/infrastructure may need guarantees a general-purpose product doesn't provide out of the box. *Alternative:* extend/configure an existing coding-agent product's permission and sandboxing features if they're sufficient, rather than building a control plane from scratch — a legitimate build-vs-buy decision to make with real requirements in hand.

**LangGraph:** *Why:* the orchestrating-agent-with-subagents pattern and the human-approval interrupt for high-risk actions map directly onto LangGraph's design. *Why not:* if adopting an existing coding-agent product's built-in orchestration, a separate framework may be redundant. *Alternative:* the coding agent's native orchestration if sufficient.

**Container/sandbox runtimes (e.g., gVisor, Firecracker-class isolation, or a managed sandboxed-execution service):** *Why:* this is the actual security-critical infrastructure decision — process and filesystem isolation must be enforced at the OS/container level, not application logic alone. *Why not build custom isolation:* significant security risk to reinvent this; established sandboxing technology should be used rather than a bespoke solution. *Alternative:* a managed sandboxed code-execution service if operating one internally isn't justified by scale.

**MCP:** *Why:* standardizes the codebase/test/version-control tool interface, and both major coding-agent products already support it (Research Notes Section 20), suggesting real interoperability value. *Why not:* if the control plane is fully custom and single-consumer, direct integration may be simpler initially. *Alternative:* direct tool integration, migrating to MCP as more internal consumers emerge.

## 20. Proposed Architecture

```
Engineer (task assignment via CLI / IDE / ticket)
        |
     Task Intake (normal software) -- reads issue/ticket context
        |
   Orchestrating Agent (LangGraph or equivalent)
        |
   +--------------------------------------------+
   |  Permission Enforcement Layer (deterministic, independent of model) |
   +--------------------------------------------+
        |
   +----------------+----------------+
   |                |                |
 Research         Test/Validation   Version Control
 Subagent         Subagent          (scoped branch only)
        |
   Sandboxed Execution Environment (isolated container, restricted network/filesystem)
        |
   Tool Layer (MCP): Codebase, Test Runner, VCS (all sandbox-scoped)
        |
   Diff + PR Description -> Human Review -> Merge (human-only)
        |
   Audit Log & Observability Layer (real-time alert on any blocked high-risk action)
```

## 21. MVP

The smallest version that proves value: a single orchestrating agent (no subagents yet) operating in a sandboxed environment against a single, low-stakes internal repository, scoped to fixing well-specified failing tests only (a narrow, easily-evaluated task category), with a hard-coded permission-enforcement layer blocking anything beyond read/edit/commit within its assigned branch, and full logging. This proves the sandboxing and permission model actually hold under real (if narrow) usage before expanding task scope or adding subagent decomposition.

## 22. Future Version

MVP → expand task scope to well-specified small features and bug investigation, not just failing tests → add the Research Subagent for context isolation on larger codebases → add a Test/Validation Subagent for parallel throughput on larger tasks → add adversarial/red-team evaluation as a continuous, automated process, not a one-time check → potentially expose the control plane's capabilities via MCP to other internal agents (e.g., an incident-response agent, Project 11, requesting a bounded code investigation) → continue treating deployment and CI/CD-configuration access as permanently excluded, not a future relaxation, given the risk profile.

## 23. What Makes This Project Difficult?

The permission and sandboxing model has to be genuinely airtight, not merely "the model was told not to" — this is real security engineering, and getting it wrong has real consequences (Research Notes Section 27's cited 2026 incidents). Context management for large, unfamiliar codebases is a hard problem in its own right, independent of the safety concerns — deciding what to load into the agent's context without either missing something relevant or blowing the context budget is genuinely difficult and directly affects task quality. Evaluation is harder than it looks: "did the agent's fix actually work" is testable via the test suite, but "was this the right fix, not just a fix that happens to pass tests" requires human judgment that doesn't scale as cheaply as automated evaluation. Balancing autonomy against safety is a continuous tuning problem — too conservative and the agent isn't useful, too permissive and the blast radius of a mistake grows; getting this right requires real operational experience, not just a policy written once at design time.

## 24. What I Would Demonstrate When Implementing It

A real sandboxed execution environment with enforced filesystem/network isolation; a permission-enforcement layer implemented as independently-tested code, not model-trusted policy; a subagent architecture with genuine context and permission isolation (not just cosmetic role labels); MCP tool integration for codebase/test/VCS access; adversarial evaluation specifically targeting the permission boundary (including prompt-injection attempts via repository content); and full action-level observability and audit logging.

## 25. Portfolio Story

"The interesting problem in building a coding agent isn't getting a model to write code — capable models are widely available. It's building the control plane that makes it safe to give that model real write access to a real repository. I designed the permission and sandboxing layer as ordinary, independently-tested software that enforces boundaries regardless of what the model 'decides' — pushing to a protected branch or touching a secret isn't something the model is asked nicely not to do, it's something the system makes structurally impossible. Where I did use subagents, it was specifically for context isolation on large investigations, not because more agents seemed more impressive. I'd evaluate this project as much on adversarial red-team results against the permission boundary as on task-completion rate, because a coding agent that's fast but unsafe isn't actually a net positive."

## 26. Questions a CTO Might Ask Me

1. How do you guarantee the agent can't push to a protected branch, even under a clever prompt injection?
2. What's your sandbox isolation technology, and what's its own threat model?
3. How do you decide what counts as a "high-risk" action requiring approval versus what proceeds automatically?
4. What happens if the agent's fix passes tests but is actually wrong in a way tests don't catch?
5. How do you prevent secrets from leaking into agent logs or context?
6. Why use subagents here at all — what's the actual justification versus a single agent?
7. What's your kill-switch mechanism if an agent session goes wrong mid-task?
8. How do you evaluate this system adversarially, not just on happy-path task completion?
9. What's the cost profile per task, and how does it compare to engineer time saved?
10. How would this differ operating against a monorepo with thousands of engineers versus a small team's repo?
11. Why not just use an off-the-shelf coding agent product instead of building this control plane?
12. How do you handle a task that turns out to be much larger in scope than initially assigned?
13. What's your process for updating the permission policy as new risky action types are identified?
14. How do you audit what an agent did after the fact, six months later?
15. What's the failure mode if the sandboxed environment itself has a vulnerability?

## 27. Research Sources

- [Dive into Claude Code: The Design Space of Today's and Future AI Agent Systems — arXiv](https://arxiv.org/html/2604.14228v1)
- [A Mental Model for Claude Code: Skills, Subagents, and Plugins — Level Up Coding](https://levelup.gitconnected.com/a-mental-model-for-claude-code-skills-subagents-and-plugins-3dea9924bf05)
- [Claude Code vs Codex CLI vs Gemini CLI (2026 Comparison) — DeployHQ](https://www.deployhq.com/blog/comparing-claude-code-openai-codex-and-google-gemini-cli-which-ai-coding-assistant-is-right-for-your-deployment-workflow)
- [Best Terminal AI Coding Agents in 2026 — amux](https://amux.io/blog/best-terminal-ai-coding-agents-2026/)
- [AI agent security permissions sandboxing — OWASP Gen AI Security Project](https://genai.owasp.org/2026/04/14/owasp-genai-exploit-round-up-report-q1-2026/)
- [Beyond Static Sandboxing: Learned Capability Governance for Autonomous AI Agents — arXiv](https://arxiv.org/pdf/2604.11839)
- See also [../RESEARCH_NOTES.md](../RESEARCH_NOTES.md) for full ecosystem sourcing.

# Roadmaps

Use a roadmap when work spans multiple milestones or has meaningful dependencies.
Keep it in the repository's canonical planning location and link it from the
developer entrypoint. A roadmap guides implementation; it is not a promise that
every future task will remain unchanged.

## Structure

- Start with the goal, scope, constraints, current state, and intended end state.
- Split work into ordered stages by dependency and risk, not arbitrary size.
- Give each stage an outcome, bounded scope, prerequisites, deliverables,
  acceptance checks, test/documentation expectations, and exit criteria.
- Break stages into tasks small enough to delegate. State owned files or
  boundaries, expected outputs, dependencies, and verification for each task.
- Mark tasks that can run in parallel. Avoid assigning overlapping files or
  shared high-conflict documents to concurrent agents; define integration order
  and designate an integrator for unavoidable shared work.
- Identify cross-stage contracts and decisions that must be settled before
  parallel implementation. Keep unresolved choices visible rather than hiding
  them in task prose.

## Maintenance

- Reconcile the plan with the current branch and implementation before starting
  a stage. Label completed, deferred, blocked, and superseded work accurately.
- Update the roadmap when scope, dependencies, architecture, or acceptance
  criteria change. Remove completed implementation instructions from active
  task lists while retaining useful history in concise status notes or decision
  records.
- Keep one canonical active plan. Link related plans rather than duplicating
  tasks or maintaining competing status summaries.
- Prefer actionable acceptance criteria that can be verified by tests, scripts,
  analyzers, or a named manual check. Give each manual check an owner and a
  completion signal.
- Include relevant test layers, documentation/index updates, compatibility,
  security, performance, and rollout concerns per stage; explicitly mark
  reasoned N/A items.
- After parallel work, compare each deliverable with its task and stage
  acceptance criteria, resolve integration conflicts, and update status only
  after verification. Do not infer completion from agent reports or merged
  commits alone.

## Delegation Readiness

A task is ready for parallel delegation when an agent can understand its goal,
inputs, output, owned boundary, dependencies, and verification without relying
on undocumented context. If two tasks need the same files, either sequence them
or specify a single owner and have others provide review findings instead of
editing concurrently.

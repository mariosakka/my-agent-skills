---
name: lab-creation
description: >-
  Create or complete educational laboratory exercises from an assignment,
  lecture material, or existing course repository, with runnable work and
  reproducible explanations appropriate to the requested deliverables.
---

# Lab Creation

Use this skill for coursework labs and practical exercises. Adapt to the subject,
assignment, course rules, and existing repository; a lab need not be Python,
a notebook, or an AI exercise. Respect the user's requested depth and deliverables.

## Course Repository

For a new course repository, use the name provided by the user; ask for it when
needed instead of prescribing one. When remote creation is requested, default
to public visibility unless the user requests otherwise. Before publishing,
inspect the actual files and history for personal data, secrets, private course
materials, and content that cannot be published; resolve any uncertainty with
the user. Never make an existing private repository public without explicit
authorization.

Use the reference repos' GitHub description format when the details are known:
`<Course> Lab Solutions - <Institution / Program> - Year <year> Sem <semester>`.
Ask for missing details when they are needed; do not invent them. In the root
README, identify the course and list each lab's number, topic, and folder.

Organize a new course repository into root-level `lab-1/`, `lab-2/`, and so on,
with each lab's inputs, work, and requested explanations under its own folder.
Use the existing layout when working in an established repository; do not
renumber or relocate user work without a request. Put genuinely shared course
resources and environment configuration at the root where appropriate.

For a new repository, add a lightweight Git hook (or the repository's existing
hook mechanism) that checks whether adding a `lab-N/` requires updates to the
root lab index, shared environment, or other maintained lab manifests. Make
the check actionable and provide a documented bypass for cases where it is not
applicable or hooks cannot run; CI or a manual command should remain available
when the check is required. Do not silently rewrite files or block unrelated
changes.

Provide a small, reusable set of tools for recurring course-repository tasks,
such as creating/indexing a lab, validating required files, or checking shared
environment consistency when those tasks recur. Index each tool with its
purpose, prerequisites, and exact invocation in the root README or canonical
development guide. While adding labs, actively look for repeated manual
updates to indexes, environment files, manifests, tests, and release/submission
steps that can be made deterministic; automate them when useful. Prefer
extending an existing hook, task runner, or script. Do not create placeholder
tools or a general framework for a one-off lab.

## Understand The Assignment

1. Inspect the supplied assignment, datasets, templates, and relevant course
   repository instructions before editing. Identify each required task,
   inputs, outputs, constraints, submission format, and assessment criteria.
2. Preserve supplied source files and existing work. Distinguish teacher
   examples, starter code, user edits, and your own calculations; do not invent
   missing requirements, data, observations, citations, or execution results.
   Ask when missing information prevents a correct solution.
3. Honor course restrictions and the requested level of assistance. If asked
   for hints or an incomplete exercise, do not silently supply a full solution.

## Build The Lab

- Follow the course repository's established layout and numbering. If none
  exists, use a clearly named lab folder and a brief course-level index; keep
  original inputs separate from generated results.
- Use the assignment's required language and tools. Make setup reproducible
  through the ecosystem's standard configuration and lockfiles, build tooling,
  or a container when appropriate; document prerequisites, versions, setup,
  execution, and any external services or data. This can be Conda, a language
  toolchain such as Java, Docker, or another suitable approach. Reuse the
  course's shared environment and add packages only when needed. Do not replace
  or prune a user's environment without authorization. On Windows, use
  `conda run` or an activated environment when direct execution would miss
  native-library paths.
- Keep reusable computation separate from presentation where that removes
  actual duplication. Functions should return results; notebooks or scripts
  may display, plot, and explain them. Avoid creating a framework for one lab.
- Preserve units, assumptions, formulas, data provenance, and edge cases.
  Explain what results mean and when they are invalid; distinguish a computed
  result from an expectation or hypothesis. Protect personal or licensed data.
- Produce only requested artifacts. When runnable notebooks are appropriate,
  keep cells ordered and reproducible, use portable paths, and avoid embedding
  secrets or large private datasets. Use the existing `explanation-notebooks`
  skill if available and teaching notebooks or visual explanations are requested;
  otherwise follow the assignment and repository conventions directly. Do not
  force a PDF, companion document, or multiple versions on every lab.
- Maintain a `.gitignore` suited to the actual language and tools: exclude
  secrets, personal configuration and data, local environments, caches, and
  reproducible build output while keeping source, dependency specifications,
  needed fixtures, and explicitly requested deliverables trackable. Review
  notebook outputs and generated files for sensitive content. Ignore rules do
  not remove tracked files or secrets already in history; inspect Git's staged
  changes and history as appropriate, and never delete or untrack user data
  without authorization.

## Verify And Hand Off

Map each requirement to its implementation and evidence. Run relevant scripts,
tests, and notebook cells in the intended environment where feasible; use small
checks for non-trivial computations and compare results with known examples or
independent calculations when available. Execute notebooks on a copy or into a
temporary output unless changing stored outputs is explicitly intended.

Report the commands run, results, assumptions, unmet requirements, and anything
not executed. Keep generated artifacts only when requested or required by the
repository. Do not publish or commit personal data, private assignment material,
or outputs without confirming they are appropriate for that repository.

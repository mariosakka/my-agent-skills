---
name: explain-syntax
description: Use when explaining any framework syntax, API, or language feature to someone learning it — especially when they already know another language or framework.
---

# Explaining Syntax

## Core principle

Never explain syntax in isolation. Always anchor it to something the learner already knows. A concept lands when the reader thinks "oh, that's just like X" — then you add what's different.

## The explanation order

For every concept, follow this sequence:

1. **What it is** — one plain sentence. No jargon.
2. **Analogy** — map it to something they already know (Java, React, OOP pattern, everyday concept).
3. **What's different** — where the analogy breaks down or where this version goes further.
4. **Code** — minimal, annotated example showing the concept in action.
5. **Gotcha** (if any) — one callout for the non-obvious trap beginners hit.

## Analogy sources — use all that apply

| If learner knows… | Map to… |
|---|---|
| Java / Spring | `@Annotations`, beans, `ApplicationContext`, `@PostConstruct`, `@PreDestroy`, `HandlerInterceptor`, `@Service`, Bean Validation (`@NotNull`, `@Pattern`) |
| React | `useState`, `useEffect`, `useRef`, `useMemo`, props, callback props, `React.lazy()`, `useParams()`, `useNavigate()`, `<Outlet />`, Context/Provider |
| OOP / GoF patterns | Observer, Decorator, Builder, Strategy, Chain of Responsibility, Facade, Null Object, Singleton, Factory |
| General programming | Event listeners, callbacks, streams, pipelines, middleware, dependency injection |

## Comparison tables

Use a table whenever you are explaining a concept that has a direct parallel in another framework. Three columns is the sweet spot: `This framework | React | Java`.

```
| Angular          | React              | Java / Spring         |
|------------------|--------------------|-----------------------|
| signal()         | useState()         | field + setter        |
| ngOnInit()       | useEffect(fn, [])  | @PostConstruct        |
| @Injectable      | —                  | @Service              |
| canActivate guard| <ProtectedRoute>   | HandlerInterceptor    |
```

Tables let the learner scan, not read. Always prefer them over prose for parallel comparisons.

## Design pattern callouts

When a concept implements a GoF pattern, say so explicitly. Use a callout:

> **Design pattern — Observer:** signals notify the template automatically when state changes — no manual diffing required.

Name the pattern, name the concept, name the benefit. Three parts, one sentence.

## Code annotation style

Annotate inline with `// = equivalent in React` or `// = @PostConstruct in Spring`:

```typescript
ngOnInit(): void { this.load(); }   // = useEffect(() => {}, [])
readonly destroyRef = inject(DestroyRef);  // = @PreDestroy hook
readonly title = input<string>();   // = prop in React
```

This ties code to the analogy without breaking flow.

## What to avoid

- **Don't explain what well-named code already says.** `signal(false)` does not need "this creates a signal with initial value false."
- **Don't use analogies that don't hold.** State where the comparison breaks down before the reader hits the wall themselves.
- **Don't pile multiple new concepts in one example.** Introduce one thing at a time; use `...` or comments to stub the rest.
- **Don't skip the "what's different" step.** Analogies that are 100% identical don't exist — the delta is often the most important thing to learn.
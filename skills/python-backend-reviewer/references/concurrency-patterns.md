# Concurrency Patterns Reference

Common fixes for shared state mutation in async Python code.

## The Core Problem

When async methods mutate `self.attr`, concurrent requests can corrupt state:

```python
# Before: Mutating shared instance state
class Workflow:
    async def run(self, task):
        self.current_task = task  # Race condition!
```

## Fix: Request-Scoped State

```python
# After: Request-scoped state
class Workflow:
    async def run(self, task):
        execution = ExecutionContext(task=task)
        return await self._execute(execution)
```

## Alternative Patterns

1. **Pass state through parameters** (preferred) -- avoids shared mutation entirely
2. **Use `contextvars`** for request-scoped data that needs to flow through call stacks
3. **Use `asyncio.Lock`** for truly shared state that must be synchronized
4. **Create new instances per request** -- avoids sharing at the object level

## When to Apply

- **Critical**: Any `self.x = y` assignment inside an `async def` method where the instance is shared across concurrent requests
- **Warning**: Any `self.attr` mutation in async context -- may be safe if the instance is request-scoped
- **Acceptable**: Module-level mutable objects that are initialized once and never mutated after startup

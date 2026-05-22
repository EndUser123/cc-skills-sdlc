# Failure-Mode Checklist

Run this checklist internally before synthesizing a critique. Surface questions to the user only when blocked.

- What is the most plausible way this target still fails even if the happy path passes?
- What am I treating as safe because the producer succeeds, even though the consumer could still fail?
- What hidden assumption would most likely break under stale data, workflow interruption, compaction, resume, or multi-terminal use?
- What recommendation becomes dangerous if it is low-reversibility or applied out of order?
- What evidence is missing that would meaningfully downgrade or overturn a high-severity finding?
- What blind spot is shared across multiple specialists or review passes rather than isolated to one agent?
- What risk am I underweighting because it is operational, temporal, or only appears during live use?
- What recommendation is really architecture work, not a local patch?
- What would a faster or more literal model fail to challenge in this critique?
- What change here reduces one failure mode but creates a new one elsewhere?
- Do we have predictable issues in primary code and related code, dependent files, supporting scripts, configs, docs, tests, or runtime state?
- Does this target's dependency chain extend beyond what was reviewed?
- What could break if recommendations are applied at the wrong scope?
- Is the target in a valid critiqueable state, or is it mid-edit, stale, unverified, or disconnected from the active source of truth?
- Is this the right priority, or are we optimizing something that does not affect the outcome?

## Mandatory Data-Safety Addendum

For cleanup, deletion, migration, live-run, auth, credential, or external-service work, also ask:

- What names, IDs, paths, profiles, accounts, or namespaces are safe to touch?
- What names, IDs, paths, profiles, accounts, or namespaces must not be touched?
- Does failure to list, parse, authenticate, or validate fail closed?
- Can a stale state file cause the wrong target to be modified or deleted?
- Does post-run cleanup preserve the original failure context if cleanup also fails?
- Is there an audit trail for what changed?

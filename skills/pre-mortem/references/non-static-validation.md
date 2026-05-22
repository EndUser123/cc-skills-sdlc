# Non-Static Validation

Non-static validation exercises the installed environment or runtime behavior. It is useful when static checks cannot prove the system a user will actually run.

## Default Boundary

Non-static validation must be explicit about:

- command or action;
- expected signal;
- state mutation risk;
- external service or credential risk;
- cleanup or rollback;
- whether the result is comparable with prior runs.

Do not run probes that mutate user-visible resources, contact authenticated services, consume quota, or start live work unless the user explicitly authorized that class of action.

## Recommended Local Live Checks

For this pre-mortem package, the safe local live checks are:

- verify the Codex installed adapter exists and all package-owned reference paths resolve;
- import `premortem_io.py`, create a temporary session root, write a work file, create the specialists directory, verify path containment, and delete the temporary root;
- run `claude plugin validate P:\packages\cc-skills-sdlc`;
- run `claude plugin details cc-skills-sdlc@local` and verify `pre-mortem` plus all package-owned adversarial agents are visible;
- verify the Claude plugin cache contains the current package version and pre-mortem files after `claude plugin update`;
- report when Claude says restart is required.

## Unsafe Or Higher-Risk Checks

These require separate explicit permission:

- invoking NotebookLM, authenticated CLIs, or external APIs;
- starting benchmarks, live downloads, or worker lanes;
- creating or deleting notebooks, browser profiles, caches, or remote resources;
- dispatching long-running specialist teams when the user requested only static review.

## Reporting

Every pre-mortem should say whether non-static validation was:

- run and passed;
- run and failed;
- not run because it was outside permission;
- recommended next, with exact command and reason.

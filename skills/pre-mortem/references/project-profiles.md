# Project Profiles

Project profiles make pre-mortems domain-aware without forking the generic skill.

## Discovery Order

Load the first existing profile from the active repository:

1. `docs/operations/pre-mortem-profile.md`
2. `docs/pre-mortem-profile.md`
3. `.codex/pre-mortem-profile.md`
4. `.claude/pre-mortem-profile.md`

If multiple profiles exist, prefer the most specific operational profile and mention the others as possible secondary context.

## Required Profile Content

A useful project profile should define:

- domain-specific failure modes;
- safe and unsafe resource scopes;
- live-run or destructive-operation preflight requirements;
- historical regressions to check before declaring readiness;
- project-specific static checks;
- project-specific non-static probes;
- metrics that make a run valid or invalid;
- stop/go criteria.

## Use In Output

The pre-mortem final output must state:

- profile path used, or `none found`;
- profile-specific risks applied;
- profile-specific risks not applicable;
- missing profile sections that would materially improve readiness.

# Modernization Detection (EXPLORE Phase)

Modernization detection is an always-on library version analysis during the EXPLORE phase.

## Workflow

### Step 1: Library Scanning (`utils.library_scanner`)
- Detect Python imports via AST (imports `ImportScanner`)
- Parse requirements.txt and pyproject.toml (uses `DependencyFileParser`)
- Returns unified library list with versions (uses `LibraryDetector`)
- Graceful handling: Missing files -> empty list (no error)

### Step 2: Context7 Integration (`utils.context7_client`)
- Resolve library names to Context7 IDs (uses `Context7Resolver`)
- Query breaking changes from changelogs (uses `BreakingChangeDetector`)
- Rate limit handling with exponential backoff
- Result caching to avoid duplicate queries

### Step 3: Priority Scoring (`utils.priority_scorer`)
- Categorize findings: P0 (critical), P1 (high), P2 (low)
- Calculate confidence score (0.0-1.0) based on evidence
- **Important**: Priorities are RECOMMENDATIONS, never blocks

### Step 4: Rate Limit Coordination (`utils.context7_rate_limiter`)
- Shared rate limit tracking across Track 1, Track 2, EXPLORE
- Batch query optimization to reduce API calls
- Graceful fallback to local version checking
- Never blocks EXPLORE phase (always returns results)

### Step 5: Plan Enhancement (`utils.modernization_section_generator`)
- Generate "Modernization Considerations" section for plan.md
- Format: Detected Divergences (P0/P1/P2), Recommendation, Your Choice
- Integration points: Adds after Section 7 of plan.md template

### Step 6: User Opt-Out (`utils.user_optout_handler`)
- Detect opt-out checkbox in plan.md: "- [x] Skip modernization detection"
- Persist preference to `.claude/modernization_optout.json`
- EXPLORE phase continues normally when opted out

## Error Handling

- Context7 unavailable -> Skip modernization, continue EXPLORE
- Rate limit exceeded -> Use fallback (local version checking)
- No dependencies -> Skip modernization (pure stdlib/non-Python)
- User opt-out -> Respect choice, don't show modernization section

## Integration Points

- Called automatically during EXPLORE phase (no user action required)
- Results appended to plan.md before PLAN phase begins
- Existing plan.md -> Modernization section added if not present
- No plan.md -> Modernization findings included in generated plan

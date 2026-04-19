---
name: harden
version: "1.0.0"
status: "stable"
description: Harden function with guards + logging for defensive programming
category: defensive
triggers:
  - /harden
aliases:
  - /harden
suggest:
  - /debug
execution:
  directive: |
    1. Read the target function to understand its parameters and control flow
    2. Add assertion guards at function entry (parameter validation)
    3. Add debug_log() calls at key decision points
    4. Add logging for guard failures (try/except around assertions)
    5. Import debug_log if needed: from ..hooks.tdd_core import debug_log
  examples:
    - "/harden process_videos"
    - "/harden fetch_channel_videos --file=metadata_backfill_api.py"
---

# /harden

**Purpose:** Harden functions with defensive guards and debug logging

## EXECUTE

### Step 1: Read the target function

Identify:
- All parameters and their types
- Expected value ranges (positive, non-negative, specific lengths)
- Decision points (conditionals, loops, early returns)
- Error handling paths

**Example invocation:**
```
/harden process_videos
```

**With file flag:**
```
/harden fetch_channel_videos --file=metadata_backfill_api.py
```

### Step 2: Add assertion guards at function entry

Place guards immediately after function signature, before any logic:

```python
def process_videos(videos, estimated_total):
    # Parameter validation
    assert videos is not None, "videos cannot be None"
    assert isinstance(videos, list), f"videos must be list, got {type(videos)}"
    assert estimated_total > 0, f"estimated_total must be positive, got {estimated_total}"

    # Function logic continues...
```

**Guard types:**
- None/empty checks
- Type constraints
- Value ranges (positive, non-negative, etc.)
- Length constraints

### Step 3: Add debug_log() calls at decision points

```python
debug_log(f"process_videos: videos_count={len(videos)}, estimated_total={estimated_total}")

if not videos:
    debug_log(f"process_videos: empty_videos - returning")
    return []

for video in videos:
    debug_log(f"process_videos: processing video_id={video.get('video_id')}")
```

**Log at:**
- Function entry (parameters received)
- Before conditional branches
- Loop iterations (key progress points)
- Early returns or breaks
- Error paths

### Step 4: Add guard failure logging

Wrap assertions with logging for better debugging:

```python
# Parameter validation with logging
if videos is None:
    debug_log(f"process_videos: guard_failure - videos is None")
    assert False, "videos cannot be None"

if not isinstance(videos, list):
    debug_log(f"process_videos: guard_failure - wrong_type videos={type(videos)}")
    assert False, f"videos must be list, got {type(videos)}"
```

### Step 5: Complexity check (inline)

After hardening, run quick complexity check:

```bash
radon cc <file> -a -s
```

## When to use

- Function receives external/untrusted input
- Need to enforce preconditions
- Defensive programming for public APIs
- After bug caused by invalid input
- Investigating issues with unclear control flow

## Integration

After hardening, the system will suggest:
- **`/debug`** - Full debug workflow if issues persist

## Verification

After hardening:

1. Run tests to ensure guards don't break valid inputs
2. Test with invalid inputs to verify guards trigger
3. Check debug_log output shows proper context
4. Verify complexity hasn't increased significantly

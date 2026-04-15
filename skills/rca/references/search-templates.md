# Multi-Angle Search Templates by Symptom Type

**Select the template matching your symptom type and run ALL search angles.**

## Template 1: PERFORMANCE (slow/flashing/timeouts/high CPU)

**Symptoms:** "It's slow", "flashing UI", "takes too long", "timeout", "high CPU/memory"

1. **Mechanism Search** (How is it implemented?)
   ```bash
   grep -r "Progress\(" "src/"           # Rich Progress contexts
   grep -r "update\(" "src/"             # State updates
   grep -r "render|draw|paint" "src/"    # Rendering operations
   ```

2. **Functional Search** (What produces visible symptom?)
   ```bash
   grep -r "yt-api:" "src/"              # VISIBLE: "yt-api: 54%" output
   grep -r "status.*:" "src/"             # Progress bars, counters
   grep -r "console.log|print(" "src/"   # Console output
   ```

3. **Temporal Search** (What changed recently?)
   ```bash
   git log --since='7d' --oneline        # Recent commits
   git diff HEAD~5 --stat                 # File changes
   ```

4. **Contextual Search** (What calls it?)
   ```bash
   grep -r "import.*Progress" "src/"     # Where Progress imported
   grep -r "Progress(" "src/" | head -20  # Usage sites
   ```

---

## Template 2: ERROR (exceptions/crashes/AttributeError)

**Symptoms:** "AttributeError", "KeyError", "TypeError", "NoneType has no attribute", crash

1. **Mechanism Search** (Where is it raised?)
   ```bash
   grep -r "raise AttributeError" "src/"   # Where raised
   grep -r "class.*Error" "src/"          # Exception definitions
   grep -r "except.*:" "src/"              # Exception handlers
   ```

2. **Functional Search** (Where is it displayed?)
   ```bash
   grep -r "AttributeError" "src/"        # Error message
   grep -r "traceback|stack trace" "src/" # Error logging
   grep -r "logger.error" "src/"           # Error reports
   ```

3. **Contextual Search** (What calls it?)
   ```bash
   grep -r "\.attribute_name" "src/"     # Attribute access
   grep -r "\[\[" "src/"                  # Dictionary/array access
   grep -r "getattr" "src/"                # Dynamic access
   ```

4. **Temporal Search** (What changed recently?)
   ```bash
   git log --since='7d' --oneline
   git diff HEAD~5 --stat
   ```

---

## Template 3: INTEGRATION (cross-component/API failures)

**Symptoms:** "API call failed", "integration broken", "service X not responding"

1. **Mechanism Search** (Where is it integrated?)
   ```bash
   grep -r "import.*service" "src/"       # Service imports
   grep -r "api_client|http" "src/"      # API clients
   grep -r "requests|fetch" "src/"        # HTTP calls
   ```

2. **Functional Search** (What's the visible failure?)
   ```bash
   grep -r "timeout|ConnectionError" "src/"  # Connection errors
   grep -r "500|404|error" "src/"              # HTTP errors
   grep -r "fallback|retry" "src/"                # Error handling
   ```

3. **Contextual Search** (What calls it?)
   ```bash
   grep -r "def.*integration" "src/"    # Integration points
   grep -r "class.*Client" "src/"        # Client classes
   grep -r "\._call|\._request" "src/"  # Method calls
   ```

4. **Temporal Search** (What changed recently?)
   ```bash
   git log --since='7d' --oneline
   git diff HEAD~5 --stat
   ```

---

## Template 4: INTERMITTENT (flaky/rare/sometimes fails)

**Symptoms:** "Works sometimes", "flaky test", "race condition", "only fails on Tuesdays"

1. **Mechanism Search** (What could cause intermittent behavior?)
   ```bash
   grep -r "sleep|time|delay" "src/"    # Timing dependencies
   grep -r "async|await|thread" "src/"   # Concurrency
   grep -r "cache|memoize" "src/"         # Caching layers
   ```

2. **Functional Search** (What's the failure symptom?)
   ```bash
   grep -r "random|choice" "src/"         # Randomness
   grep -r "if.*time|date" "src/"          # Time-based logic
   grep -r "race|lock" "src/"             # Concurrency keywords
   ```

3. **Contextual Search** (What depends on state?)
   ```bash
   grep -r "global|static" "src/"         # Shared state
   grep -r "singleton|class.*:" "src/"    # Class variables
   grep -r "\.__dict__|setattr" "src/"   # Dynamic attributes
   ```

4. **Temporal Search** (What changed recently?)
   ```bash
   git log --since='7d' --oneline
   git diff HEAD~5 --stat
   ```

---

## Template 5: SECURITY (auth/vulnerability/injection)

**Symptoms:** "Unauthorized", "auth failed", "XSS", "injection", "security error"

1. **Mechanism Search** (Where is security enforced?)
   ```bash
   grep -r "auth|login|token" "src/"     # Authentication
   grep -r "permission|access" "src/"     # Authorization
   grep -r "validate|sanitize" "src/"     # Input validation
   ```

2. **Functional Search** (What's the security failure?)
   ```bash
   grep -r "UNAUTHORIZED|403|401" "src/"  # Auth errors
   grep -r "injection|XSS|CSRF" "src/"      # Vulnerabilities
   grep -r "eval|exec|system" "src/"        # Dangerous functions
   ```

3. **Contextual Search** (Where does input come from?)
   ```bash
   grep -r "request|user_input" "src/"    # User input
   grep -r "query|param|form" "src/"       # Parameters
   grep -r "\$\{\}|%s|format" "src/"       # String formatting
   ```

4. **Temporal Search** (What changed recently?)
   ```bash
   git log --since='7d' --oneline
   git diff HEAD~5 --stat
   ```

---

## Template Selection Guide

| Symptom | Use Template | Key Searches |
|----------|--------------|--------------|
| Slow/flashing UI | PERFORMANCE | `Progress(`, visible output, git log |
| AttributeError/crash | ERROR | Exception type, error message, attribute access |
| API call failed | INTEGRATION | API client, timeout, integration points |
| Flaky/sometimes | INTERMITTENT | async/thread, cache, shared state |
| Unauthorized | SECURITY | auth, token, input validation |

## Why Templates Matter: Flashing Progress Bar Example

**WITHOUT templates** (iteration 1):
```bash
grep("Progress(")  # Mechanism only -> Found 4 Rich Progress contexts
# FIXED ALL 4 -> USER: "Still flashing"  # MISSED!
```

**WITH templates** (iteration 1):
```bash
# Template 1: PERFORMANCE
grep("Progress(")     # Mechanism -> Found 4 Rich Progress contexts
grep("yt-api:")        # Functional -> Found 2 manual stdout writes  # ROOT CAUSE!
git log --since='7d' # Temporal -> Checked recent changes
# FIXED ALL 6 -> USER: "Fixed"  # CAUGHT IN ONE ITERATION!
```

**Lesson:** Functional search (`grep("yt-api:")`) would have been required by Template 1, preventing the 2-iteration miss.

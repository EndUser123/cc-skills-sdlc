# TRACE Phase Templates

This document provides trace table templates for common code patterns that require careful verification of resource management and logic correctness.

## How to Use TRACE Tables

1. **Create a table** for the function you're tracing
2. **List all scenarios** (happy path, error path, edge case)
3. **Step through each line** mentally, recording variable states
4. **Check cleanup** in all exception paths
5. **Document findings** - any logic errors or resource leaks

---

## Template 1: File I/O with Locking

**Use for:** Functions that acquire locks, read/write files, need cleanup in all paths

### Example Code
```python
def write_data_with_lock(filepath, data):
    lock_path = Path(str(filepath) + ".lock")
    lock_acquired = False
    lock_fd = None

    try:
        # Acquire lock exclusively
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        lock_acquired = True

        # Write data
        with open(filepath, 'w') as f:
            f.write(data)

        return True

    except OSError as e:
        logger.error(f"Failed to write {filepath}: {e}")
        return False

    finally:
        # Release lock
        if lock_acquired and lock_fd is not None:
            try:
                os.close(lock_fd)
            except OSError:
                pass
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass
```

### TRACE Table: Happy Path (Lock acquired, write succeeds)

| Line | Operation | lock_acquired | lock_fd | lock_path exists | Return | Notes |
|------|-----------|--------------|---------|------------------|--------|-------|
| 3 | Create lock_path | False | None | No | - | Path object created |
| 7 | os.open() | True | 3 | Yes | - | Lock file created |
| 11 | with open() | True | 3 | Yes | - | File opened for write |
| 12 | f.write() | True | 3 | Yes | - | Data written |
| 14 | return True | True | 3 | Yes | True | ✓ Function returns success |
| 21 | finally: check | True | 3 | Yes | - | ✓ lock_acquired is True |
| 22 | os.close() | True | None | Yes | - | ✓ File descriptor closed |
| 26 | unlink() | True | None | No | - | ✓ Lock file deleted |

**Findings:** ✓ Correct - lock properly acquired and released

---

### TRACE Table: Error Path (os.open fails - lock already exists)

| Line | Operation | lock_acquired | lock_fd | lock_path exists | Return | Notes |
|------|-----------|--------------|---------|------------------|--------|-------|
| 3 | Create lock_path | False | None | Yes | - | Lock file already exists |
| 7 | os.open() | False | OSError | Yes | - | ✗ OSError raised - lock exists |
| 17 | except OSError | False | None | Yes | - | Exception caught |
| 18 | logger.error() | False | None | Yes | - | Error logged |
| 19 | return False | False | None | Yes | False | ✓ Function returns failure |
| 21 | finally: check | False | None | Yes | - | ✓ lock_acquired is False |
| 22 | os.close() SKIP | False | None | Yes | - | ✓ Skipped - lock not acquired |
| 26 | unlink() SKIP | False | None | Yes | - | ✓ Skipped - won't delete another process's lock |

**Findings:** ✓ Correct - finally block only releases lock if we acquired it

---

### TRACE Table: Error Path (Write fails after lock acquired)

| Line | Operation | lock_acquired | lock_fd | lock_path exists | Return | Notes |
|------|-----------|--------------|---------|------------------|--------|-------|
| 7 | os.open() | True | 3 | Yes | - | Lock acquired |
| 11 | with open() | True | 3 | Yes | - | File opened |
| 12 | f.write() | True | 3 | Yes | OSError | ✗ Disk full, write fails |
| 13 | exception raised | True | 3 | Yes | - | Propagates to except |
| 17 | except OSError | True | 3 | Yes | - | Exception caught |
| 21 | finally: check | True | 3 | Yes | - | ✓ lock_acquired is True |
| 22 | os.close() | True | None | Yes | - | ✓ File descriptor closed |
| 26 | unlink() | True | None | No | - | ✓ Lock file deleted |

**Findings:** ✓ Correct - lock released even when write fails

---

## Template 2: File Descriptor Management

**Use for:** Functions that create temp files, use file descriptors, risk of fd reuse

### Example Code (BUG - File Descriptor Reuse)
```python
def write_with_retry(filepath, data, fallback_data):
    # Create temp file
    fd, temp_path = tempfile.mkstemp()

    try:
        # Write primary data
        with os.fdopen(fd, "w") as f:
            f.write(data)
        os.replace(temp_path, filepath)
        return True

    except OSError:
        # BUG: fd already consumed by fdopen()!
        with os.fdopen(fd, "w") as f:  # ✗ OSError - bad file descriptor
            f.write(fallback_data)
        os.replace(temp_path, filepath)
        return False
```

### TRACE Table: Error Path Showing Bug

| Line | Operation | fd | temp_path | file state | Notes |
|------|-----------|-----|-----------|------------|-------|
| 3 | mkstemp() | 5 | "/tmp/tmpXXX" | fd open | ✓ Valid fd |
| 6 | fdopen(fd) | 5 (consumed) | "/tmp/tmpXXX" | file object | ✗ fd consumed by os.fdopen() |
| 7 | f.write() | 5 (closed) | "/tmp/tmpXXX" | data written | with block closed fd |
| 8 | os.replace() | 5 (closed) | "/tmp/tmpXXX" | file moved | ✓ Success |
| 11 | except (not triggered) | - | - | - | No error here |
| 12 | fdopen(fd) | 5 (invalid) | "/tmp/tmpXXX" | - | ✗ OSError: Bad file descriptor |

**Findings:** ✗ **BUG** - File descriptor `fd` was consumed by first `fdopen()`, can't reuse in except block

---

### Fixed Code
```python
def write_with_retry_fixed(filepath, data, fallback_data):
    # Create temp file
    fd, temp_path = tempfile.mkstemp()

    try:
        # Write primary data
        with os.fdopen(fd, "w") as f:
            f.write(data)
        os.replace(temp_path, filepath)
        return True

    except OSError:
        # Create NEW temp file with NEW file descriptor
        fd_retry, temp_path_retry = tempfile.mkstemp()
        try:
            with os.fdopen(fd_retry, "w") as f:
                f.write(fallback_data)
            os.replace(temp_path_retry, filepath)
        finally:
            try:
                os.close(fd_retry)
            except OSError:
                pass
        return False
    finally:
        # Clean up original temp file if still exists
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            Path(temp_path).unlink(missing_ok=True)
        except OSError:
            pass
```

### TRACE Table: Fixed Error Path

| Line | Operation | fd_retry | temp_path_retry | Notes |
|------|-----------|----------|-----------------|-------|
| 13 | mkstemp() | 7 | "/tmp/tmpYYY" | ✓ New fd created |
| 14 | fdopen(fd_retry) | 7 (consumed) | "/tmp/tmpYYY" | ✓ Valid new fd |
| 15 | f.write() | 7 | "/tmp/tmpYYY" | ✓ Fallback data written |
| 20 | finally: close | None | "/tmp/tmpYYY" | ✓ Cleanup runs |

**Findings:** ✓ Correct - new temp file with new fd in except block

---

## Template 3: Concurrent Access with Race Conditions

**Use for:** Functions accessed by multiple processes/threads, risk of TOCTOU races

### Example Code (BUG - TOCTOU Race)
```python
def read_if_exists(filepath):
    # Check if file exists
    if Path(filepath).exists():
        # RACE: File could be deleted between check and read!
        with open(filepath, 'r') as f:
            return f.read()
    return None
```

### TRACE Table: Race Condition Scenario

| Process | Time | Operation | State |
|---------|------|-----------|-------|
| A | T1 | exists() check | True - file exists |
| B | T2 | exists() check | True - file exists |
| B | T3 | open() | Success - B reads file |
| B | T4 | unlink() | File deleted by B |
| A | T5 | open() | ✗ FileNotFoundError - race! |

**Findings:** ✗ **BUG** - TOCTOU (Time-of-check vs Time-of-use) race condition

---

### Fixed Code (Atomic Operation)
```python
def read_if_exists_fixed(filepath):
    try:
        # Atomic: open() will fail if file doesn't exist
        with open(filepath, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return None
```

### TRACE Table: Fixed Race Condition

| Process | Time | Operation | State |
|---------|------|-----------|-------|
| A | T1 | open() | Success - atomic check+open |
| B | T2 | open() | Success or fails atomically |
| A | T3 | read() | Success - no race |

**Findings:** ✓ Correct - atomic operation eliminates TOCTOU race

---

## Template 4: Exception Handling with Cleanup

**Use for:** Functions with complex exception handling, multiple cleanup steps

### Example Code
```python
def process_database(query):
    conn = None
    cursor = None
    transaction_started = False

    try:
        conn = db.connect()
        cursor = conn.cursor()
        cursor.execute("BEGIN")
        transaction_started = True

        cursor.execute(query)
        results = cursor.fetchall()

        conn.commit()
        return results

    except db.Error as e:
        if transaction_started:
            conn.rollback()
        raise

    finally:
        # Cleanup in reverse order of creation
        if cursor:
            cursor.close()
        if conn:
            conn.close()
```

### TRACE Table: Error Path (Query fails, transaction rollback)

| Line | Operation | conn | cursor | transaction_started | rollback? | Notes |
|------|-----------|------|--------|---------------------|-----------|-------|
| 5 | db.connect() | obj | None | False | - | ✓ Connection open |
| 6 | cursor() | obj | obj | False | - | ✓ Cursor created |
| 7 | BEGIN | obj | obj | True | - | ✓ Transaction started |
| 9 | execute() | obj | obj | True | - | Query fails |
| 12 | db.Error raised | obj | obj | True | - | Exception caught |
| 13 | if check | obj | obj | True | Yes | ✓ Check passes |
| 14 | rollback() | obj | obj | False | - | ✓ Transaction rolled back |
| 15 | raise | obj | obj | False | - | Re-raise to caller |
| 19 | finally: cursor | obj | obj | False | - | ✓ Close cursor |
| 21 | finally: conn | None | None | False | - | ✓ Close connection |

**Findings:** ✓ Correct - cleanup runs in all paths, transaction rolled back before re-raise

---

## Template 5: Concurrent Resource Access (Lock Acquisition Timeout)

**Use for:** Functions that acquire locks with timeout, risk of stale lock detection

### Example Code
```python
def acquire_with_timeout(lock_path, timeout_ms=5000):
    lock_acquired = False
    lock_fd = None
    start_time = time.time()

    try:
        while time.time() - start_time < timeout_ms / 1000:
            try:
                lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                lock_acquired = True
                return True
            except OSError:
                time.sleep(0.1)
        return False

    finally:
        # Only release if WE acquired it
        if lock_acquired and lock_fd is not None:
            try:
                os.close(lock_fd)
            except OSError:
                pass
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass
```

### TRACE Table: Timeout Path (Lock never acquired)

| Line | Operation | lock_acquired | lock_fd | finally cleanup? | Notes |
|------|-----------|--------------|---------|------------------|-------|
| 7 | while loop | False | None | - | Trying to acquire |
| 9 | os.open() | False | OSError | - | Lock held by another process |
| 11 | sleep | False | None | - | Wait and retry |
| 7 | while loop | False | None | - | Timeout expired |
| 14 | return False | False | None | - | ✓ Failed to acquire |
| 17 | finally: check | False | None | No | ✓ lock_acquired is False |
| 18 | close() SKIP | False | None | No | ✓ Skipped - no lock to release |
| 22 | unlink() SKIP | False | None | No | ✓ Won't delete other process's lock |

**Findings:** ✓ Correct - lock cleanup only happens if we acquired the lock

---

## TRACE Checklist

For each traced function, verify:

### Resource Management
- [ ] **File descriptors**: Opened → Used → Closed (even on exceptions)
- [ ] **Locks**: Acquired → Used → Released (even if acquisition fails)
- [ ] **Temp files**: Created → Used → Deleted (even on errors)
- [ ] **Network connections**: Open → Used → Close (with timeouts)
- [ ] **Database transactions**: Begin → Commit/Rollback → Close

### Exception Handling
- [ ] **No bare excepts** - must catch specific exceptions
- [ ] **All paths clean up** - exception paths don't leak resources
- [ ] **Error messages informative** - not empty or generic
- [ ] **Failures logged appropriately** - DEBUG vs INFO vs ERROR

### Concurrency Safety
- [ ] **Locks released even if try fails** - finally block checks acquisition flag
- [ ] **No TOCTOU races** - use atomic operations instead of check-then-act
- [ ] **File descriptors not reused** - create new fd in except blocks
- [ ] **Shared state has synchronization** - locks, atomic operations, or immutable data

### Logic Correctness
- [ ] **Early returns don't skip cleanup** - use finally or explicit cleanup
- [ ] **Finally blocks execute in all cases** - no early returns that bypass finally
- [ ] **Variables not reused after consumption** - fd, iterators, generators
- [ ] **Conditional branches cover all cases** - no missing else clauses

---

## How to Document TRACE Findings

After tracing, document your findings:

```markdown
## TRACE Results: module.py::function_name()

### Scenarios Traced
1. ✓ Happy path: Lock acquired, operation succeeds, lock released
2. ✓ Error path: Lock acquisition timeout, no cleanup attempted
3. ✓ Edge case: Operation fails after lock acquired, lock properly released

### Findings
- **No issues found** - all three scenarios trace correctly
- Resource cleanup works in all exception paths
- Lock acquisition flag properly prevents cleanup race

### Logic Errors Found: 0
### Resource Leaks Found: 0
### Race Conditions Found: 0
```

If issues found:

```markdown
## TRACE Results: module.py::function_name()

### Scenarios Traced
1. ✓ Happy path: File opened, data written, file closed
2. ✗ Error path: Write fails, file descriptor leaked
3. ✓ Edge case: File locked, waits for timeout

### Findings
- **BUG: File descriptor leak in error path**
  - Line 42: File descriptor `fd` consumed by fdopen() in try block
  - Line 48: Reused in except block → OSError
  - **Fix**: Create new temp file with new fd in except block (see Template 2)

### Logic Errors Found: 1
### Resource Leaks Found: 1
### Race Conditions Found: 0
```

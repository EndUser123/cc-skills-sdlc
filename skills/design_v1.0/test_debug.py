import sys

sys.path.insert(0, ".")

# Simulate exact pytest scenario
import json
import os
import threading
from pathlib import Path
import tempfile
from unittest.mock import patch

from config import load_arch_config, clear_config_cache

# Simulate test_concurrent_cache_access_no_corruption
print("=== test_concurrent_cache_access_no_corruption ===")
print("ARCH_DEFAULT_DOMAIN at start:", os.environ.get("ARCH_DEFAULT_DOMAIN"))

with patch.dict("os.environ", {"ARCH_DEFAULT_DOMAIN": "python"}, clear=False):
    print("ARCH_DEFAULT_DOMAIN during patch:", os.environ.get("ARCH_DEFAULT_DOMAIN"))

    num_iterations = 10
    num_threads = 5
    errors = []
    success_count = [0]

    def concurrent_load():
        for _ in range(num_iterations):
            try:
                with patch("pathlib.Path.exists") as mock_exists:
                    mock_exists.return_value = False
                    result = load_arch_config()
                    success_count[0] += 1
            except (KeyError, RuntimeError, TypeError) as e:
                errors.append((type(e).__name__, str(e)))

    threads = []
    for _ in range(num_threads):
        thread = threading.Thread(target=concurrent_load)
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    print(f"Success count: {success_count[0]}, Expected: {num_threads * num_iterations}")
    print(f"Errors: {errors}")

print("ARCH_DOMAIN after patch:", os.environ.get("ARCH_DEFAULT_DOMAIN"))

# Clear cache
clear_config_cache()

# Simulate test_no_lost_updates_under_concurrency
print("")
print("=== test_no_lost_updates_under_concurrency ===")

tmp_path = Path(tempfile.mkdtemp())
config_file = tmp_path / ".archconfig.json"
config_file.write_text(json.dumps({"default_domain": "python", "output_size": "normal"}))

print(f"Created config at: {config_file}")
print(f"Config exists: {config_file.exists()}")

original_cwd = os.getcwd()
os.chdir(tmp_path)
print(f"Changed to: {os.getcwd()}")

clear_config_cache()

results = []


def load_config():
    result = load_arch_config()
    results.append(result)


threads = []
for _ in range(5):
    thread = threading.Thread(target=load_config)
    threads.append(thread)
    thread.start()

for thread in threads:
    thread.join()

print(f"Results: {len(results)}")
print(f"None results: {sum(1 for r in results if r is None)}")
print(f"First result: {results[0] if results else 'No results'}")

os.chdir(original_cwd)

import shutil

shutil.rmtree(tmp_path)

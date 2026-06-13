# Post-Consolidation Environment Audit

## 1. Root Cause: `tests/test_data/test_output.json` Modification

**Root cause:** `tests/test_extraction.py` is a script-style integration test with no `def test_*` functions. It executes its pipeline code at **module top-level** (import-time), which means pytest triggers the full `IngestionPipeline.process()` during test collection. The script writes the resulting SRO JSON to the tracked path `tests/test_data/test_output.json`, causing the working tree to become dirty on every `pytest` invocation.

**Evidence:**
- `tests/test_extraction.py` line 101 (original): `out_path = Path(r"D:\RM\tests\test_data\test_output.json")`
- `git diff` showed `sro_id`, `created_at`, `updated_at`, and `processing_time_ms` changes — all non-deterministic runtime values

**Fix applied:**
1. Redirected the output path to `D:\RM\.tmp\test_output.json` (an untracked, ignored directory)
2. Added `collect_ignore = ["tests/test_extraction.py"]` to `conftest.py` to prevent pytest from collecting this script-style test during standard runs
3. Added a note: run explicitly via `python tests/test_extraction.py` when the full pipeline integration check is needed

---

## 2. Root Cause: Pytest Using `C:\Users\...\AppData\Local\Temp`

**Root cause:** The system `TEMP` and `TMP` environment variables point to `C:\Users\RATISH~1\AppData\Local\Temp`. Python's `tempfile.gettempdir()` reads these variables, so any pytest fixture using `tmp_path`, `tmpdir`, or `tempfile.mkdtemp()` defaults to the C: drive.

**Evidence:**
```
$env:TEMP  → C:\Users\RATISH~1\AppData\Local\Temp
$env:TMP   → C:\Users\RATISH~1\AppData\Local\Temp
python -c "import tempfile; print(tempfile.gettempdir())" → C:\Users\RATISH~1\AppData\Local\Temp
```

**Fix applied:**
1. `pyproject.toml` `[tool.pytest.ini_options]`:
   - `basetemp = "D:/RM/.tmp/pytest"` — sets the base dir for `tmp_path` fixtures
   - `cache_dir = "D:/RM/.cache/pytest"` — redirects the pytest cache away from `.pytest_cache`
   - `tmp_path_retention_policy = "failed"` — only retain `tmp_path` dirs for failed tests
2. `conftest.py` (root-level, runs at session start):
   - `os.environ["TEMP"] = "D:/RM/.tmp"`
   - `os.environ["TMP"] = "D:/RM/.tmp"`
   - `tempfile.tempdir = "D:/RM/.tmp"` — overrides Python's built-in default

> **Note:** The session-level shell `TEMP`/`TMP` must also be set before invoking pytest (e.g., `$env:TEMP="D:\RM\.tmp"; python -m pytest ...`). The conftest.py override covers any code running *inside* the pytest process.

---

## 3. Root Cause: `.pytest_cache` Access Denied

**Root cause:** The `D:\RM\.pytest_cache` directory was created during a **previous elevated or different-session pytest run** (likely during the original M7/M8 Antigravity worktree sessions). The resulting directory has an ACL that excludes the current user token, which runs in a **split-token UAC context** (`Group used for deny only`). This means even Administrator group membership doesn't grant access without a UAC elevation prompt.

**Evidence:**
```
icacls .pytest_cache        → "Access is denied."
takeown /F .pytest_cache    → "ERROR: Access is denied."
Set-Acl                     → "Attempted to perform an unauthorized operation."
attrib D:\RM\.pytest_cache  → (no flags shown, directory accessible to attrib but not icacls)
cacls D:\RM\.pytest_cache   → "Access is denied."
```
The directory appears valid in `dir /A` but is inaccessible to all standard operations. The `fsutil reparsepoint query` also fails with error 5.

**Fix applied:**
- Redirected `cache_dir` to `D:\RM\.cache\pytest` (fully user-writable, confirmed working)
- The locked `.pytest_cache` directory remains in place (empty/inaccessible), but is no longer used
- Added `.pytest_cache/` to `.gitignore` so it is not tracked
- **Manual cleanup note:** The locked directory can be permanently removed by running an elevated Command Prompt: `rd /S /Q D:\RM\.pytest_cache`

---

## 4. Exact Fixes Applied

| File | Change |
|------|--------|
| `pyproject.toml` | Added `cache_dir`, `basetemp`, `tmp_path_retention_policy` to `[tool.pytest.ini_options]` |
| `conftest.py` | Created root conftest; overrides `TEMP`/`TMP`/`tempfile.tempdir`; adds `collect_ignore` |
| `tests/test_extraction.py` | Redirected SRO output from `tests/test_data/test_output.json` → `D:\RM\.tmp\test_output.json` |
| `.gitignore` | Added `.tmp/`, `.cache/`, `.venv/`, `.eval_deps/`, `tmp/` |

**Commit:** `f75118a chore(env): configure pytest to use D:\RM for all temp/cache artifacts`

---

## 5. Final Directory Locations Used by Pytest

| Artifact | Location |
|----------|----------|
| `tmp_path` fixtures | `D:\RM\.tmp\pytest\` |
| Cache (nodeids, lastfailed, etc.) | `D:\RM\.cache\pytest\v\cache\` |
| Python `tempfile` calls | `D:\RM\.tmp\` |
| Integration test SRO output | `D:\RM\.tmp\test_output.json` |
| Legacy locked cache (unused) | `D:\RM\.pytest_cache` (inaccessible, empty) |

**Confirmed:** `D:\RM\.cache\pytest\v\cache\nodeids` was written after running pytest with cache enabled.

---

## 6. Final Git Status

```
On branch module5-development
nothing to commit, working tree clean
```

**Final HEAD commit:** `f75118a chore(env): configure pytest to use D:\RM for all temp/cache artifacts`

---

## 7. Final Test Results

**Run 1:** `pytest -p no:cacheprovider` (skips cache)
```
3054 passed, 7 warnings in 13.17s
```

**Run 2:** `pytest` (with cache_dir=D:/RM/.cache/pytest)
```
3054 passed, 6 warnings in 25.63s
```

No test failures. Git status remained clean after both runs (no tracked files modified).

---

## 8. Confirmation: ResearchMind is Self-Contained Under D:\RM

| Check | Status |
|-------|--------|
| Source code | `D:\RM\src\researchmind\` ✅ |
| Backend (M8 FastAPI) | `D:\RM\backend\` ✅ |
| Frontend (M7) | `D:\RM\frontend\` ✅ |
| Pytest cache | `D:\RM\.cache\pytest\` ✅ |
| Pytest temp | `D:\RM\.tmp\pytest\` ✅ |
| Python tempfile | `D:\RM\.tmp\` ✅ |
| Integration test output | `D:\RM\.tmp\test_output.json` ✅ |
| No C: paths in pytest artifacts | ✅ (with `$env:TEMP/TMP` set before invocation) |
| Working tree clean after `pytest` | ✅ |
| Worktree removed | ✅ (removed in previous session) |
| `main` branch untouched | ✅ |
| All work on `module5-development` | ✅ |

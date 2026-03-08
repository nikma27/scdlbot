# Dependency Scan Report — scdlbot

**Scan date:** 2026-03-07  
**Scope:** Python dependencies (Poetry / requirements.txt)

---

## Executive Summary

| Category | Count |
|----------|-------|
| **Security vulnerabilities** | 1 (cryptography) |
| **High-confidence safe upgrades** | 8 |
| **Potential breaking changes** | 2 (scdl, doc8) |
| **Git-pinned deps with newer commits** | 2 |

---

## 1. Security Vulnerabilities (High Priority)

### cryptography 46.0.4 → 46.0.5

- **CVE:** CVE-2026-26007 (GHSA-r6ph-v2qm-q3c2)
- **CVSS:** 6.5 (MEDIUM)
- **Impact:** Public key functions fail to verify that points belong to the expected prime-order subgroup for SECT curves. Can lead to private key leakage, signature forgery, or partial key disclosure.
- **Fix:** Upgrade to cryptography ≥46.0.5
- **Where:** Transitive via `authlib` in dev dependencies (`requirements-dev.txt`)

**Action:** Add explicit `cryptography>=46.0.5` or run `poetry update cryptography` and re-export requirements.

---

## 2. High-Confidence Safe Upgrades (Patch/Minor)

These are low-risk, backwards-compatible updates:

| Package | Current | Latest | Notes |
|---------|---------|--------|-------|
| certifi | 2026.1.4 | 2026.2.25 | CA bundle updates |
| charset-normalizer | 3.4.4 | 3.4.5 | Bug fixes |
| filelock | 3.20.3 | 3.25.0 | Patch releases |
| soundcloud-v2 | 1.6.1 | 1.6.2 | Minor |
| tqdm | 4.67.1 | 4.67.3 | Patch |
| yt-dlp-ejs | 0.4.0 | 0.5.0 | Minor (EJS support) |

---

## 3. Potential Breaking Changes

### scdl 2.12.4 → 3.0.4 (MAJOR)

- **Change:** SCDL 3.x is a wrapper around `yt-dlp` instead of its own downloader.
- **CLI compatibility:** `-l`, `--path`, `--onlymp3`, `-c`, `--addtofile`, `--addtimestamp`, `--no-playlist-folder`, `--extract-artist` appear to be preserved for backwards compatibility.
- **Risk:** Medium — architecture change; recommend testing SoundCloud downloads before production.
- **Recommendation:** Upgrade in a separate PR with manual testing of SoundCloud links.

### doc8 1.1.2 → 2.0.0 (MAJOR)

- **Note:** `pyproject.toml` specifies `doc8 = "^2.0.0"` but `poetry.lock` has 1.1.2. Lock may be stale.
- **Risk:** Low — doc linter; changes may affect RST style rules.
- **Recommendation:** Run `poetry lock` and `poetry update doc8`, then run `doc8 docs` to verify.

---

## 4. Git-Pinned Dependencies

| Package | Current | Latest commit | Notes |
|---------|---------|---------------|-------|
| bandcamp-downloader | a980996 | 558b785 | Newer commit available |
| yt-dlp | e4c120f (2026.1.29) | b8058cd (2026.3.3) | Newer release available |

**Recommendation:** Update git refs periodically for security and compatibility. Test Bandcamp and YouTube downloads after updating.

---

## 5. Deprecations & Tooling Notes

- **safety `check`:** The `safety check` command is deprecated (post June 2024). Prefer `safety scan`.
- **requests 2.32.x:** `get_connection` deprecated in favor of `get_connection_with_tls_context`; only relevant if using custom HTTPAdapters.
- **urllib3 2.x:** `HTTPResponse.getheaders()` / `getheader()` deprecated in favor of `HTTPResponse.headers`.

---

## 6. Proposed Update Plan (Smallest Safe Path)

### Phase 1 — Security (do first)

1. Update cryptography to ≥46.0.5:
   ```bash
   poetry add "cryptography>=46.0.5"
   # or: poetry update cryptography
   ```

### Phase 2 — Low-risk patches

2. Update patch/minor versions:
   ```bash
   poetry update certifi charset-normalizer filelock soundcloud-v2 tqdm yt-dlp-ejs
   ```

### Phase 3 — Optional, higher-risk

3. **scdl 3.0.4:** Upgrade and run SoundCloud download tests.
4. **doc8 2.0.0:** Run `poetry update doc8` and `doc8 docs`.
5. **Git refs:** Update bandcamp-dl and yt-dlp to latest commits/releases; test Bandcamp and YouTube flows.

### Phase 4 — Re-export requirements

6. Regenerate lock and requirements files:
   ```bash
   poetry lock
   poetry export -f requirements.txt --without-hashes -o requirements.txt
   poetry export -f requirements.txt --without-hashes --with dev -o requirements-dev.txt
   poetry export -f requirements.txt --without-hashes --with docs -o requirements-docs.txt
   ```

---

## 7. Safety Scan Summary

- **safety check** on `requirements.txt` and `requirements-dev.txt`: **0 vulnerabilities** (safety DB; CVE-2026-26007 may not yet be in DB).
- **Manual review:** cryptography 46.0.4 is affected by CVE-2026-26007; upgrade to 46.0.5+.

---

## 8. Cloud Environment Policy (Cursor)

- Startup bootstrap should install from lock file only (`poetry install --with main,dev,docs,flacbot --sync`) and **must not** auto-upgrade dependencies.
- Keep major upgrades flagged in this report (currently `scdl` and `doc8`) in separate PRs with targeted validation.
- Ensure system FFmpeg availability before bot/runtime checks to avoid false-negative failures in smoke tests.

---

## Files Referenced

- `pyproject.toml` — Poetry project definition
- `poetry.lock` — Locked dependencies
- `requirements.txt` — Main runtime deps (exported)
- `requirements-dev.txt` — Dev deps (exported)
- `requirements-docs.txt` — Docs deps (exported)
- `requirements-flacbot.txt` — Flacbot extras (minimal)

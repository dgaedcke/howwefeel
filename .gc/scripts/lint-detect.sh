#!/usr/bin/env bash
# lint-detect.sh — city-wide lint runner.
#
# Auto-detects the rig's language/toolchain from files at the CWD and runs
# the appropriate lint command. Exits 0 when lint passes (or no toolchain
# is detected — a rig without lint simply no-ops). Exits non-zero when
# lint fails or a detected linter is missing.
#
# Used as the default {{lint_command}} in gastown formulas so that the
# refinery and polecat enforce lint without the formulas being tied to a
# single language.

set -euo pipefail

# -- Python (ruff) -----------------------------------------------------------
if [ -f pyproject.toml ] && grep -q '\[tool\.ruff' pyproject.toml; then
  # Pick a ruff runner. Order: direct binary > uvx (no-install, fast) >
  # pipx > python -m ruff (venv). Falls through to failure if none work.
  if command -v ruff >/dev/null 2>&1; then
    RUFF=(ruff)
  elif command -v uvx >/dev/null 2>&1; then
    RUFF=(uvx ruff)
  elif command -v pipx >/dev/null 2>&1; then
    RUFF=(pipx run ruff)
  elif command -v python3 >/dev/null 2>&1 && python3 -c "import ruff" 2>/dev/null; then
    RUFF=(python3 -m ruff)
  else
    echo "lint-detect: pyproject.toml declares ruff but no runner available" >&2
    echo "  tried: ruff, uvx ruff, pipx run ruff, python3 -m ruff" >&2
    exit 2
  fi
  # Prefer configured src/tests layout; fall back to repo root.
  if [ -d src ] && [ -d tests ]; then
    "${RUFF[@]}" format --check src/ tests/
    "${RUFF[@]}" check src/ tests/
  else
    "${RUFF[@]}" format --check .
    "${RUFF[@]}" check .
  fi
  exit 0
fi

# -- JavaScript / TypeScript (eslint) ----------------------------------------
if [ -f package.json ]; then
  if grep -qE '"eslint"' package.json || ls .eslintrc* eslint.config.* >/dev/null 2>&1; then
    # Prefer repo's own `lint` script when defined.
    if grep -qE '"lint"\s*:' package.json; then
      npm run --silent lint
    else
      npx --no-install eslint .
    fi
    exit 0
  fi
fi

# -- Go ----------------------------------------------------------------------
if [ -f go.mod ]; then
  unformatted=$(gofmt -l .)
  if [ -n "$unformatted" ]; then
    echo "lint-detect: gofmt reports unformatted files:" >&2
    echo "$unformatted" >&2
    exit 1
  fi
  go vet ./...
  exit 0
fi

# -- Rust --------------------------------------------------------------------
if [ -f Cargo.toml ]; then
  cargo fmt --all -- --check
  cargo clippy --all-targets --all-features -- -D warnings
  exit 0
fi

# -- No toolchain detected ---------------------------------------------------
# A rig may legitimately have no lint step configured yet; don't block merges
# on that. A rig that wants stricter enforcement can override lint_command.
echo "lint-detect: no known toolchain at $(pwd); skipping lint"
exit 0

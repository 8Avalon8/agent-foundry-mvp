#!/usr/bin/env bash
set -euo pipefail

REPO_NAME="${1:-agent-foundry-mvp}"
VISIBILITY="${2:-private}" # private or public
BRANCH="${BRANCH:-main}"

if [[ "$VISIBILITY" != "private" && "$VISIBILITY" != "public" ]]; then
  echo "Usage: $0 [repo-name] [private|public]" >&2
  exit 2
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git is required." >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  cat >&2 <<'MSG'
GitHub CLI (gh) is required for one-command publishing.
Install it, then run:
  gh auth login
  bash scripts/publish_to_github.sh agent-foundry-mvp private

Alternative manual flow:
  1. Create an empty GitHub repo named agent-foundry-mvp.
  2. Run:
     git remote add origin git@github.com:<owner>/agent-foundry-mvp.git
     git push -u origin main
MSG
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "gh is not authenticated. Run: gh auth login" >&2
  exit 1
fi

if [[ ! -d .git ]]; then
  git init -b "$BRANCH"
fi

git add .
if ! git diff --cached --quiet; then
  git commit -m "Initial Agent Foundry MVP"
fi

# Create repo if needed; if it exists, continue and just ensure remote is set.
if ! gh repo view "$REPO_NAME" >/dev/null 2>&1; then
  if [[ "$VISIBILITY" == "private" ]]; then
    gh repo create "$REPO_NAME" --private --source=. --remote=origin --push
  else
    gh repo create "$REPO_NAME" --public --source=. --remote=origin --push
  fi
else
  OWNER="$(gh api user --jq .login)"
  if ! git remote get-url origin >/dev/null 2>&1; then
    git remote add origin "git@github.com:${OWNER}/${REPO_NAME}.git"
  fi
  git push -u origin "$BRANCH"
fi

echo "Published: $(gh repo view "$REPO_NAME" --json url --jq .url)"

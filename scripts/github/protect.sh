#!/usr/bin/env bash
# One-time GitHub setup for d-rohan-web/openwatch (needs: gh auth login, as the repo owner).
#   bash scripts/github/protect.sh
set -euo pipefail
REPO="${REPO:-d-rohan-web/openwatch}"

echo "→ repository settings: squash-only, auto-merge, delete merged branches, security features"
gh api -X PATCH "repos/$REPO" --silent \
  -F allow_squash_merge=true -F allow_merge_commit=false -F allow_rebase_merge=false \
  -F allow_auto_merge=true -F delete_branch_on_merge=true \
  -f squash_merge_commit_title=PR_TITLE \
  -F 'security_and_analysis[secret_scanning][status]=enabled' \
  -F 'security_and_analysis[secret_scanning_push_protection][status]=enabled' || true
gh api -X PUT "repos/$REPO/private-vulnerability-reporting" --silent || true
gh api -X PUT "repos/$REPO/vulnerability-alerts" --silent || true
gh api -X PUT "repos/$REPO/automated-security-fixes" --silent || true
# let the Dependabot workflow approve its own patch/minor PRs
gh api -X PUT "repos/$REPO/actions/permissions/workflow" --silent \
  -f default_workflow_permissions=read -F can_approve_pull_request_reviews=true

echo "→ ruleset 'main protection'"
existing=$(gh api "repos/$REPO/rulesets" --jq '.[] | select(.name=="main protection") | .id' || true)
method=POST; path="repos/$REPO/rulesets"
[ -n "$existing" ] && { method=PUT; path="repos/$REPO/rulesets/$existing"; }
gh api -X "$method" "$path" --silent --input - <<'JSON'
{
  "name": "main protection",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "bypass_actors": [
    { "actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "pull_request" }
  ],
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "required_linear_history" },
    { "type": "pull_request", "parameters": {
        "required_approving_review_count": 1,
        "require_code_owner_review": true,
        "dismiss_stale_reviews_on_push": true,
        "require_last_push_approval": true,
        "required_review_thread_resolution": true,
        "allowed_merge_methods": ["squash"] } },
    { "type": "required_status_checks", "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [
          { "context": "Backend tests" },
          { "context": "Frontend types, tests, build" },
          { "context": "Docker images build" },
          { "context": "No secrets committed" },
          { "context": "Conventional PR title" }
        ] } }
  ]
}
JSON
echo "✓ done: main needs a PR, passing CI and a code-owner review; no force-push or deletion."
echo "  (Repository admins can merge their own PRs without a second reviewer, but still through a PR.)"

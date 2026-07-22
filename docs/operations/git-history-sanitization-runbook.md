# Git History Sanitization Runbook

This procedure removes the revoked Supabase credential from reachable Git history. Run it from a fresh clone. Do not use an existing working copy.

## Preconditions

- The exposed Supabase service-role key and legacy JWT signing secret are revoked.
- All open pull requests are closed.
- No collaborator is pushing during the rewrite.
- Git 2.36 or newer, Python 3, and `git-filter-repo` 2.47 or newer are installed.

## Windows PowerShell Procedure

```powershell
$ErrorActionPreference = "Stop"
$RepoUrl = "https://github.com/muhamedsohaib/gemini-trading.git"
$CleanupRoot = Join-Path $HOME "Desktop\gemini-trading-history-cleanup"

Remove-Item -Recurse -Force $CleanupRoot -ErrorAction SilentlyContinue
git clone $RepoUrl $CleanupRoot
Set-Location $CleanupRoot

git filter-repo --sensitive-data-removal --invert-paths `
  --path .env.local `
  --path .env.local.txt `
  --path test_ledger.py
```

`--sensitive-data-removal` fetches refs needed for the cleanup. `git-filter-repo` may remove the `origin` remote as a safety measure. Restore it before pushing:

```powershell
if ((git remote) -contains "origin") {
    git remote remove origin
}
git remote add origin $RepoUrl
```

## Verification Before Push

```powershell
$RemovedPaths = git log --all --name-only --pretty=format: -- .env.local .env.local.txt test_ledger.py
if ($RemovedPaths) {
    throw "Sensitive paths still exist in rewritten history. Do not push."
}

$ChangedRefs = Get-Content .git\filter-repo\changed-refs
$AffectedPullRefs = $ChangedRefs | Select-String '^refs/pull/.*/head$'
$AffectedPullRefs

git fsck --full --no-reflogs --unreachable
```

For an additional content check, create a temporary text file outside the repository containing the exact revoked key followed by `==>REMOVED_SUPABASE_SERVICE_ROLE_KEY`, then run:

```powershell
git filter-repo --force --sensitive-data-removal --replace-text ..\private-secret-replacements.txt
Remove-Item ..\private-secret-replacements.txt -Force
```

Do not commit, upload, or paste that replacement file anywhere.

Repeat the path and content verification after the replacement pass.

## Force Push

Temporarily disable branch rules that block force pushes, then run:

```powershell
git push --force --mirror origin
```

Failures for `refs/pull/*` are expected because GitHub pull-request refs are read-only. Any other failed branch or tag update must be resolved before considering the rewrite complete.

## After Push

1. Re-enable branch protection immediately.
2. Confirm that `main`, `design/hybrid-open-core-reconstruction`, and `security/containment-foundation` have new commit hashes.
3. Open a new pull request from the rewritten security branch.
4. Require every existing clone to be deleted and cloned again, or carefully cleaned without merging old history.
5. Contact GitHub Support with the repository name, affected pull-request count, first changed commit reported by `git-filter-repo`, and any orphaned LFS report so cached views and pull-request refs can be evaluated for removal.
6. Delete the cleanup clone after verification.

## Abort Conditions

Do not push if:

- any removed path still appears in `git log`;
- the exact revoked credential is still found;
- unexpected branches or tags appear in `.git/filter-repo/changed-refs`;
- collaborators have pushed after the cleanup clone was created;
- any non-pull-request ref fails to update.

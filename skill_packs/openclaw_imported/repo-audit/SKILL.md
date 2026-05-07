---
name: repo-audit
description: Audit a Git repository for issues, code smells, and security vulnerabilities.
requires:
  env: [GITHUB_TOKEN]
  bins: [git, docker]
install:
  brew: [git]
---

# Repo Audit

## Procedure
1. Clone or open the target repository.
2. Run static analyzers (ruff, bandit, eslint) on the codebase.
3. Check for security vulnerabilities in dependencies.
4. Generate a summary report with findings and severity levels.
5. Output a JSON report with all issues found.

## Verification
- Verify all required tools are installed.
- Confirm audit completes without errors.
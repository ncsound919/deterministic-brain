---
skill: gitlab-manage
version: 1.0
backend: local
backend_skill_id: ""
description: GitLab operations — projects, issues, merge requests, pipelines
inputs:
  action: string
  project_id: int
  title: string
  description: string
tools: [gitlab_list_issues, gitlab_create_issue, gitlab_list_mrs]
audit: []
monte_carlo: false
---
## Step 1 — Perform GitLab action
- list_projects: search and list accessible projects
- create_issue: file a new issue in a project
- list_mrs: view open merge requests
- pipeline_status: check CI/CD pipeline status

## Step 2 — Return structured result
Requires: GITLAB_TOKEN + GITLAB_INSTANCE env vars

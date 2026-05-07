---
skill: create-react-component
version: 1.0
backend: local
backend_skill_id: ""
description: Create a React component with optional props
inputs:
  component_name: string
  props: list
tools: [file_write, run_linter]
audit: []
monte_carlo: false
---
## Step 1
Render template `skill_packs/react/templates/react-component.tsx.j2` with context:
  - component_name = {{component_name}}
  - props = {{props}}

## Step 2
Write result to `output/components/{{component_name}}.tsx`

## Step 3
Run linter on `output/components/{{component_name}}.tsx`

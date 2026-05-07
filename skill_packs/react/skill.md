---
name: React Component Generator
description: Generate React components with TypeScript
backend: local
---

# Steps

## Generate Component
template: |
  import React from 'react';
  
  interface {{component_name}}Props {
    className?: string;
  }
  
  export const {{component_name}}: React.FC<{{component_name}}Props> = ({ className }) => {
    return (
      <div className={className}>
        {{component_name}} Component
      </div>
    );
  };
output: src/components/{{component_name}}.tsx
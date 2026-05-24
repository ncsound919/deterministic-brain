// SkillMarketplace.types.ts
// Type definitions for SkillMarketplace component

export interface SkillInput {
  [key: string]: string | {
    type?: string;
    description?: string;
    required?: boolean;
    default?: string;
  };
}

export interface Skill {
  skill_id: string;
  skill_name: string;
  description: string;
  backend: string;
  source_format?: string;
  skill_path?: string;
  inputs?: SkillInput;
  tools?: string[];
  [key: string]: any; // Allow additional properties
}

export interface Chain {
  id?: string;
  name?: string;
  description?: string;
  cron?: string;
  steps?: Array<{
    skill?: string;
    name?: string;
    status?: string;
  }>;
  [key: string]: any; // Allow additional properties
}

export interface ExecutionLogEntry {
  ts: string;
  skillId: string;
  status: 'running' | 'success' | 'failed' | 'error';
  msg: string;
}

export interface CategoryMeta {
  label: string;
  icon: any; // Lucide icon component
  color: string;
  keywords: string[];
}

export type CategoryMap = Record<string, CategoryMeta>;

export interface SkillMarketplaceProps {
  // No props currently, but can be extended
}

export interface SkillMarketplaceState {
  skills: Skill[];
  chains: Chain[];
  activeCat: string;
  search: string;
  loading: boolean;
  running: string | null;
  resultLog: ExecutionLogEntry[];
  activeTab: 'skills' | 'chains';
  selectedSkill: Skill | null;
  showCreate: boolean;
  newSkillName: string;
  newSkillDesc: string;
  newSkillCode: string;
  showInputs: boolean;
  inputValues: Record<string, string>;
  selectedSkillForExecution: Skill | null;
  showConfirm: boolean;
  skillToConfirm: Skill | null;
}
"""Audit Repo Lane — analyze repository for code quality and security issues."""
from __future__ import annotations
import os
import re
from typing import Dict, List

def run(state: dict) -> dict:
    """Run repository audit.
    
    Expected state keys:
    - query: str - the original user query (e.g., "audit repo ./my-project")
    - retrieved_contexts: list - any pre-retrieved context
    - task: dict - parsed task with repo_path
    """
    query = state.get('query', '')
    task = state.get('task', {})
    repo_path = task.get('repo_path', '')
    
    if not repo_path:
        repo_path = _extract_repo_path(query)
    
    audit_results = {
        'repo_path': repo_path,
        'files_analyzed': 0,
        'issues': [],
        'security_issues': [],
        'code_quality': [],
        'summary': '',
    }
    
    if os.path.exists(repo_path):
        audit_results = _analyze_repository(repo_path)
    else:
        audit_results['issues'].append(f"Repository path does not exist: {repo_path}")
        audit_results['summary'] = 'Audit failed: path not found'
    
    state['candidate_artifacts'] = [{
        'id': 'audit-report',
        'kind': 'audit',
        'content': _format_audit_report(audit_results),
    }]
    
    state['verification_results'].append({
        'stage': 'repo_audit',
        'passed': len(audit_results['issues']) == 0,
        'reason': 'audit_complete',
        'details': audit_results,
    })
    
    state['final_output'] = _format_audit_report(audit_results)
    state['output_mode'] = 'text'
    state['confidence'] = 0.85 if audit_results['files_analyzed'] > 0 else 0.3
    state['history'].append({
        'lane': 'audit_repo',
        'repo_path': repo_path,
        'files_analyzed': audit_results['files_analyzed'],
        'issues_found': len(audit_results['issues']),
    })
    
    return state


def _extract_repo_path(query: str) -> str:
    """Extract repository path from query."""
    patterns = [
        r'audit\s+(?:repo\s+)?(?:repository\s+)?([^\s]+)',
        r'review\s+([^\s]+)',
        r'check\s+([^\s]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return match.group(1)
    return './'


def _analyze_repository(repo_path: str) -> Dict:
    """Perform static analysis on repository."""
    results = {
        'repo_path': repo_path,
        'files_analyzed': 0,
        'issues': [],
        'security_issues': [],
        'code_quality': [],
    }
    
    for root, dirs, files in os.walk(repo_path):
        if '.git' in root or '__pycache__' in root or 'node_modules' in root:
            continue
            
        for file in files:
            if file.endswith(('.py', '.js', '.ts', '.tsx', '.jsx', '.go', '.rs', '.java')):
                results['files_analyzed'] += 1
                file_path = os.path.join(root, file)
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    _analyze_file_content(file_path, content, results)
                except Exception as e:
                    results['issues'].append(f"Error reading {file_path}: {e}")
    
    results['summary'] = _generate_summary(results)
    return results


def _analyze_file_content(file_path: str, content: str, results: Dict) -> None:
    """Analyze file content for issues."""
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        
        if 'eval(' in stripped or 'exec(' in stripped:
            results['security_issues'].append({
                'file': file_path,
                'line': i,
                'issue': 'Dangerous function usage (eval/exec)',
                'severity': 'high',
            })
        
        if 'password' in stripped.lower() or 'secret' in stripped.lower() or 'api_key' in stripped.lower():
            if '=' in stripped and not stripped.startswith('#'):
                results['security_issues'].append({
                    'file': file_path,
                    'line': i,
                    'issue': 'Potential hardcoded secret',
                    'severity': 'high',
                })
        
        if len(line) > 120:
            results['code_quality'].append({
                'file': file_path,
                'line': i,
                'issue': 'Line exceeds 120 characters',
                'severity': 'low',
            })
        
        if stripped == 'TODO' or stripped.startswith('TODO:'):
            results['code_quality'].append({
                'file': file_path,
                'line': i,
                'issue': 'TODO comment found',
                'severity': 'low',
            })


def _generate_summary(results: Dict) -> str:
    """Generate audit summary."""
    sec = len(results['security_issues'])
    qual = len(results['code_quality'])
    total = sec + qual
    
    if total == 0:
        return f"✓ Audit complete: {results['files_analyzed']} files analyzed, no issues found."
    elif sec > 0:
        return f"⚠ Audit complete: {results['files_analyzed']} files, {sec} security issues, {qual} quality issues."
    else:
        return f"ℹ Audit complete: {results['files_analyzed']} files, {qual} code quality issues."


def _format_audit_report(results: Dict) -> str:
    """Format audit results as readable report."""
    lines = [
        f"# Repository Audit Report",
        f"",
        f"Path: {results['repo_path']}",
        f"Files Analyzed: {results['files_analyzed']}",
        f"",
        f"## Summary",
        f"{results['summary']}",
        f"",
    ]
    
    if results['security_issues']:
        lines.append("## Security Issues")
        for issue in results['security_issues']:
            lines.append(f"- [{issue['severity'].upper()}] {issue['file']}:{issue['line']} - {issue['issue']}")
        lines.append("")
    
    if results['code_quality']:
        lines.append("## Code Quality Issues")
        for issue in results['code_quality'][:10]:
            lines.append(f"- {issue['file']}:{issue['line']} - {issue['issue']}")
        if len(results['code_quality']) > 10:
            lines.append(f"- ... and {len(results['code_quality']) - 10} more")
        lines.append("")
    
    return '\n'.join(lines)
"""Live Docs to Skill Lane — convert live documentation to skill format."""
from __future__ import annotations
import re
import os
from typing import List, Optional

def run(state: dict) -> dict:
    """Convert live documentation to skill format.
    
    Expected state keys:
    - query: str - the original user query (e.g., "scrape docs from https://...")
    - retrieved_contexts: list - any pre-retrieved context
    - task: dict - parsed task with url
    """
    query = state.get('query', '')
    task = state.get('task', {})
    url = task.get('url', '')
    
    if not url:
        url = _extract_url(query)
    
    if not url:
        state['status'] = 'failed'
        state['final_output'] = {'error': 'No URL provided in query'}
        return state
    
    doc_content = _fetch_doc_content(url)
    
    if not doc_content:
        state['status'] = 'failed'
        state['final_output'] = {'error': f'Could not fetch documentation from {url}'}
        return state
    
    skill_content = _convert_to_skill(doc_content, url)
    
    skill_id = _extract_skill_name(url)
    output_path = f'output/skills/{skill_id}.md'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(skill_content)
    
    state['candidate_artifacts'] = [{
        'id': f'skill-{skill_id}',
        'kind': 'skill',
        'content': skill_content,
        'source_url': url,
        'output_path': output_path,
    }]
    
    state['verification_results'].append({
        'stage': 'docs_to_skill',
        'passed': True,
        'reason': 'conversion_complete',
        'details': {
            'url': url,
            'skill_id': skill_id,
            'output_path': output_path,
            'content_length': len(skill_content),
        },
    })
    
    state['final_output'] = {
        'skill_id': skill_id,
        'content': skill_content,
        'output_path': output_path,
    }
    state['output_mode'] = 'skill'
    state['confidence'] = 0.8
    state['history'].append({
        'lane': 'live_docs_to_skill',
        'url': url,
        'skill_id': skill_id,
        'output_path': output_path,
    })
    
    return state


def _extract_url(query: str) -> Optional[str]:
    """Extract URL from query."""
    url_pattern = r'https?://[^\s]+'
    match = re.search(url_pattern, query)
    return match.group(0) if match else None


def _extract_skill_name(url: str) -> str:
    """Extract skill name from URL."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    path = parsed.path.strip('/')
    
    if '/' in path:
        path = path.split('/')[-1]
    
    name = re.sub(r'[^a-zA-Z0-9_-]', '-', path)
    return name[:50] or 'doc-skill'


def _fetch_doc_content(url: str) -> Optional[str]:
    """Fetch content from URL."""
    try:
        import requests
        response = requests.get(url, timeout=30, headers={
            'User-Agent': 'Deterministic-Brain/1.0'
        })
        if response.status_code == 200:
            return response.text
    except Exception:
        return None
    return None


def _convert_to_skill(doc_content: str, source_url: str) -> str:
    """Convert documentation content to skill format."""
    title = _extract_title(doc_content)
    sections = _extract_sections(doc_content)
    
    lines = [
        "---",
        f"skill: {title.lower().replace(' ', '-')}",
        "version: 1.0",
        "backend: local",
        "description: Generated from live documentation",
        "inputs: {}",
        "tools: [web_fetch, file_write]",
        "audit: []",
        "monte_carlo: false",
        "---",
        "",
        f"# {title}",
        "",
        f"Generated from: {source_url}",
        "",
    ]
    
    if sections:
        lines.append("## Steps")
        for i, section in enumerate(sections[:10], 1):
            lines.append(f"### Step {i}")
            lines.append(section.strip()[:500])
            lines.append("")
    
    lines.append("## Usage")
    lines.append("This skill was auto-generated from documentation.")
    lines.append("Review and refine the steps before use.")
    
    return '\n'.join(lines)


def _extract_title(doc_content: str) -> str:
    """Extract title from document."""
    h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', doc_content, re.IGNORECASE | re.DOTALL)
    if h1_match:
        return _strip_tags(h1_match.group(1))
    
    title_match = re.search(r'<title>(.*?)</title>', doc_content, re.IGNORECASE)
    if title_match:
        return title_match.group(1)
    
    return "Auto-generated Skill"


def _extract_sections(doc_content: str) -> List[str]:
    """Extract sections from document."""
    html_sections = re.findall(
        r'<h[2-4][^>]*>(.*?)</h[2-4]>(.*?)(?=<h[2-4]|$)',
        doc_content,
        re.IGNORECASE | re.DOTALL
    )
    
    sections = []
    for heading, content in html_sections:
        heading_text = _strip_tags(heading).strip()
        content_text = _strip_tags(content).strip()
        
        if len(content_text) > 50:
            sections.append(f"**{heading_text}**: {content_text[:400]}")
    
    return sections


def _strip_tags(html: str) -> str:
    """Remove HTML tags from string."""
    text = re.sub(r'<[^>]+>', '', html)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()
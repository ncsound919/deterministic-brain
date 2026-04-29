from __future__ import annotations
"""
BASH_CLASSIFIER — Bash command safety classifier.

Before any shell command is executed, this classifier evaluates it
for safety and assigns a risk level. HIGH-risk commands are blocked
unless explicit approval is granted.

Risk tiers:
- SAFE:    Read-only ops, directory listing, basic queries
- CAUTION: File writes, network calls, installs
- DANGER:  rm -rf, curl|sh, sudo, credential-touching, exfil patterns
- BLOCKED: Hardcoded deny-list (always denied regardless of approval)
"""
import re
from typing import NamedTuple

class Classification(NamedTuple):
    tier: str       # SAFE | CAUTION | DANGER | BLOCKED
    blocked: bool
    reason: str

_BLOCKED_PATTERNS = [
    r'rm\s+-rf\s+/',
    r':(){ :|:& };:',      # fork bomb
    r'dd if=/dev/zero of=/dev/sd',
    r'mkfs\.',
    r'>(\s*)*/etc/passwd',
    r'curl.*\|.*sh',
    r'wget.*\|.*sh',
    r'python.*-c.*exec',
]

_DANGER_PATTERNS = [
    r'\brm -rf\b',
    r'\bsudo\b',
    r'\bchmod 777\b',
    r'\beval\b',
    r'\bcurl\b.*-o',
    r'\bwget\b',
    r'\bssh\b',
    r'\bscp\b',
    r'\benv\b.*KEY',
    r'\bexport\b.*PASSWORD',
    r'\bcat\b.*/etc/',
]

_CAUTION_PATTERNS = [
    r'\bpip install\b',
    r'\bnpm install\b',
    r'\bwrite\b|>\s*\w+\.py',
    r'\bgit push\b',
    r'\bgit commit\b',
    r'\bdocker run\b',
    r'\bmkdir\b',
]


def classify(command: str) -> Classification:
    cmd = command.strip()
    for pat in _BLOCKED_PATTERNS:
        if re.search(pat, cmd):
            return Classification('BLOCKED', True, f'Matches blocked pattern: {pat}')
    for pat in _DANGER_PATTERNS:
        if re.search(pat, cmd, re.IGNORECASE):
            return Classification('DANGER', False, f'Dangerous operation detected: {pat}')
    for pat in _CAUTION_PATTERNS:
        if re.search(pat, cmd, re.IGNORECASE):
            return Classification('CAUTION', False, f'Elevated privilege or write operation')
    return Classification('SAFE', False, 'No dangerous patterns detected')


def is_safe(command: str) -> bool:
    return classify(command).tier == 'SAFE'


def requires_approval(command: str) -> bool:
    c = classify(command)
    return c.tier in ('DANGER',) or c.blocked

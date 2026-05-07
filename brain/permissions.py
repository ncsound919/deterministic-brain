from __future__ import annotations

def default_permissions() -> dict:
    return {
        'allow_code_execution': True,
        'allow_browser': True,
        'allow_external_tools': True,
        'require_confirmation_for_side_effects': True,
    }

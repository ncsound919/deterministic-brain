from __future__ import annotations

def decompose_goal(query: str) -> list:
    q = query.lower()
    if 'dashboard' in q:
        return ['navigate_to_dashboard', 'inspect_layout', 'extract_metrics', 'summarize_findings']
    if 'login' in q:
        return ['locate_login_form', 'fill_credentials', 'submit_form', 'verify_session']
    if 'search' in q:
        return ['locate_search_input', 'type_query', 'submit_search', 'extract_results']
    return ['observe_current_state', 'identify_target', 'propose_action', 'execute_and_verify']

from __future__ import annotations

def get_dom_snapshot(url: str = 'https://example.com') -> dict:
    return {
        'url': url, 'title': 'Example Page',
        'elements': [
            {'type': 'button', 'id': 'login-btn', 'text': 'Login', 'visible': True},
            {'type': 'input', 'id': 'search-input', 'placeholder': 'Search...', 'visible': True},
            {'type': 'link', 'id': 'reports-link', 'text': 'Reports', 'visible': True},
            {'type': 'nav', 'id': 'main-nav', 'children': ['dashboard', 'analytics', 'settings'], 'visible': True},
        ],
        'forms': [{'id': 'search-form', 'action': '/search', 'method': 'GET'}],
        'accessible': True,
    }

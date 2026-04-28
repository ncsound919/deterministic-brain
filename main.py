from orchestration.langgraph_app import build_app

if __name__ == '__main__':
    brain = build_app()
    queries = [
        ('coding', 'Write python code for a deterministic router'),
        ('business_logic', 'Create a business rule approval policy for budget requests'),
        ('agent_brain', 'Use browser agent to navigate to the dashboard and extract metrics'),
        ('tool_calling', 'Call a tool to validate data'),
        ('cross_domain', 'Analyze cross-domain trend signals across AI regulation supply logistics and energy'),
    ]
    for expected_lane, q in queries:
        r = brain.run(q)
        ok = '\u2713' if r['status'] == 'ok' else '\u2717'
        print(f"{ok} [{r['lane']:>15}]  conf={r['confidence']:.2f}  mode={r['output_mode']:<8}  {q[:60]}")
        for v in r.get('verification_results', []):
            mark = '  \u2713' if v['passed'] else '  \u2717'
            print(f"     {mark}  {v['stage']}: {v['reason']}")
        print()

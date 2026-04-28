from __future__ import annotations

from planners.browser_planner import plan_browser_task
from tools.browser.controller import observe_browser_state, propose_browser_action
from tools.browser.policies import allow_browser_action
from tools.browser.session import BrowserSession
from lanes.agent_brain.goal_stack import decompose_goal
from lanes.agent_brain.observer import verify_action_outcome

def run(state: dict) -> dict:
    plan = plan_browser_task(state['query'])
    goals = decompose_goal(state['query'])
    session = BrowserSession()
    observation = observe_browser_state(state['query'])
    proposed = propose_browser_action(state['query'], observation)
    approved = allow_browser_action(proposed['args']['action'])
    proposed['approved'] = approved
    session.record_action(proposed)
    outcome = verify_action_outcome(proposed, goals[0])
    state['tool_calls'] = [proposed]
    state['browser_sessions'] = {session.session_id: session.to_dict()}
    state['working_memory']['agent_plan'] = plan
    state['working_memory']['goal_stack'] = goals
    state['working_memory']['observation'] = observation
    state['working_memory']['outcome'] = outcome
    if approved:
        state['final_output'] = ('Agent plan: ' + str(goals) + '\nAction: ' +
            proposed['args']['action'] + ' on ' + proposed['args']['target'] +
            '\nOutcome: ' + ('success' if outcome['success'] else 'failed'))
        state['status'] = 'ok'
        state['confidence'] = 0.91
    else:
        state['final_output'] = 'Browser action blocked by policy: ' + proposed['args']['action']
        state['status'] = 'failed'
        state['confidence'] = 0.4
    state['output_mode'] = 'action'
    state['history'].append({'lane': 'agent_brain', 'goals': goals, 'approved': approved, 'session': session.session_id})
    return state

from __future__ import annotations
from tools.llm.router import chat
from planners.browser_planner import plan_browser_task
from tools.browser.controller import observe_browser_state, propose_browser_action
from tools.browser.policies import allow_browser_action
from tools.browser.session import BrowserSession
from lanes.agent_brain.goal_stack import decompose_goal
from lanes.agent_brain.observer import verify_action_outcome

_SYSTEM = """You are an autonomous browser agent.
Given an observation of the current browser state and a goal, produce a precise action plan.
Format:
ACTION: <navigate | click | fill | extract | submit | scroll>
TARGET: <CSS selector, URL, or element description>
VALUE: <value to fill or search term, if applicable>
GOAL_STEP: <which goal step this action accomplishes>
CONFIDENCE: <0.0-1.0>
RATIONALE: <one sentence>"""

def run(state: dict) -> dict:
    plan = plan_browser_task(state['query'])
    goals = decompose_goal(state['query'])
    session = BrowserSession()
    observation = observe_browser_state(state['query'])

    user_msg = (
        f"Goal: {state['query']}\n"
        f"Goal steps: {goals}\n"
        f"Current observation: {observation}\n\n"
        "Produce the next browser action."
    )
    llm_action = chat(system=_SYSTEM, user=user_msg, lane='agent_brain')

    # Merge LLM action plan with the deterministic proposal
    proposed = propose_browser_action(state['query'], observation)
    proposed['llm_plan'] = llm_action
    approved = allow_browser_action(proposed['args']['action'])
    proposed['approved'] = approved
    session.record_action(proposed)
    outcome = verify_action_outcome(proposed, goals[0])

    state['tool_calls'] = [proposed]
    state['browser_sessions'] = {session.session_id: session.to_dict()}
    state['working_memory']['agent_plan'] = plan
    state['working_memory']['goal_stack'] = goals
    state['working_memory']['observation'] = observation
    state['working_memory']['llm_action'] = llm_action
    state['working_memory']['outcome'] = outcome

    if approved:
        state['final_output'] = (
            f'Agent plan:\n{llm_action}\n\n'
            f'Goals: {goals}\n'
            f'Outcome: {"success" if outcome["success"] else "failed"}'
        )
        state['status'] = 'ok'
        state['confidence'] = 0.91
    else:
        state['final_output'] = 'Browser action blocked by policy: ' + proposed['args']['action']
        state['status'] = 'failed'
        state['confidence'] = 0.4

    state['output_mode'] = 'action'
    state['history'].append({'lane': 'agent_brain', 'goals': goals, 'approved': approved,
                             'session': session.session_id, 'llm_backend': 'claude_sonnet_via_openrouter'})
    return state

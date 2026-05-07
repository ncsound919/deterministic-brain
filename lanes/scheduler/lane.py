"""Scheduler Lane — manages periodic tasks and workflows."""
from __future__ import annotations
from typing import Dict, List
from features.scheduler import get_scheduler, schedule_task as schedule_task_fn


def run(state: dict) -> dict:
    """Run scheduler lane.
    
    Expected state keys:
    - query: str - the original user query
    - action: str - "list", "schedule", "unschedule", "results", "start", "stop"
    - task_config: dict - task configuration for scheduling
    """
    query = state.get('query', '')
    action = state.get('action', 'list')
    task_config = state.get('task_config', {})
    
    scheduler = get_scheduler()
    
    if action == "list":
        tasks = scheduler.list_tasks()
        state['final_output'] = {
            'tasks': tasks,
            'count': len(tasks),
            'running': scheduler.is_running(),
        }
        state['candidate_artifacts'] = [{
            'id': 'scheduler-tasks',
            'kind': 'scheduler',
            'content': tasks,
        }]
        
    elif action == "schedule":
        task_name = task_config.get('name', f'task_{len(scheduler.list_tasks())}')
        skill = task_config.get('skill', 'unknown')
        cron = task_config.get('cron')
        interval = task_config.get('interval_seconds')
        inputs = task_config.get('inputs', {})
        notify_email = task_config.get('notify_email')
        notify_webhook = task_config.get('notify_webhook')
        
        task_id = schedule_task_fn(
            name=task_name,
            skill=skill,
            cron_expr=cron,
            interval_seconds=interval,
            inputs=inputs,
            notify_email=notify_email,
            notify_webhook=notify_webhook,
        )
        
        state['final_output'] = {
            'status': 'scheduled',
            'task_id': task_id,
        }
        
    elif action == "unschedule":
        task_name = task_config.get('name')
        removed = scheduler.remove_task(task_name)
        state['final_output'] = {
            'status': 'removed' if removed else 'not_found',
            'task_name': task_name,
        }
        
    elif action == "results":
        task_name = task_config.get('name')
        results = scheduler.get_results(task_name)
        state['final_output'] = {
            'results': results,
        }
        
    elif action == "start":
        scheduler.start()
        state['final_output'] = {'status': 'started'}
        
    elif action == "stop":
        scheduler.stop()
        state['final_output'] = {'status': 'stopped'}
    
    else:
        state['final_output'] = {'error': f'Unknown action: {action}'}
        state['status'] = 'failed'
    
    state['confidence'] = 0.95
    state['output_mode'] = 'scheduler'
    state['history'].append({
        'lane': 'scheduler',
        'action': action,
    })
    
    return state
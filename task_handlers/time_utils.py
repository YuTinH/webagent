from datetime import datetime, timedelta

def get_sim_time(env):
    """Get the current simulation time from env, default to system real time if not set."""
    return datetime.fromisoformat(env.get('system_time', datetime.now().isoformat()))

def advance_time(env, days=0, hours=0):
    """Advance the simulation time by delta."""
    current = get_sim_time(env)
    new_time = current + timedelta(days=days, hours=hours)
    env['system_time'] = new_time.isoformat()
    return env

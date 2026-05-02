def deep_merge(a, b):
    """Deep merge two dictionaries"""
    if isinstance(a, dict) and isinstance(b, dict):
        r = dict(a)
        for k, v in b.items():
            r[k] = deep_merge(r.get(k), v) if k in r else v
        return r
    return b


def write_memory_entries(execute_db_fn, entries, ts, source, retries=3):
    """Persist memory_kv entries with small bounded retries."""
    last_error = None
    payload = list(entries or [])
    for _ in range(max(1, int(retries))):
        try:
            for key, value in payload:
                execute_db_fn(
                    "INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                    [str(key), str(value), ts, source, 1.0],
                )
            return True
        except Exception as exc:
            last_error = exc
    if last_error is not None:
        print(f"ERROR: memory_kv write failed for source={source}: {last_error}")
    return False

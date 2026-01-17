import time

def handler(payload):
    """
    Simple task that adds two numbers and sleeps for 2 seconds.
    Used for CI/CD autoscaling tests.
    
    Expected payload format from worker:
    {
        "data": {
            "a": 5,
            "b": 10
        },
        "_run_id": "some-uuid"
    }
    """
    start_time = time.time()
    
    # Extract data dict from payload
    data = payload.get("data", {})
    run_id = payload.get("_run_id", "unknown")
    
    # Extract values or use defaults
    a = data.get("a", 1)
    b = data.get("b", 2)
    
    # Simple computation
    result = a + b
    
    # Sleep to simulate some work (helps test autoscaling)
    time.sleep(2)
    
    execution_time = time.time() - start_time
    
    return {
        "status": "success",
        "operation": "addition",
        "run_id": run_id,
        "input_a": a,
        "input_b": b,
        "result": result,
        "execution_time_seconds": round(execution_time, 2)
    }

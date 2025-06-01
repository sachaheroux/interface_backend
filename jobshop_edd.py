from collections import defaultdict
from typing import List, Dict, Any

def planifier_jobshop_edd(job_names: List[str], machine_names: List[str], jobs_data: List[List[List[float]]], due_dates: List[float]) -> Dict[str, Any]:
    machine_time = defaultdict(float)
    job_time = defaultdict(float)
    machines = defaultdict(list)
    completion_times = defaultdict(float)
    cumulative_delay = 0.0

    # Format: (due_date, processing_time, operation_index, job_index, machine)
    jobs = [(due_dates[j], float(t), i, j, int(m)) 
            for j, job in enumerate(jobs_data) 
            for i, (m, t) in enumerate(job)]
    job_indices = defaultdict(int)

    time = 0.0
    while jobs:
        available_tasks = [(due_date, t, i, j, m) for due_date, t, i, j, m in jobs 
                          if i == job_indices[j] and max(machine_time[m], job_time[j]) <= time]
        if not available_tasks:
            time += 0.1
            time = round(time, 2)
            continue

        # Trier par EDD (Earliest Due Date)
        available_tasks.sort()
        due_date, t, i, j, m = available_tasks[0]

        start_time = max(machine_time[m], job_time[j])
        end_time = start_time + t
        machines[m].append({
            "job": job_names[j],
            "task_index": i,
            "start": start_time,
            "end": end_time
        })

        job_indices[j] += 1
        machine_time[m] = end_time
        job_time[j] = end_time
        jobs.remove((due_date, t, i, j, m))

        completion_times[j] = job_time[j]
        delay = max(completion_times[j] - due_dates[j], 0)
        cumulative_delay += delay

        time += 0.1
        time = round(time, 2)

    makespan = max(machine_time.values())
    flowtime = sum(completion_times.values())

    schedule = []
    for m_index, tasks in machines.items():
        machine_name = machine_names[m_index]
        for task in tasks:
            schedule.append({
                "job": task["job"],
                "machine": machine_name,
                "start": task["start"],
                "end": task["end"]
            })

    return {
        "schedule": schedule,
        "metrics": {
            "makespan": makespan,
            "flowtime": flowtime,
            "retard_cumule": cumulative_delay
        }
    } 
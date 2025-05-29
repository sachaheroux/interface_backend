from collections import defaultdict
from typing import List, Dict, Any
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")
import io
import base64

def planifier_jobshop_spt(job_names: List[str], machine_names: List[str], jobs_data: List[List[List[float]]], due_dates: List[float]) -> Dict[str, Any]:
    machine_time = defaultdict(int)
    job_time = defaultdict(int)
    machines = defaultdict(list)
    completion_times = defaultdict(int)
    cumulative_delay = 0

    jobs = [(t, i, j, m) for j, job in enumerate(jobs_data) for i, (m, t) in enumerate(job)]
    job_indices = defaultdict(int)

    time = 0
    while jobs:
        available_tasks = [(t, i, j, m) for t, i, j, m in jobs if i == job_indices[j] and 
                           max(machine_time[m], job_time[j]) <= time]
        if not available_tasks:
            time += 1
            continue

        available_tasks.sort()
        t, i, j, m = available_tasks[0]

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
        jobs.remove((t, i, j, m))

        completion_times[j] = job_time[j]
        delay = max(completion_times[j] - due_dates[j], 0)
        cumulative_delay += delay

        time += 1

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

def generer_gantt_jobshop(schedule: List[Dict[str, Any]]) -> str:
    machines = list({task["machine"] for task in schedule})
    machines.sort()
    machine_index = {m: i for i, m in enumerate(machines)}

    fig, ax = plt.subplots(figsize=(10, len(machines)))
    for task in schedule:
        y = machine_index[task["machine"]]
        ax.broken_barh(
            [(task["start"], task["end"] - task["start"])],
            (y - 0.4, 0.8),
            facecolors=f"C{hash(task['job']) % 10}"
        )
        ax.text(
            task["start"] + (task["end"] - task["start"]) / 2,
            y,
            task["job"],
            ha='center', va='center', color='white', fontsize=8
        )

    ax.set_yticks(range(len(machines)))
    ax.set_yticklabels(machines)
    ax.set_xlabel("Temps")
    ax.set_title("Diagramme de Gantt - Jobshop SPT")
    ax.grid(True)

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')

# backend/edd.py
from collections import defaultdict
from operator import itemgetter

def schedule(jobs_data, due_dates):
    machine_time = defaultdict(int)
    job_time = defaultdict(int)
    machines = defaultdict(list)
    completion_times = {}

    # Tri des jobs selon la date due (EDD)
    job_due_dates = [(j, due_dates[j]) for j in range(len(jobs_data))]
    sorted_jobs = sorted(job_due_dates, key=itemgetter(1))
    sequence = [j for j, _ in sorted_jobs]

    cumulative_delay = 0

    for j in sequence:
        job = jobs_data[j]
        for i, (m, t) in enumerate(job):
            start_time = max(machine_time[m], job_time[j])
            end_time = start_time + t

            machines[m].append({
                "job": j,
                "task": i,
                "start": start_time,
                "duration": t
            })

            machine_time[m] = end_time
            job_time[j] = end_time

        completion_times[j] = job_time[j]
        delay = max(job_time[j] - due_dates[j], 0)
        cumulative_delay += delay

    makespan = max(machine_time.values())
    flowtime = sum(completion_times.values()) / len(completion_times)

    return {
        "makespan": makespan,
        "flowtime": flowtime,
        "retard_cumule": cumulative_delay,
        "completion_times": completion_times,
        "machines": machines
    }
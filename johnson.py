# backend/johnson.py
from collections import defaultdict

def johnson_schedule(tasks):
    tasks = sorted([(min(time), i, time) for i, time in enumerate(tasks)])
    schedule = [0] * len(tasks)
    start, end = 0, len(tasks) - 1

    for _, original_i, times in tasks:
        if times[0] <= times[1]:
            schedule[start] = original_i
            start += 1
        else:
            schedule[end] = original_i
            end -= 1

    return schedule

def compute_metrics(schedule, tasks, due_dates):
    m1 = m2 = 0
    completion_times = {}
    cumulative_delay = 0

    for i in schedule:
        m1 += tasks[i][0]
        m2 = max(m1, m2) + tasks[i][1]
        completion_times[i] = m2
        delay = max(0, m2 - due_dates[i])
        cumulative_delay += delay

    flowtime = sum(completion_times.values()) / len(completion_times)
    makespan = max(completion_times.values())

    return schedule, completion_times, makespan, flowtime, cumulative_delay

def schedule(jobs_data, due_dates):
    sequence = johnson_schedule(jobs_data)
    sequence, completion_times, makespan, flowtime, cumulative_delay = compute_metrics(sequence, jobs_data, due_dates)

    machines = defaultdict(list)
    m1 = m2 = 0
    for j in sequence:
        start_m1 = m1
        end_m1 = start_m1 + jobs_data[j][0]
        m1 = end_m1
        machines[0].append({"job": j, "task": 0, "start": start_m1, "duration": jobs_data[j][0]})

        start_m2 = max(end_m1, m2)
        end_m2 = start_m2 + jobs_data[j][1]
        m2 = end_m2
        machines[1].append({"job": j, "task": 1, "start": start_m2, "duration": jobs_data[j][1]})

    return {
        "sequence": [j + 1 for j in sequence],
        "completion_times": {f"Job {j}": t for j, t in completion_times.items()},
        "makespan": makespan,
        "flowtime": flowtime,
        "retard_cumule": cumulative_delay,
        "machines": machines
    }

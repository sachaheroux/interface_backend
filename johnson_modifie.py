# backend/johnson_modifie.py
from collections import defaultdict
from typing import List, Tuple
import numpy as np

def backtrack(tasks, start, end, schedule):
    if not tasks:
        yield [i for i in schedule if i != 0]
    else:
        min_time = min(min(time) for _, _, time in tasks)
        for i, original_i, times in [(i, original_i, times) for i, (_, original_i, times) in enumerate(tasks) if min(times) == min_time]:
            new_tasks = tasks[:i] + tasks[i+1:]
            if times[0] == min_time:
                new_schedule = schedule[:start] + [original_i+1] + schedule[start:]
                yield from backtrack(new_tasks, start+1, end, new_schedule)
            if times[1] == min_time:
                new_schedule = schedule[:end+1] + [original_i+1] + schedule[end+1:]
                yield from backtrack(new_tasks, start, end-1, new_schedule)

def johnson_schedule(tasks):
    tasks = sorted([(min(time), i, time) for i, time in enumerate(tasks)])
    return [list(x) for x in set(tuple(x) for x in backtrack(tasks, 0, len(tasks)-1, [0]*len(tasks)))]

def makespan(schedule, tasks):
    m = [0]*len(tasks[0])
    for i in schedule:
        for j in range(len(tasks[0])):
            m[j] = max(m[j], m[j-1] if j > 0 else 0) + tasks[i-1][j]
    return max(m)

def flowtime(schedule, tasks):
    m = [0]*len(tasks[0])
    completion_times = {}
    for idx, i in enumerate(schedule):
        for j in range(len(tasks[0])):
            m[j] = max(m[j], m[j-1] if j > 0 else 0) + tasks[i-1][j]
        completion_times[i-1] = max(m)
    return sum(completion_times.values()) / len(schedule), completion_times

def cumulative_delay(schedule, tasks, due_dates):
    schedule_due_dates = [due_dates[i-1] for i in schedule]
    m = [0]*len(tasks[0])
    delays = []
    for i, due_date in zip(schedule, schedule_due_dates):
        for j in range(len(tasks[0])):
            m[j] = max(m[j], m[j-1] if j > 0 else 0) + tasks[i-1][j]
        delay = max(0, max(m) - due_date)
        delays.append(delay)
    return sum(delays)

def generate_sub_problems(tasks: List[List[int]]) -> List[Tuple[List[float], List[float]]]:
    num_machines = len(tasks[0])
    sub_problems = []

    for i in range(1, num_machines):
        pseudo_machine_1 = [sum(job[:i]) for job in tasks]
        pseudo_machine_2 = [sum(job[-i:]) for job in tasks]
        sub_problems.append((pseudo_machine_1, pseudo_machine_2))

    return sub_problems

def schedule(jobs_data, due_dates):
    sub_problems = generate_sub_problems(jobs_data)
    best_schedules = []

    for sub_problem in sub_problems:
        pseudo_tasks = list(zip(*sub_problem))
        solutions = johnson_schedule(pseudo_tasks)
        best_schedule = min(solutions, key=lambda x: makespan(x, jobs_data))
        best_schedules.append(best_schedule)

    best_global_schedule = min(best_schedules, key=lambda x: makespan(x, jobs_data))
    ftime, completion_times = flowtime(best_global_schedule, jobs_data)
    delay = cumulative_delay(best_global_schedule, jobs_data, due_dates)
    mspan = makespan(best_global_schedule, jobs_data)

    machines = defaultdict(list)
    m = [0]*len(jobs_data[0])
    for j in best_global_schedule:
        job = jobs_data[j-1]
        for i in range(len(job)):
            start_time = max(m[i], m[i-1] if i > 0 else 0)
            machines[i].append({"job": j-1, "task": i, "start": start_time, "duration": job[i]})
            m[i] = start_time + job[i]

    return {
        "sequence": best_global_schedule,
        "completion_times": {f"Job {j}": t for j, t in completion_times.items()},
        "makespan": mspan,
        "flowtime": ftime,
        "retard_cumule": delay,
        "machines": machines
    }

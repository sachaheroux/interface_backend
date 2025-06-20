import collections
from ortools.sat.python import cp_model
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from datetime import datetime
import os
import numpy as np

def schedule(jobs_data, due_dates):
    # ✅ Convertir en int pour OR-Tools (qui ne supporte pas les floats)
    jobs_data = [
        [(int(machine), int(round(duration))) for machine, duration in job]
        for job in jobs_data
    ]
    due_dates = [int(round(d)) for d in due_dates]

    machines_count = 1 + max(task[0] for job in jobs_data for task in job)
    all_machines = range(machines_count)
    horizon = sum(task[1] for job in jobs_data for task in job)

    model = cp_model.CpModel()
    task_type = collections.namedtuple('task_type', 'start end interval')

    all_tasks = {}
    machine_to_intervals = collections.defaultdict(list)

    for job_id, job in enumerate(jobs_data):
        for task_id, (machine, duration) in enumerate(job):
            suffix = f'_{job_id}_{task_id}'
            start_var = model.NewIntVar(0, horizon, f'start{suffix}')
            end_var = model.NewIntVar(0, horizon, f'end{suffix}')
            
            # OR-Tools supporte les intervalles de durée 0
            interval_var = model.NewIntervalVar(start_var, duration, end_var, f'interval{suffix}')
            all_tasks[job_id, task_id] = task_type(start=start_var, end=end_var, interval=interval_var)
            
            # Ajouter toutes les tâches aux contraintes de non-chevauchement
            # Les tâches de durée 0 ne posent pas de problème à OR-Tools
            machine_to_intervals[machine].append(interval_var)

    for machine in all_machines:
        model.AddNoOverlap(machine_to_intervals[machine])

    for job_id, job in enumerate(jobs_data):
        for task_id in range(len(job) - 1):
            model.Add(all_tasks[job_id, task_id + 1].start >= all_tasks[job_id, task_id].end)

    obj_var = model.NewIntVar(0, horizon, 'makespan')
    model.AddMaxEquality(obj_var, [all_tasks[job_id, len(job) - 1].end for job_id, job in enumerate(jobs_data)])
    model.Minimize(obj_var)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        raise ValueError("Aucune solution trouvée par le solveur CP.")

    assigned_jobs = collections.defaultdict(list)
    completion_times = [0] * len(jobs_data)
    total_delay = 0

    for job_id, job in enumerate(jobs_data):
        for task_id, (machine, duration) in enumerate(job):
            start_time = solver.Value(all_tasks[job_id, task_id].start)
            assigned_jobs[machine].append({
                "job": job_id,
                "task": task_id,
                "start": start_time,
                "duration": duration
            })
            completion_times[job_id] = max(completion_times[job_id], solver.Value(all_tasks[job_id, task_id].end))

    # Trier les tâches par temps de début pour chaque machine
    for machine in assigned_jobs:
        assigned_jobs[machine].sort(key=lambda task: task["start"])

    for j, c in enumerate(completion_times):
        delay = max(0, c - due_dates[j])
        total_delay += delay

    makespan = solver.ObjectiveValue()
    flowtime = sum(completion_times) / len(jobs_data)

    return {
        "makespan": makespan,
        "flowtime": flowtime,
        "retard_cumule": total_delay,
        "completion_times": {f"Job {j}": c for j, c in enumerate(completion_times)},
        "machines": assigned_jobs
    }


def flowshop_contraintes(jobs_data, due_dates, job_names=None, machine_names=None, machines_per_stage=None):
    """
    Fonction principale pour flowshop avec contraintes.
    Utilise seulement l'algorithme de base (une machine par étape).
    """
    print("DEBUG: Flowshop classique avec contraintes")
    return schedule(jobs_data, due_dates)










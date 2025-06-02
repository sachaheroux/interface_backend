import collections
from ortools.sat.python import cp_model

def planifier_jobshop_contraintes(job_names, machine_names, jobs_data, due_dates):
    # Convertir en int pour OR-Tools (qui ne supporte pas les floats)
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
        for task_id, task in enumerate(job):
            machine = task[0]
            duration = task[1]
            suffix = f'_{job_id}_{task_id}'
            start_var = model.NewIntVar(0, horizon, f'start{suffix}')
            end_var = model.NewIntVar(0, horizon, f'end{suffix}')
            interval_var = model.NewIntervalVar(start_var, duration, end_var, f'interval{suffix}')
            all_tasks[job_id, task_id] = task_type(start=start_var, end=end_var, interval=interval_var)
            machine_to_intervals[machine].append(interval_var)

    # Contrainte : pas de chevauchement sur chaque machine
    for machine in all_machines:
        model.AddNoOverlap(machine_to_intervals[machine])

    # Contrainte : précédence des tâches dans chaque job
    for job_id, job in enumerate(jobs_data):
        for task_id in range(len(job) - 1):
            model.Add(all_tasks[job_id, task_id + 1].start >= all_tasks[job_id, task_id].end)

    # Objectif : minimiser le makespan
    obj_var = model.NewIntVar(0, horizon, 'makespan')
    model.AddMaxEquality(obj_var, [
        all_tasks[job_id, len(job) - 1].end
        for job_id, job in enumerate(jobs_data)
    ])
    model.Minimize(obj_var)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        raise ValueError("Aucune solution trouvée par le solveur CP.")

    # Préparer les résultats
    schedule = []
    completion_times = [0] * len(jobs_data)
    total_delay = 0

    for job_id, job in enumerate(jobs_data):
        for task_id, task in enumerate(job):
            machine = task[0]
            duration = task[1]
            start_time = solver.Value(all_tasks[job_id, task_id].start)
            end_time = solver.Value(all_tasks[job_id, task_id].end)
            
            schedule.append({
                "job": job_names[job_id],
                "machine": machine_names[machine],
                "task": task_id,
                "start": start_time,
                "end": end_time,
                "duration": duration
            })
            
            completion_times[job_id] = max(completion_times[job_id], end_time)

    # Calculer les métriques
    makespan = solver.ObjectiveValue()
    flowtime = sum(completion_times) / len(jobs_data)
    
    for job_id, completion_time in enumerate(completion_times):
        delay = max(0, completion_time - due_dates[job_id])
        total_delay += delay

    return {
        "makespan": makespan,
        "flowtime": flowtime,
        "retard_cumule": total_delay,
        "completion_times": {job_names[i]: completion_times[i] for i in range(len(jobs_data))},
        "schedule": schedule
    } 
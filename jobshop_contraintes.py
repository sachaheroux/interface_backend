import collections
from ortools.sat.python import cp_model

def planifier_jobshop_contraintes(job_names, machine_names, jobs_data, due_dates, setup_times=None):
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
    machine_to_tasks = collections.defaultdict(list)  # Pour gérer les temps de setup

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
            machine_to_tasks[machine].append((job_id, task_id, start_var, end_var, duration))

    # Contrainte : pas de chevauchement sur chaque machine
    for machine in all_machines:
        model.AddNoOverlap(machine_to_intervals[machine])

    # Contrainte : précédence des tâches dans chaque job
    for job_id, job in enumerate(jobs_data):
        for task_id in range(len(job) - 1):
            model.Add(all_tasks[job_id, task_id + 1].start >= all_tasks[job_id, task_id].end)

    # Contraintes de temps de setup si spécifiées
    if setup_times:
        # Convertir les temps de setup en entiers
        setup_times_int = {}
        for machine_id, machine_setups in setup_times.items():
            machine_id_int = int(machine_id)
            setup_times_int[machine_id_int] = {}
            for from_job, to_jobs in machine_setups.items():
                from_job_int = int(from_job)
                setup_times_int[machine_id_int][from_job_int] = {}
                for to_job, setup_time in to_jobs.items():
                    to_job_int = int(to_job)
                    setup_times_int[machine_id_int][from_job_int][to_job_int] = int(round(float(setup_time)))
        
        # Ajouter les contraintes de setup pour chaque machine
        for machine_id, tasks_on_machine in machine_to_tasks.items():
            if machine_id in setup_times_int and len(tasks_on_machine) > 1:
                # Créer des variables booléennes pour l'ordre des tâches
                for i, (job_i, task_i, start_i, end_i, duration_i) in enumerate(tasks_on_machine):
                    for j, (job_j, task_j, start_j, end_j, duration_j) in enumerate(tasks_on_machine):
                        if i != j:
                            # Variable booléenne : task_i précède task_j sur cette machine
                            precedence_var = model.NewBoolVar(f'precedence_{machine_id}_{job_i}_{task_i}_{job_j}_{task_j}')
                            
                            # Si task_i précède task_j, alors end_i + setup_time <= start_j
                            setup_time = setup_times_int.get(machine_id, {}).get(job_i, {}).get(job_j, 0)
                            if setup_time > 0:
                                model.Add(start_j >= end_i + setup_time).OnlyEnforceIf(precedence_var)
                            else:
                                model.Add(start_j >= end_i).OnlyEnforceIf(precedence_var)
                            
                            # Si task_j précède task_i, alors end_j + setup_time <= start_i
                            setup_time_reverse = setup_times_int.get(machine_id, {}).get(job_j, {}).get(job_i, 0)
                            if setup_time_reverse > 0:
                                model.Add(start_i >= end_j + setup_time_reverse).OnlyEnforceIf(precedence_var.Not())
                            else:
                                model.Add(start_i >= end_j).OnlyEnforceIf(precedence_var.Not())

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
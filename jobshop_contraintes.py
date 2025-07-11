import collections
from ortools.sat.python import cp_model

def planifier_jobshop_contraintes(job_names, machine_names, jobs_data, due_dates, setup_times=None, release_times=None):
    # Convertir en int pour OR-Tools (qui ne supporte pas les floats)
    jobs_data = [
        [(int(machine), int(round(duration))) for machine, duration in job]
        for job in jobs_data
    ]
    due_dates = [int(round(d)) for d in due_dates]
    
    # Traiter les temps d'arrivée (release times)
    release_times_int = [0] * len(jobs_data)  # Par défaut, tous les jobs arrivent à t=0
    if release_times and isinstance(release_times, (list, dict)):
        if isinstance(release_times, list):
            # Si c'est une liste, utiliser directement
            for i, release_time in enumerate(release_times):
                if i < len(release_times_int):
                    try:
                        release_times_int[i] = max(0, int(round(float(release_time))))
                    except (ValueError, TypeError):
                        release_times_int[i] = 0
        elif isinstance(release_times, dict):
            # Si c'est un dictionnaire, mapper par index de job
            for job_idx, release_time in release_times.items():
                try:
                    job_idx_int = int(job_idx)
                    if 0 <= job_idx_int < len(release_times_int):
                        release_times_int[job_idx_int] = max(0, int(round(float(release_time))))
                except (ValueError, TypeError):
                    continue

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
    
    # Contraintes de temps d'arrivée (release times)
    for job_id, job in enumerate(jobs_data):
        if len(job) > 0:  # S'assurer qu'il y a au moins une tâche
            # La première tâche du job ne peut pas commencer avant son temps d'arrivée
            model.Add(all_tasks[job_id, 0].start >= release_times_int[job_id])

    # Contraintes de temps de setup si spécifiées
    if setup_times and isinstance(setup_times, dict) and len(setup_times) > 0:
        # Convertir les temps de setup en entiers (gère les floats et les zéros)
        setup_times_int = {}
        for machine_id, machine_setups in setup_times.items():
            if machine_setups and isinstance(machine_setups, dict):
                machine_id_int = int(machine_id)
                setup_times_int[machine_id_int] = {}
                for from_job, to_jobs in machine_setups.items():
                    if to_jobs and isinstance(to_jobs, dict):
                        from_job_int = int(from_job)
                        setup_times_int[machine_id_int][from_job_int] = {}
                        for to_job, setup_time in to_jobs.items():
                            to_job_int = int(to_job)
                            # Convertir en float d'abord, puis arrondir et convertir en int
                            # Cela gère les strings, floats, et ints
                            try:
                                setup_time_float = float(setup_time) if setup_time is not None else 0.0
                                setup_time_int = int(round(setup_time_float))
                                # Accepter les temps de setup >= 0 (y compris zéro)
                                setup_times_int[machine_id_int][from_job_int][to_job_int] = max(0, setup_time_int)
                            except (ValueError, TypeError):
                                # Si conversion impossible, utiliser 0
                                setup_times_int[machine_id_int][from_job_int][to_job_int] = 0
        
        # Ajouter les contraintes de setup pour chaque machine
        for machine_id, tasks_on_machine in machine_to_tasks.items():
            if machine_id in setup_times_int and len(tasks_on_machine) > 1:
                # Créer des variables booléennes pour l'ordre des tâches
                for i, (job_i, task_i, start_i, end_i, duration_i) in enumerate(tasks_on_machine):
                    for j, (job_j, task_j, start_j, end_j, duration_j) in enumerate(tasks_on_machine):
                        if i != j:
                            # Variable booléenne : task_i précède task_j sur cette machine
                            precedence_var = model.NewBoolVar(f'precedence_{machine_id}_{job_i}_{task_i}_{job_j}_{task_j}')
                            
                            # Si task_i précède task_j, alors start_j >= end_i + setup_time
                            setup_time = setup_times_int.get(machine_id, {}).get(job_i, {}).get(job_j, 0)
                            # Toujours ajouter la contrainte, même si setup_time = 0
                            model.Add(start_j >= end_i + setup_time).OnlyEnforceIf(precedence_var)
                            
                            # Si task_j précède task_i, alors start_i >= end_j + setup_time
                            setup_time_reverse = setup_times_int.get(machine_id, {}).get(job_j, {}).get(job_i, 0)
                            # Toujours ajouter la contrainte, même si setup_time_reverse = 0
                            model.Add(start_i >= end_j + setup_time_reverse).OnlyEnforceIf(precedence_var.Not())

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
    setup_schedule = []  # Pour les temps de setup
    completion_times = [0] * len(jobs_data)
    total_delay = 0

    # Collecter toutes les tâches avec leurs temps de début/fin
    all_task_times = {}
    for job_id, job in enumerate(jobs_data):
        for task_id, task in enumerate(job):
            machine = task[0]
            duration = task[1]
            start_time = solver.Value(all_tasks[job_id, task_id].start)
            end_time = solver.Value(all_tasks[job_id, task_id].end)
            
            all_task_times[(job_id, task_id)] = {
                "job_id": job_id,
                "task_id": task_id,
                "machine": machine,
                "start": start_time,
                "end": end_time,
                "duration": duration
            }
            
            schedule.append({
                "job": job_names[job_id],
                "machine": machine_names[machine],
                "task": task_id,
                "start": start_time,
                "end": end_time,
                "duration": duration
            })
            
            completion_times[job_id] = max(completion_times[job_id], end_time)

    # Calculer les temps de setup réels si spécifiés
    if setup_times and isinstance(setup_times, dict) and len(setup_times) > 0:
        # Grouper les tâches par machine
        tasks_by_machine = {}
        for (job_id, task_id), task_info in all_task_times.items():
            machine = task_info["machine"]
            if machine not in tasks_by_machine:
                tasks_by_machine[machine] = []
            tasks_by_machine[machine].append(task_info)
        
        # Pour chaque machine, trier les tâches par temps de début et calculer les setups
        for machine, tasks in tasks_by_machine.items():
            if len(tasks) > 1:
                # Trier par temps de début
                tasks.sort(key=lambda x: x["start"])
                
                # Calculer les temps de setup entre tâches consécutives
                for i in range(len(tasks) - 1):
                    current_task = tasks[i]
                    next_task = tasks[i + 1]
                    
                    # Vérifier s'il y a un temps de setup configuré
                    setup_time_configured = 0
                    
                    # Convertir les clés en int pour la comparaison
                    machine_key = int(machine)
                    current_job_key = int(current_task["job_id"])
                    next_job_key = int(next_task["job_id"])
                    
                    # Chercher dans setup_times avec différents types de clés
                    for m_key in [machine_key, str(machine_key)]:
                        if m_key in setup_times:
                            machine_setups = setup_times[m_key]
                            for from_key in [current_job_key, str(current_job_key)]:
                                if from_key in machine_setups:
                                    from_setups = machine_setups[from_key]
                                    for to_key in [next_job_key, str(next_job_key)]:
                                        if to_key in from_setups:
                                            setup_time_configured = from_setups[to_key]
                                            break
                                    if setup_time_configured > 0:
                                        break
                            if setup_time_configured > 0:
                                break
                    
                    # Convertir en int si nécessaire
                    try:
                        setup_time_configured = int(round(float(setup_time_configured)))
                    except:
                        setup_time_configured = 0
                    
                    # Si il y a un gap entre les tâches et un setup configuré
                    gap_time = next_task["start"] - current_task["end"]
                    if gap_time > 0 and setup_time_configured > 0:
                        # Le temps de setup réel est le minimum entre le gap et le setup configuré
                        actual_setup_time = min(gap_time, setup_time_configured)
                        
                        setup_schedule.append({
                            "machine": machine_names[machine],
                            "from_job": job_names[current_task["job_id"]],
                            "to_job": job_names[next_task["job_id"]],
                            "start": current_task["end"],
                            "end": current_task["end"] + actual_setup_time,
                            "duration": actual_setup_time,
                            "type": "setup"
                        })

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
        "release_times": {job_names[i]: release_times_int[i] for i in range(len(jobs_data))},
        "schedule": schedule,
        "setup_schedule": setup_schedule  # Ajouter les temps de setup
    } 
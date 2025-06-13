import collections
from ortools.sat.python import cp_model
import matplotlib.pyplot as plt
import matplotlib.patches as patches

def debug_jobs_data(jobs_data, due_dates):
    """Debug function to trace data structure"""
    print("=== DEBUG FLOWSHOP FLEXIBLE ===")
    print(f"Nombre de jobs: {len(jobs_data)}")
    print(f"Due dates: {due_dates}")
    
    for job_idx, job in enumerate(jobs_data):
        print(f"Job {job_idx + 1}: {len(job)} étapes")
        for task_idx, alternatives in enumerate(job):
            print(f"  Étape {task_idx + 1}: {len(alternatives)} alternatives")
            for alt_idx, (machine_id, duration) in enumerate(alternatives):
                print(f"    Machine {machine_id}: durée {duration} (type: {type(duration)})")
    print("=" * 35)

def solve_flexible_flowshop(jobs_data, due_dates, machine_names=None, stage_names=None, machines_per_stage=None, machine_priorities=None):
    """
    Résout un problème de flowshop flexible avec machines multiples
    
    Args:
        jobs_data: Liste des jobs, chaque job est une liste de tâches, 
                  chaque tâche est une liste d'alternatives [machine_id, duration]
        due_dates: Liste des dates d'échéance
        machine_names: Noms des machines (optionnel)
        stage_names: Noms des étapes (optionnel)  
        machines_per_stage: Nombre de machines par étape (optionnel)
        machine_priorities: Dictionnaire {machine_id: priority} où priority plus petit = plus prioritaire (optionnel)
    """
    # Convertir toutes les durées en entiers pour OR-Tools
    jobs_data_int = []
    for job in jobs_data:
        job_int = []
        for task in job:
            task_int = []
            for machine_id, duration in task:
                # Convertir en entier (arrondir si nécessaire)
                duration_int = int(round(float(duration)))
                machine_id_int = int(machine_id)
                task_int.append([machine_id_int, duration_int])
            job_int.append(task_int)
        jobs_data_int.append(job_int)
    
    # Convertir les due_dates en entiers aussi
    due_dates_int = [int(round(float(dd))) for dd in due_dates]
    
    # Utiliser les données converties
    jobs_data = jobs_data_int
    due_dates = due_dates_int
    
    model = cp_model.CpModel()

    # Mapper les machines
    machine_map = {}
    display_name_to_id = {}

    for job in jobs_data:
        for task in job:
            if len(task) > 1:
                base = task[0][0]
                suffixes = 'abcdefghijklmnopqrstuvwxyz'
                for i, (machine_id, _) in enumerate(sorted(task)):
                    name = f"Machine {base}" if i == 0 else f"Machine {base}{suffixes[i]}"
                    machine_map[machine_id] = name
                    display_name_to_id[name] = machine_id
            else:
                machine_id, _ = task[0]
                name = f"Machine {machine_id}"
                machine_map[machine_id] = name
                display_name_to_id[name] = machine_id

    machine_display_names = sorted(display_name_to_id.keys(), key=lambda x: (int(''.join(filter(str.isdigit, x))), x))
    horizon = sum(max(duration for _, duration in task) for job in jobs_data for task in job)

    task_type = collections.namedtuple('task_type', 'start end interval presence')
    assigned_task_type = collections.namedtuple('assigned_task_type', 'start job index duration machine')

    all_tasks = {}
    assigned_jobs = collections.defaultdict(list)

    for job_id, job in enumerate(jobs_data):
        for task_id, alternatives in enumerate(job):
            suffix = f'_{job_id}_{task_id}'
            start_var = model.NewIntVar(0, horizon, 'start' + suffix)
            end_var = model.NewIntVar(0, horizon, 'end' + suffix)
            presence_bools = []
            interval_vars = []

            for alt_index, (machine_id, duration) in enumerate(alternatives):
                alt_suffix = f'_{job_id}_{task_id}_alt{alt_index}'
                presence = model.NewBoolVar('presence' + alt_suffix)
                interval = model.NewOptionalIntervalVar(start_var, duration, end_var, presence, 'interval' + alt_suffix)
                presence_bools.append(presence)
                interval_vars.append(interval)
                assigned_jobs[machine_id].append((presence, start_var, job_id + 1, task_id + 1, duration))

            model.Add(sum(presence_bools) == 1)
            all_tasks[job_id + 1, task_id + 1] = task_type(start=start_var, end=end_var, interval=interval_vars, presence=presence_bools)

    for machine_id, intervals in assigned_jobs.items():
        model.AddNoOverlap([
            model.NewOptionalIntervalVar(start, duration, model.NewIntVar(0, horizon, ''), presence, '')
            for presence, start, _, _, duration in intervals
        ])

    for job_id, job in enumerate(jobs_data):
        for task_id in range(len(job) - 1):
            model.Add(all_tasks[job_id + 1, task_id + 2].start >= all_tasks[job_id + 1, task_id + 1].end)

    obj_var = model.NewIntVar(0, horizon, 'makespan')
    model.AddMaxEquality(obj_var, [all_tasks[job_id + 1, len(job)].end for job_id, job in enumerate(jobs_data)])
    
    # Objectif principal : minimiser le makespan
    # Objectif secondaire : favoriser les machines avec priorité plus élevée (valeur plus petite)
    if machine_priorities:
        # Calculer le terme de priorité
        priority_penalty = []
        for job_id, job in enumerate(jobs_data):
            for task_id, alternatives in enumerate(job):
                for alt_index, (machine_id, duration) in enumerate(alternatives):
                    priority_value = machine_priorities.get(machine_id, 0)  # 0 = priorité neutre
                    # La pénalité est proportionnelle à la priorité ET à la présence de la tâche
                    penalty_var = model.NewIntVar(0, priority_value, f'penalty_{job_id}_{task_id}_{alt_index}')
                    presence_var = all_tasks[job_id + 1, task_id + 1].presence[alt_index]
                    model.Add(penalty_var == priority_value * presence_var)
                    priority_penalty.append(penalty_var)
        
        # Objectif combiné : makespan principal + terme de priorité (très petit coefficient)
        total_penalty = model.NewIntVar(0, sum(machine_priorities.values()) if machine_priorities else 0, 'total_penalty')
        model.Add(total_penalty == sum(priority_penalty))
        
        # Le coefficient 0.001 assure que la priorité n'affecte pas le makespan optimal
        # mais départage les solutions avec le même makespan
        combined_objective = model.NewIntVar(0, horizon * 1000 + sum(machine_priorities.values()) if machine_priorities else horizon * 1000, 'combined_obj')
        model.Add(combined_objective == obj_var * 1000 + total_penalty)
        model.Minimize(combined_objective)
        
        print(f"Priorités des machines activées: {machine_priorities}")
    else:
        model.Minimize(obj_var)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "makespan": 0,
            "flowtime": 0,
            "retard_cumule": 0,
            "completion_times": {},
            "machines": {},
            "raw_machines": {},
            "planification": {},
            "status": "no_solution",
            "error": "Aucune solution trouvée"
        }

    machine_to_tasks = collections.defaultdict(list)
    completion_times = [0] * len(jobs_data)

    for job_id, job in enumerate(jobs_data):
        for task_id, alternatives in enumerate(job):
            for alt_index, (machine_id, duration) in enumerate(alternatives):
                if solver.BooleanValue(all_tasks[job_id + 1, task_id + 1].presence[alt_index]):
                    start = solver.Value(all_tasks[job_id + 1, task_id + 1].start)
                    machine_to_tasks[machine_id].append(assigned_task_type(
                        start=start, job=job_id + 1, index=task_id + 1, duration=duration, machine=machine_id))
                    end = start + duration
                    completion_times[job_id] = max(completion_times[job_id], end)

    # Récupérer le makespan réel (pas l'objectif combiné)
    if machine_priorities:
        makespan = solver.Value(obj_var)  # Le vrai makespan, pas l'objectif combiné
    else:
        makespan = solver.ObjectiveValue()
    
    flowtime = sum(completion_times) / len(completion_times)
    total_delay = sum(max(0, ct - dd) for ct, dd in zip(completion_times, due_dates))

    print(f"Makespan (Cmax): {makespan}")
    print(f"Flowtime (F): {flowtime}")
    print(f"Retard cumulé (Rc): {total_delay}")

    # Formatter les résultats pour l'interface web
    machines_formatted = {}
    for machine_id, tasks in machine_to_tasks.items():
        tasks.sort(key=lambda x: x.start)
        machines_formatted[machine_id] = [
            {
                "job": task.job,
                "task": task.index,
                "start": task.start,
                "duration": task.duration
            }
            for task in tasks
        ]

    # Formater les temps d'achèvement
    completion_times_formatted = {f"Job {i+1}": completion_times[i] for i in range(len(completion_times))}

    return {
        "makespan": int(makespan),
        "flowtime": round(flowtime, 2),
        "retard_cumule": int(total_delay),
        "completion_times": completion_times_formatted,
        "machines": machines_formatted,
        "raw_machines": machines_formatted,
        "planification": machines_formatted,
        "status": "optimal" if status == cp_model.OPTIMAL else "feasible"
    }


def create_gantt_chart(jobs_data, due_dates, machine_names=None, stage_names=None, machines_per_stage=None, machine_priorities=None):
    """
    Crée un diagramme de Gantt pour la solution du flowshop flexible
    """
    # Résoudre d'abord le problème
    result = solve_flexible_flowshop(jobs_data, due_dates, machine_names, stage_names, machines_per_stage, machine_priorities)
    
    if result["status"] == "no_solution":
        # Créer un graphique vide en cas de pas de solution
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, 'Aucune solution trouvée', ha='center', va='center', transform=ax.transAxes)
        ax.set_title("Flow Shop Scheduling - Pas de solution")
        return fig

    # Reconstruire le mapping des machines
    machine_map = {}
    display_name_to_id = {}

    for job in jobs_data:
        for task in job:
            if len(task) > 1:
                base = task[0][0]
                suffixes = 'abcdefghijklmnopqrstuvwxyz'
                for i, (machine_id, _) in enumerate(sorted(task)):
                    name = f"Machine {base}" if i == 0 else f"Machine {base}{suffixes[i]}"
                    machine_map[machine_id] = name
                    display_name_to_id[name] = machine_id
            else:
                machine_id, _ = task[0]
                name = f"Machine {machine_id}"
                machine_map[machine_id] = name
                display_name_to_id[name] = machine_id

    machine_display_names = sorted(display_name_to_id.keys(), key=lambda x: (int(''.join(filter(str.isdigit, x))), x))
    
    # Créer le diagramme de Gantt
    fig, ax = plt.subplots(figsize=(12, 8))

    ax.set_yticks(range(len(machine_display_names)))
    ax.set_yticklabels(machine_display_names)
    ax.invert_yaxis()

    cmap = plt.get_cmap("tab10")
    colors = [cmap(i) for i in range(len(jobs_data))]

    # Dessiner les tâches
    for y, label in enumerate(machine_display_names):
        machine_id = display_name_to_id[label]
        if machine_id in result["machines"]:
            for task in result["machines"][machine_id]:
                ax.barh(y, task["duration"], left=task["start"], height=0.8, 
                       color=colors[task["job"] - 1], alpha=0.8, edgecolor='black', linewidth=0.5)
                ax.text(task["start"] + task["duration"] / 2, y, 
                       f"Job {task['job']}\nTask {task['task']}",
                       ha='center', va='center', fontsize=8, fontweight='bold')

    # Grouper les machines alternatives avec des rectangles
    base_to_group = collections.defaultdict(list)
    for label in machine_display_names:
        base = label[:-1] if label[-1].isalpha() else label
        base_to_group[base].append(label)

    for group_labels in base_to_group.values():
        if len(group_labels) > 1:
            ys = [machine_display_names.index(lab) for lab in group_labels]
            y_min = min(ys) - 0.4
            height = len(ys) * 1.0 - 0.2
            ax.add_patch(
                patches.Rectangle(
                    (0, y_min), result["makespan"], height,
                    linewidth=1, edgecolor='black', facecolor='none'
                )
            )

    ax.set_xlim(0, result["makespan"])
    ax.set_xlabel("Temps", fontsize=12)
    ax.set_ylabel("Machines", fontsize=12)
    ax.set_title("Flowshop Flexible - Machines Multiples", fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    
    return fig


# Exemple de test (pour usage en ligne de commande)
if __name__ == '__main__':
    jobs_data = [
        [[(11, 10), (12, 9), (13, 8)], [(21, 12), (22, 11)], [(31, 30)], [(41, 10)], [(51, 14)], [(61, 16)]],
        [[(11, 11), (12, 10), (13, 9)], [(21, 10), (22, 9)], [(31, 35)], [(41, 12)], [(51, 15)], [(61, 17)]],
        [[(11, 9), (12, 11), (13, 10)], [(21, 9), (22, 10)], [(31, 25)], [(41, 11)], [(51, 13)], [(61, 16)]],
        [[(11, 12), (12, 8), (13, 7)], [(21, 11), (22, 12)], [(31, 27)], [(41, 9)], [(51, 14)], [(61, 15)]]
    ]
    due_dates = [85, 90, 80, 95]
    
    result = solve_flexible_flowshop(jobs_data, due_dates)
    print("Résultat:", result)
    
    # Créer et afficher le diagramme de Gantt
    fig = create_gantt_chart(jobs_data, due_dates)
    plt.show()

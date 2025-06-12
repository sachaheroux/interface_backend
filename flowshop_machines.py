import collections
from ortools.sat.python import cp_model
import matplotlib.pyplot as plt
import matplotlib.patches as patches

def solve_flexible_flowshop(jobs_data, due_dates, machine_names=None, stage_names=None, machines_per_stage=None):
    """
    Résout un problème de flowshop flexible avec machines multiples
    
    Args:
        jobs_data: Liste des jobs, chaque job est une liste de tâches, 
                  chaque tâche est une liste d'alternatives [machine_id, duration]
        due_dates: Liste des dates d'échéance
        machine_names: Noms des machines (optionnel)
        stage_names: Noms des étapes (optionnel)  
        machines_per_stage: Nombre de machines par étape (optionnel)
    """
    model = cp_model.CpModel()

    # Mapper les machines pour l'affichage
    machine_map = {}
    display_name_to_id = {}

    # Créer le mapping des machines avec noms d'affichage
    for job in jobs_data:
        for task in job:
            if len(task) > 1:
                # Machines alternatives - utiliser base + suffixes
                base = task[0][0]
                suffixes = 'abcdefghijklmnopqrstuvwxyz'
                for i, (machine_id, _) in enumerate(sorted(task)):
                    if machine_names and base < len(machine_names):
                        name = machine_names[base] if i == 0 else f"{machine_names[base]}{suffixes[i]}"
                    else:
                        name = f"Machine {base}" if i == 0 else f"Machine {base}{suffixes[i]}"
                    machine_map[machine_id] = name
                    display_name_to_id[name] = machine_id
            else:
                # Machine unique
                machine_id, _ = task[0]
                if machine_names and machine_id < len(machine_names):
                    name = machine_names[machine_id]
                else:
                    name = f"Machine {machine_id}"
                machine_map[machine_id] = name
                display_name_to_id[name] = machine_id

    # Trier les noms d'affichage pour l'ordre correct
    machine_display_names = sorted(display_name_to_id.keys(), 
                                 key=lambda x: (int(''.join(filter(str.isdigit, x))), x))
    
    # Calculer l'horizon
    horizon = sum(max(duration for _, duration in task) for job in jobs_data for task in job)

    # Types de données
    task_type = collections.namedtuple('task_type', 'start end interval presence')
    assigned_task_type = collections.namedtuple('assigned_task_type', 'start job index duration machine')

    all_tasks = {}
    assigned_jobs = collections.defaultdict(list)

    # Créer les variables pour chaque tâche
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
                assigned_jobs[machine_id].append((presence, start_var, job_id, task_id, duration))

            # Contrainte : choisir exactement une machine pour cette tâche
            model.Add(sum(presence_bools) == 1)
            all_tasks[job_id, task_id] = task_type(start=start_var, end=end_var, interval=interval_vars, presence=presence_bools)

    # Contraintes de non-chevauchement pour chaque machine
    for machine_id, intervals in assigned_jobs.items():
        model.AddNoOverlap([
            model.NewOptionalIntervalVar(start, duration, model.NewIntVar(0, horizon, ''), presence, '')
            for presence, start, _, _, duration in intervals
        ])

    # Contraintes de précédence dans chaque job
    for job_id, job in enumerate(jobs_data):
        for task_id in range(len(job) - 1):
            model.Add(all_tasks[job_id, task_id + 1].start >= all_tasks[job_id, task_id].end)

    # Objectif : minimiser le makespan
    obj_var = model.NewIntVar(0, horizon, 'makespan')
    model.AddMaxEquality(obj_var, [all_tasks[job_id, len(job) - 1].end for job_id in range(len(jobs_data))])
    model.Minimize(obj_var)

    # Résoudre
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

    # Extraire la solution
    machine_to_tasks = collections.defaultdict(list)
    completion_times = [0] * len(jobs_data)

    for job_id, job in enumerate(jobs_data):
        for task_id, alternatives in enumerate(job):
            for alt_index, (machine_id, duration) in enumerate(alternatives):
                if solver.BooleanValue(all_tasks[job_id, task_id].presence[alt_index]):
                    start = solver.Value(all_tasks[job_id, task_id].start)
                    machine_to_tasks[machine_id].append(
                        assigned_task_type(start=start, job=job_id, index=task_id, 
                                         duration=duration, machine=machine_id)
                    )
                    end = start + duration
                    completion_times[job_id] = max(completion_times[job_id], end)

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

    # Formater les temps d'achèvement (commencer les noms à 1)
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


def create_gantt_chart(jobs_data, due_dates, machine_names=None, stage_names=None, machines_per_stage=None):
    """
    Crée un diagramme de Gantt pour la solution du flowshop flexible
    """
    # Résoudre d'abord le problème
    result = solve_flexible_flowshop(jobs_data, due_dates, machine_names, stage_names, machines_per_stage)
    
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
                    if machine_names and base < len(machine_names):
                        name = machine_names[base] if i == 0 else f"{machine_names[base]}{suffixes[i]}"
                    else:
                        name = f"Machine {base}" if i == 0 else f"Machine {base}{suffixes[i]}"
                    machine_map[machine_id] = name
                    display_name_to_id[name] = machine_id
            else:
                machine_id, _ = task[0]
                if machine_names and machine_id < len(machine_names):
                    name = machine_names[machine_id]
                else:
                    name = f"Machine {machine_id}"
                machine_map[machine_id] = name
                display_name_to_id[name] = machine_id

    machine_display_names = sorted(display_name_to_id.keys(), 
                                 key=lambda x: (int(''.join(filter(str.isdigit, x))), x))
    
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
                       color=colors[task["job"]], alpha=0.8, edgecolor='black', linewidth=0.5)
                ax.text(task["start"] + task["duration"] / 2, y, 
                       f"Job {task['job']+1}\nOp {task['task']+1}",
                       ha='center', va='center', fontsize=8, fontweight='bold')

    # Grouper les machines alternatives avec des rectangles
    base_to_group = collections.defaultdict(list)
    for label in machine_display_names:
        # Extraire la base (sans suffixe alphabétique)
        base = label[:-1] if label[-1].isalpha() else label
        base_to_group[base].append(label)

    for group_labels in base_to_group.values():
        if len(group_labels) > 1:
            ys = [machine_display_names.index(lab) for lab in group_labels]
            y_min = min(ys) - 0.45
            height = len(ys) * 1.0 - 0.1
            ax.add_patch(
                patches.Rectangle(
                    (0, y_min), result["makespan"], height,
                    linewidth=2, edgecolor='red', facecolor='none', linestyle='--'
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
        [[(0, 10)], [(1, 10)], [(2, 60), (21, 40), (22, 45)], [(3, 9)]],
        [[(0, 10)], [(1, 10)], [(2, 30), (21, 45), (22, 30)], [(3, 18)]],
        [[(0, 10)], [(1, 20)], [(2, 60), (21, 50), (22, 65)], [(3, 8)]],
        [[(0, 10)], [(1, 10)], [(2, 30), (21, 30), (22, 25)], [(3, 12)]]
    ]
    due_dates = [100, 100, 100, 100]
    machine_names = ["M1", "M2", "M3", "M4"]
    
    result = solve_flexible_flowshop(jobs_data, due_dates, machine_names)
    print("Résultat:", result)
    
    # Créer et afficher le diagramme de Gantt
    fig = create_gantt_chart(jobs_data, due_dates, machine_names)
    plt.show()

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
    Détecte automatiquement si c'est hybride (machines en parallèle) ou classique.
    """
    # Vérifier s'il y a des machines en parallèle
    if machines_per_stage and any(count > 1 for count in machines_per_stage):
        print("DEBUG: Flowshop hybride détecté (machines en parallèle)")
        return _flowshop_hybride_solver(jobs_data, machines_per_stage, job_names, machine_names, due_dates)
    else:
        print("DEBUG: Flowshop classique détecté")
        return schedule(jobs_data, due_dates)


def _flowshop_hybride_solver(jobs_data, machines_per_stage, job_names=None, machine_names=None, due_dates=None):
    """
    Solveur pour flowshop hybride avec machines parallèles par étape
    """
    print(f"DEBUG: Données reçues - jobs_data: {jobs_data}")
    print(f"DEBUG: machines_per_stage: {machines_per_stage}")
    
    # Initialisation
    job_names = job_names or [f"Job {i}" for i in range(len(jobs_data))]
    machine_names = machine_names or [f"Machine {i+1}" for i in range(len(machines_per_stage))]
    
    num_jobs = len(jobs_data)
    num_stages = len(machines_per_stage)
    
    # Créer la matrice des durées
    durations = []
    for job_idx, job in enumerate(jobs_data):
        job_durations = []
        for stage_idx in range(num_stages):
            if stage_idx < len(job):
                # Format: [(machine_id, duration), ...] donc prendre duration
                duration = float(job[stage_idx][1])
            else:
                duration = 0.0
            job_durations.append(duration)
        durations.append(job_durations)
    
    print(f"DEBUG: Durées créées = {durations}")
    
    # Créer le modèle OR-Tools
    model = cp_model.CpModel()
    
    # Variables pour chaque tâche sur chaque machine
    tasks = {}
    task_starts = {}
    task_ends = {}
    
    # Créer un mapping des machines réelles
    machine_to_stage = {}
    stage_to_machines = {}
    machine_counter = 0
    
    for stage_idx in range(num_stages):
        stage_to_machines[stage_idx] = []
        for machine_idx in range(machines_per_stage[stage_idx]):
            machine_to_stage[machine_counter] = stage_idx
            stage_to_machines[stage_idx].append(machine_counter)
            machine_counter += 1
    
    total_machines = machine_counter
    
    # Horizon temporel (convertir en entier pour OR-Tools)
    horizon = int(sum(sum(job_durations) for job_durations in durations) * 2)
    print(f"DEBUG: Horizon = {horizon}")
    
    # Variables pour chaque job sur chaque machine
    for job_idx in range(num_jobs):
        for machine_idx in range(total_machines):
            stage_idx = machine_to_stage[machine_idx]
            duration = int(durations[job_idx][stage_idx])  # Convertir en entier pour OR-Tools
            
            # Variables de début et fin pour chaque tâche
            start_var = model.NewIntVar(0, horizon, f'start_j{job_idx}_m{machine_idx}')
            end_var = model.NewIntVar(0, horizon, f'end_j{job_idx}_m{machine_idx}')
            task_var = model.NewBoolVar(f'task_j{job_idx}_m{machine_idx}')
            
            tasks[(job_idx, machine_idx)] = task_var
            task_starts[(job_idx, machine_idx)] = start_var
            task_ends[(job_idx, machine_idx)] = end_var
            
            # Si la tâche est assignée, alors end = start + duration
            model.Add(end_var == start_var + duration).OnlyEnforceIf(task_var)
    
    # Contraintes: chaque job doit être assigné à exactement une machine par étape
    for job_idx in range(num_jobs):
        for stage_idx in range(num_stages):
            machines_in_stage = stage_to_machines[stage_idx]
            model.Add(sum(tasks[(job_idx, machine_idx)] for machine_idx in machines_in_stage) == 1)
    
    # Contraintes de précédence: un job ne peut pas commencer à l'étape i+1 avant d'avoir fini l'étape i
    for job_idx in range(num_jobs):
        for stage_idx in range(num_stages - 1):
            current_stage_machines = stage_to_machines[stage_idx]
            next_stage_machines = stage_to_machines[stage_idx + 1]
            
            # Fin de l'étape courante
            current_end = model.NewIntVar(0, horizon, f'job_{job_idx}_stage_{stage_idx}_end')
            for machine_idx in current_stage_machines:
                model.Add(current_end >= task_ends[(job_idx, machine_idx)]).OnlyEnforceIf(tasks[(job_idx, machine_idx)])
            
            # Début de l'étape suivante
            for next_machine_idx in next_stage_machines:
                model.Add(task_starts[(job_idx, next_machine_idx)] >= current_end).OnlyEnforceIf(tasks[(job_idx, next_machine_idx)])
    
    # Contraintes de non-chevauchement: une machine ne peut traiter qu'un job à la fois
    for machine_idx in range(total_machines):
        intervals = []
        for job_idx in range(num_jobs):
            interval = model.NewOptionalIntervalVar(
                task_starts[(job_idx, machine_idx)],
                int(durations[job_idx][machine_to_stage[machine_idx]]),  # Convertir en entier
                task_ends[(job_idx, machine_idx)],
                tasks[(job_idx, machine_idx)],
                f'interval_j{job_idx}_m{machine_idx}'
            )
            intervals.append(interval)
        
        model.AddNoOverlap(intervals)
    
    # Objectif: minimiser le makespan
    makespan = model.NewIntVar(0, horizon, 'makespan')
    for job_idx in range(num_jobs):
        for machine_idx in range(total_machines):
            model.Add(makespan >= task_ends[(job_idx, machine_idx)]).OnlyEnforceIf(tasks[(job_idx, machine_idx)])
    
    model.Minimize(makespan)
    
    # Résoudre
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60.0
    status = solver.Solve(model)
    
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        return _extract_hybride_solution(solver, tasks, task_starts, task_ends, machine_to_stage, makespan, 
                                       job_names, machine_names, due_dates, durations)
    else:
        raise ValueError("Aucune solution trouvée par le solveur CP.")


def _extract_hybride_solution(solver, tasks, task_starts, task_ends, machine_to_stage, makespan, 
                             job_names, machine_names, due_dates, durations):
    """
    Extrait la solution du solveur hybride
    """
    solution_makespan = solver.Value(makespan)
    
    # Extraire les tâches assignées
    assigned_tasks = {}
    for machine_idx in range(len(machine_to_stage)):
        assigned_tasks[machine_idx] = []
    
    for job_idx in range(len(job_names)):
        for machine_idx in range(len(machine_to_stage)):
            if solver.Value(tasks[(job_idx, machine_idx)]):
                start_time = solver.Value(task_starts[(job_idx, machine_idx)])
                end_time = solver.Value(task_ends[(job_idx, machine_idx)])
                duration = end_time - start_time
                
                assigned_tasks[machine_idx].append({
                    'job': job_idx,
                    'start': start_time,
                    'duration': duration,
                    'stage': machine_to_stage[machine_idx]
                })
    
    # Trier les tâches par temps de début
    for machine_idx in assigned_tasks:
        assigned_tasks[machine_idx].sort(key=lambda x: x['start'])
    
    # Calculer les temps de complétion
    completion_times = {}
    for job_idx in range(len(job_names)):
        max_completion = 0
        for machine_idx in range(len(machine_to_stage)):
            for task in assigned_tasks[machine_idx]:
                if task['job'] == job_idx:
                    max_completion = max(max_completion, task['start'] + task['duration'])
        completion_times[f"Job {job_idx}"] = max_completion
    
    # Calculer le retard cumulé
    total_tardiness = 0
    if due_dates:
        for job_idx in range(len(job_names)):
            if job_idx < len(due_dates):
                completion = completion_times[f"Job {job_idx}"]
                tardiness = max(0, completion - due_dates[job_idx])
                total_tardiness += tardiness
    
    # Créer le diagramme de Gantt
    gantt_url = _create_hybride_gantt_chart(assigned_tasks, solution_makespan, job_names, machine_names, machine_to_stage)
    
    return {
        'makespan': solution_makespan,
        'machines': assigned_tasks,
        'completion_times': completion_times,
        'flowtime': sum(completion_times.values()) / len(completion_times) if completion_times else 0,
        'retard_cumule': total_tardiness,
        'gantt_url': gantt_url
    }


def _create_hybride_gantt_chart(assigned_tasks, makespan, job_names, machine_names, machine_to_stage):
    """
    Crée un diagramme de Gantt pour la solution hybride
    """
    try:
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Couleurs pour les jobs
        colors = plt.cm.Set3(np.linspace(0, 1, len(job_names)))
        
        # Dessiner les tâches
        y_pos = 0
        machine_labels = []
        
        for machine_idx, tasks in assigned_tasks.items():
            if tasks:  # S'il y a des tâches sur cette machine
                stage_idx = machine_to_stage.get(machine_idx, 0)
                stage_name = machine_names[stage_idx] if stage_idx < len(machine_names) else f"Machine {stage_idx + 1}"
                machine_label = f"{stage_name} - M{machine_idx}"
                machine_labels.append(machine_label)
                
                for task in tasks:
                    job_idx = task['job']
                    start = task['start']
                    duration = task['duration']
                    
                    # Dessiner la barre
                    rect = patches.Rectangle(
                        (start, y_pos), duration, 0.8,
                        linewidth=1, edgecolor='black',
                        facecolor=colors[job_idx], alpha=0.7
                    )
                    ax.add_patch(rect)
                    
                    # Ajouter le nom du job
                    job_name = job_names[job_idx] if job_idx < len(job_names) else f"Job {job_idx}"
                    ax.text(start + duration/2, y_pos + 0.4, job_name,
                           ha='center', va='center', fontsize=8, fontweight='bold')
                
                y_pos += 1
        
        # Configuration du graphique
        ax.set_xlim(0, makespan + 1)
        ax.set_ylim(0, len(machine_labels))
        ax.set_xlabel('Temps')
        ax.set_ylabel('Machines')
        ax.set_title(f'Diagramme de Gantt - Flowshop Hybride\nMakespan: {makespan}')
        
        # Étiquettes des machines
        ax.set_yticks(range(len(machine_labels)))
        ax.set_yticklabels(machine_labels)
        
        # Grille
        ax.grid(True, alpha=0.3)
        
        # Légende
        legend_elements = []
        for job_idx in range(len(job_names)):
            job_name = job_names[job_idx] if job_idx < len(job_names) else f"Job {job_idx}"
            legend_elements.append(patches.Patch(color=colors[job_idx], label=job_name))
        
        ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1.15, 1))
        
        plt.tight_layout()
        
        # Sauvegarder
        gantt_filename = f"gantt_flowshop_hybride_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = os.path.join("static", gantt_filename)
        os.makedirs("static", exist_ok=True)
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        return f"/static/{gantt_filename}"
    
    except Exception as e:
        print(f"Erreur lors de la création du Gantt: {e}")
        return None

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
    print(f"DEBUG: job_names: {job_names}")
    print(f"DEBUG: machine_names: {machine_names}")
    
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
    
    print(f"DEBUG: Configuration des machines:")
    print(f"  - Nombre total de machines physiques: {total_machines}")
    print(f"  - Mapping machine_to_stage: {machine_to_stage}")
    print(f"  - Mapping stage_to_machines: {stage_to_machines}")
    
    # Vérifier qu'on a bien du parallélisme
    parallel_stages = [stage for stage, machines in stage_to_machines.items() if len(machines) > 1]
    if parallel_stages:
        print(f"  - Étapes avec parallélisme: {parallel_stages}")
    else:
        print(f"  - ATTENTION: Aucune étape avec parallélisme détectée!")
    
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
            
            # Pour chaque machine de l'étape suivante
            for next_machine_idx in next_stage_machines:
                # La tâche sur cette machine ne peut commencer qu'après la fin de TOUTES les machines de l'étape précédente
                for current_machine_idx in current_stage_machines:
                    # Si les deux tâches sont assignées, contrainte de précédence
                    model.Add(task_starts[(job_idx, next_machine_idx)] >= task_ends[(job_idx, current_machine_idx)]).OnlyEnforceIf([
                        tasks[(job_idx, current_machine_idx)],
                        tasks[(job_idx, next_machine_idx)]
                    ])
    
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
    Extrait la solution du solveur hybride et la convertit au format compatible avec le frontend
    """
    solution_makespan = solver.Value(makespan)
    
    print(f"DEBUG: Extraction solution - makespan = {solution_makespan}")
    
    # Créer un mapping des étapes aux machines virtuelles (pour compatibilité avec le format classique)
    stage_machines = {}  # Format: {stage_idx: [list of tasks]}
    
    # Extraire toutes les tâches assignées
    all_assigned_tasks = []
    for job_idx in range(len(job_names)):
        job_sequence = []  # Pour vérifier la séquence
        for machine_idx in range(len(machine_to_stage)):
            if solver.Value(tasks[(job_idx, machine_idx)]):
                start_time = solver.Value(task_starts[(job_idx, machine_idx)])
                end_time = solver.Value(task_ends[(job_idx, machine_idx)])
                duration = end_time - start_time
                stage_idx = machine_to_stage[machine_idx]
                
                task_info = {
                    'job': job_idx,
                    'task': stage_idx,  # task ID = stage ID pour compatibilité 
                    'start': start_time,
                    'duration': duration,
                    'machine_idx': machine_idx,
                    'stage': stage_idx
                }
                
                all_assigned_tasks.append(task_info)
                job_sequence.append((stage_idx, start_time, duration))
        
        # Debug: afficher la séquence de chaque job
        job_sequence.sort(key=lambda x: x[1])  # Trier par temps de début
        print(f"DEBUG: Job {job_idx} sequence: {job_sequence}")
    
    # Regrouper par étape (comme dans le format classique)
    assigned_tasks = {}
    for task in all_assigned_tasks:
        stage_idx = task['stage']
        if stage_idx not in assigned_tasks:
            assigned_tasks[stage_idx] = []
        
        # Format compatible avec le frontend classique
        assigned_tasks[stage_idx].append({
            'job': task['job'],
            'task': task['task'],
            'start': task['start'],
            'duration': task['duration']
        })
    
    # Trier les tâches par temps de début pour chaque étape
    for stage_idx in assigned_tasks:
        assigned_tasks[stage_idx].sort(key=lambda x: x['start'])
        print(f"DEBUG: Stage {stage_idx} tasks: {assigned_tasks[stage_idx]}")
    
    # Calculer les temps de complétion (dernier temps de fin pour chaque job)
    completion_times = {}
    for job_idx in range(len(job_names)):
        max_completion = 0
        for task in all_assigned_tasks:
            if task['job'] == job_idx:
                completion_time = task['start'] + task['duration']
                max_completion = max(max_completion, completion_time)
        completion_times[f"Job {job_idx}"] = max_completion
    
    print(f"DEBUG: Completion times: {completion_times}")
    
    # Calculer le retard cumulé
    total_tardiness = 0
    if due_dates:
        for job_idx in range(len(job_names)):
            if job_idx < len(due_dates):
                completion = completion_times[f"Job {job_idx}"]
                tardiness = max(0, completion - due_dates[job_idx])
                total_tardiness += tardiness
    
    # Créer le diagramme de Gantt avec les vraies machines physiques
    raw_machine_data = {}
    for task in all_assigned_tasks:
        machine_idx = task['machine_idx']
        if machine_idx not in raw_machine_data:
            raw_machine_data[machine_idx] = []
        
        raw_machine_data[machine_idx].append({
            'job': task['job'],
            'task': task['task'],
            'start': task['start'],
            'duration': task['duration']
        })
    
    # Trier par temps de début
    for machine_idx in raw_machine_data:
        raw_machine_data[machine_idx].sort(key=lambda x: x['start'])
    
    # Debug: Analyser l'utilisation du parallélisme
    print(f"DEBUG: Analyse du parallélisme:")
    for stage_idx in range(len(machine_names)):
        stage_machines = [m for m, s in machine_to_stage.items() if s == stage_idx]
        used_machines = [m for m in stage_machines if m in raw_machine_data and len(raw_machine_data[m]) > 0]
        print(f"  - Étape {stage_idx} ({machine_names[stage_idx]}): {len(used_machines)}/{len(stage_machines)} machines utilisées")
        if len(used_machines) < len(stage_machines):
            print(f"    ⚠️  Machines inutilisées: {set(stage_machines) - set(used_machines)}")
        if len(used_machines) > 1:
            print(f"    ✅ Parallélisme exploité!")
    
    gantt_url = _create_hybride_gantt_chart(raw_machine_data, solution_makespan, job_names, machine_names, machine_to_stage)
    
    return {
        'makespan': solution_makespan,
        'machines': assigned_tasks,  # Format par étapes pour affichage frontend
        'raw_machines': raw_machine_data,  # Format par machines physiques pour Gantt
        'completion_times': completion_times,
        'flowtime': sum(completion_times.values()) / len(completion_times) if completion_times else 0,
        'retard_cumule': total_tardiness,
        'gantt_url': gantt_url
    }


def _create_hybride_gantt_chart(assigned_tasks, makespan, job_names, machine_names, machine_to_stage):
    """
    Crée un diagramme de Gantt pour la solution hybride - AFFICHE TOUTES LES MACHINES
    """
    try:
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Couleurs pour les jobs
        colors = plt.cm.Set3(np.linspace(0, 1, len(job_names)))
        
        # Dessiner les tâches pour TOUTES les machines (même vides)
        y_pos = 0
        machine_labels = []
        
        # Créer la liste complète des machines dans l'ordre
        all_machines = sorted(machine_to_stage.keys())
        
        for machine_idx in all_machines:
            stage_idx = machine_to_stage[machine_idx]
            stage_name = machine_names[stage_idx] if stage_idx < len(machine_names) else f"Étape {stage_idx + 1}"
            
            # Calculer le numéro de sous-machine dans l'étape 
            machines_in_same_stage = [m for m, s in machine_to_stage.items() if s == stage_idx]
            machines_in_same_stage.sort()
            sub_machine_position = machines_in_same_stage.index(machine_idx)
            
            # Nomenclature M1, M1', M1''
            if sub_machine_position == 0:
                sub_name = ""
            else:
                sub_name = "'" * sub_machine_position
            
            machine_label = f"{stage_name} - M{stage_idx + 1}{sub_name}"
            machine_labels.append(machine_label)
            
            # Dessiner les tâches de cette machine (peut être vide)
            tasks = assigned_tasks.get(machine_idx, [])
            print(f"DEBUG: Machine {machine_idx} ({machine_label}) a {len(tasks)} tâches: {tasks}")
            
            if tasks:  # S'il y a des tâches sur cette machine
                
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
            else:
                # Machine vide - dessiner une ligne vide avec texte "Vide"
                ax.text(makespan/2, y_pos + 0.4, "Vide", 
                       ha='center', va='center', fontsize=8, 
                       style='italic', alpha=0.5)
            
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

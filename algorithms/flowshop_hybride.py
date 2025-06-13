"""
Algorithme Flowshop Hybride avec machines parallèles par étape
Utilise OR-Tools pour optimiser la planification
"""

from ortools.sat.python import cp_model
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from datetime import datetime
import os
import numpy as np

class FlowshopHybrideSolver:
    def __init__(self, jobs_data, machines_per_stage, job_names=None, stage_names=None):
        """
        Initialise le solveur Flowshop Hybride
        
        Args:
            jobs_data: Liste des jobs avec leurs durées par étape
            machines_per_stage: Nombre de machines par étape
            job_names: Noms des jobs
            stage_names: Noms des étapes
        """
        self.jobs_data = jobs_data
        self.machines_per_stage = machines_per_stage
        self.job_names = job_names or [f"Job {i}" for i in range(len(jobs_data))]
        self.stage_names = stage_names or [f"Étape {i+1}" for i in range(len(machines_per_stage))]
        
        self.num_jobs = len(jobs_data)
        self.num_stages = len(machines_per_stage)
        
        # Créer la matrice des durées
        self.durations = []
        for job_idx, job in enumerate(jobs_data):
            job_durations = []
            for stage_idx in range(self.num_stages):
                duration = 0
                for task_idx, task_duration in job:
                    if task_idx == stage_idx:
                        duration = task_duration
                        break
                job_durations.append(duration)
            self.durations.append(job_durations)
    
    def solve(self):
        """
        Résout le problème de flowshop hybride
        """
        model = cp_model.CpModel()
        
        # Variables pour chaque tâche sur chaque machine
        tasks = {}
        task_starts = {}
        task_ends = {}
        
        # Créer un mapping des machines réelles
        machine_to_stage = {}
        stage_to_machines = {}
        machine_counter = 0
        
        for stage_idx in range(self.num_stages):
            stage_to_machines[stage_idx] = []
            for machine_idx in range(self.machines_per_stage[stage_idx]):
                machine_to_stage[machine_counter] = stage_idx
                stage_to_machines[stage_idx].append(machine_counter)
                machine_counter += 1
        
        total_machines = machine_counter
        
        # Horizon temporel (estimation large)
        horizon = sum(sum(job_durations) for job_durations in self.durations) * 2
        
        # Variables pour chaque job sur chaque machine
        for job_idx in range(self.num_jobs):
            for machine_idx in range(total_machines):
                stage_idx = machine_to_stage[machine_idx]
                duration = self.durations[job_idx][stage_idx]
                
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
        for job_idx in range(self.num_jobs):
            for stage_idx in range(self.num_stages):
                machines_in_stage = stage_to_machines[stage_idx]
                model.Add(sum(tasks[(job_idx, machine_idx)] for machine_idx in machines_in_stage) == 1)
        
        # Contraintes de précédence: un job ne peut pas commencer à l'étape i+1 avant d'avoir fini l'étape i
        for job_idx in range(self.num_jobs):
            for stage_idx in range(self.num_stages - 1):
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
            for job_idx in range(self.num_jobs):
                interval = model.NewOptionalIntervalVar(
                    task_starts[(job_idx, machine_idx)],
                    self.durations[job_idx][machine_to_stage[machine_idx]],
                    task_ends[(job_idx, machine_idx)],
                    tasks[(job_idx, machine_idx)],
                    f'interval_j{job_idx}_m{machine_idx}'
                )
                intervals.append(interval)
            
            model.AddNoOverlap(intervals)
        
        # Objectif: minimiser le makespan
        makespan = model.NewIntVar(0, horizon, 'makespan')
        for job_idx in range(self.num_jobs):
            for machine_idx in range(total_machines):
                model.Add(makespan >= task_ends[(job_idx, machine_idx)]).OnlyEnforceIf(tasks[(job_idx, machine_idx)])
        
        model.Minimize(makespan)
        
        # Résoudre
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0
        status = solver.Solve(model)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            return self._extract_solution(solver, tasks, task_starts, task_ends, machine_to_stage, makespan)
        else:
            return None
    
    def _extract_solution(self, solver, tasks, task_starts, task_ends, machine_to_stage, makespan):
        """
        Extrait la solution du solveur
        """
        solution_makespan = solver.Value(makespan)
        
        # Extraire les tâches assignées
        assigned_tasks = {}
        for machine_idx in range(len(machine_to_stage)):
            assigned_tasks[machine_idx] = []
        
        for job_idx in range(self.num_jobs):
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
        for job_idx in range(self.num_jobs):
            max_completion = 0
            for machine_idx in range(len(machine_to_stage)):
                for task in assigned_tasks[machine_idx]:
                    if task['job'] == job_idx:
                        max_completion = max(max_completion, task['start'] + task['duration'])
            completion_times[f"Job {job_idx}"] = max_completion
        
        return {
            'makespan': solution_makespan,
            'machines': assigned_tasks,
            'completion_times': completion_times,
            'flowtime': sum(completion_times.values()) / len(completion_times) if completion_times else 0
        }
    
    def create_gantt_chart(self, solution, filename="gantt_flowshop_hybride.png"):
        """
        Crée un diagramme de Gantt pour la solution
        """
        if not solution:
            return None
        
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Couleurs pour les jobs
        colors = plt.cm.Set3(np.linspace(0, 1, self.num_jobs))
        
        # Dessiner les tâches
        y_pos = 0
        machine_labels = []
        
        for machine_idx, tasks in solution['machines'].items():
            stage_idx = tasks[0]['stage'] if tasks else 0
            stage_name = self.stage_names[stage_idx] if stage_idx < len(self.stage_names) else f"Étape {stage_idx + 1}"
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
                job_name = self.job_names[job_idx] if job_idx < len(self.job_names) else f"Job {job_idx}"
                ax.text(start + duration/2, y_pos + 0.4, job_name,
                       ha='center', va='center', fontsize=8, fontweight='bold')
            
            y_pos += 1
        
        # Configuration du graphique
        ax.set_xlim(0, solution['makespan'] + 1)
        ax.set_ylim(0, len(solution['machines']))
        ax.set_xlabel('Temps')
        ax.set_ylabel('Machines')
        ax.set_title(f'Diagramme de Gantt - Flowshop Hybride\nMakespan: {solution["makespan"]}')
        
        # Étiquettes des machines
        ax.set_yticks(range(len(machine_labels)))
        ax.set_yticklabels(machine_labels)
        
        # Grille
        ax.grid(True, alpha=0.3)
        
        # Légende
        legend_elements = []
        for job_idx in range(self.num_jobs):
            job_name = self.job_names[job_idx] if job_idx < len(self.job_names) else f"Job {job_idx}"
            legend_elements.append(patches.Patch(color=colors[job_idx], label=job_name))
        
        ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1.15, 1))
        
        plt.tight_layout()
        
        # Sauvegarder
        filepath = os.path.join("static", filename)
        os.makedirs("static", exist_ok=True)
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        return f"/static/{filename}"

def flowshop_hybride_contraintes(jobs_data, machines_per_stage, job_names=None, stage_names=None, due_dates=None):
    """
    Fonction principale pour résoudre le flowshop hybride
    """
    solver = FlowshopHybrideSolver(jobs_data, machines_per_stage, job_names, stage_names)
    solution = solver.solve()
    
    if solution:
        # Créer le diagramme de Gantt
        gantt_filename = f"gantt_flowshop_hybride_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        gantt_url = solver.create_gantt_chart(solution, gantt_filename)
        solution['gantt_url'] = gantt_url
        
        # Calculer le retard cumulé si les dates dues sont fournies
        if due_dates:
            total_tardiness = 0
            for i, (job_name, completion_time) in enumerate(solution['completion_times'].items()):
                if i < len(due_dates):
                    tardiness = max(0, completion_time - due_dates[i])
                    total_tardiness += tardiness
            solution['retard_cumule'] = total_tardiness
        else:
            solution['retard_cumule'] = 0
    
    return solution 
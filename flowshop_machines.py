import collections
from ortools.sat.python import cp_model
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

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
    if machine_priorities and len(machine_priorities) > 0:
        # Calculer le terme de priorité de manière plus simple
        priority_penalty = []
        max_priority = max(machine_priorities.values()) if machine_priorities else 1
        
        for job_id, job in enumerate(jobs_data):
            for task_id, alternatives in enumerate(job):
                for alt_index, (machine_id, duration) in enumerate(alternatives):
                    priority_value = machine_priorities.get(machine_id, max_priority + 1)  # Si pas de priorité, donner la plus faible
                    if priority_value > 0:  # Seulement si priorité valide
                        # La pénalité est proportionnelle à la priorité ET à la présence de la tâche
                        penalty_var = model.NewIntVar(0, priority_value * 100, f'penalty_{job_id}_{task_id}_{alt_index}')
                        presence_var = all_tasks[job_id + 1, task_id + 1].presence[alt_index]
                        model.Add(penalty_var == priority_value * presence_var)
                        priority_penalty.append(penalty_var)
        
        if priority_penalty:  # Seulement si on a des pénalités
            # Objectif combiné : makespan principal + terme de priorité (très petit coefficient)
            total_penalty = model.NewIntVar(0, max_priority * 100 * len(priority_penalty), 'total_penalty')
            model.Add(total_penalty == sum(priority_penalty))
            
            # Le coefficient 10000 assure que le makespan reste dominant
            combined_objective = model.NewIntVar(0, horizon * 10000 + max_priority * 100 * len(priority_penalty), 'combined_obj')
            model.Add(combined_objective == obj_var * 10000 + total_penalty)
            model.Minimize(combined_objective)
            
            print(f"Priorités des machines activées: {machine_priorities}")
        else:
            model.Minimize(obj_var)
            print("Pas de priorités valides, utilisation de l'objectif standard")
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
    AVEC le même visuel standardisé que les autres algorithmes
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
    
    # Calculer la taille optimale selon le nombre de machines
    num_machines = len(machine_display_names)
    fig_height = max(4, num_machines * 0.8 + 2)
    fig, ax = plt.subplots(figsize=(14, fig_height))
    
    # Style professionnel (comme create_gantt_figure)
    ax.set_facecolor('#f8f9fa')
    fig.patch.set_facecolor('white')
    
    # Couleurs différentes pour chaque tâche (comme create_gantt_figure)
    colors = ["#4f46e5", "#f59e0b", "#10b981", "#ef4444", "#6366f1", "#8b5cf6", "#14b8a6", "#f97316", 
              "#06b6d4", "#84cc16", "#f43f5e", "#8b5a2b", "#6b7280", "#ec4899", "#3b82f6", "#22c55e"]

    ax.set_yticks(range(len(machine_display_names)))
    ax.set_yticklabels(machine_display_names)
    ax.invert_yaxis()

    # Hauteur des barres
    bar_height = 0.6

    # Dessiner les tâches avec le nouveau style
    for y, label in enumerate(machine_display_names):
        machine_id = display_name_to_id[label]
        if machine_id in result["machines"]:
            for task in result["machines"][machine_id]:
                job_idx = task["job"] - 1  # Ajuster l'index (jobs commencent à 1)
                color = colors[job_idx % len(colors)]
                
                # Créer la barre avec bordure (style professionnel)
                bar = ax.barh(y, task["duration"], left=task["start"], height=bar_height, 
                             color=color, alpha=0.9, edgecolor='white', linewidth=1.5)
                
                # Ajouter une ombre subtile
                shadow = ax.barh(y, task["duration"], left=task["start"] + 0.1, color='black', 
                               height=bar_height, alpha=0.1, zorder=0)
                
                # Texte du job avec style amélioré
                text_color = 'white'
                ax.text(task["start"] + task["duration"] / 2, y, 
                       f"Job {task['job']}\nTask {task['task']}",
                       ha='center', va='center', color=text_color, fontsize=9, 
                       fontweight='bold', zorder=10)

    # Grouper les machines alternatives avec des rectangles NOIRS (préserver cette fonctionnalité)
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
                    linewidth=2, edgecolor='black', facecolor='none', zorder=15
                )
            )

    # Ajouter le cadrillage avec des valeurs rondes (comme create_gantt_figure)
    max_time = result["makespan"]
    if max_time > 0:
        # Fonction pour obtenir des intervalles de temps ronds
        def get_nice_time_intervals(max_time):
            nice_intervals = [1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 150, 200, 250, 300, 350, 400, 450, 500]
            for interval in nice_intervals:
                if max_time / interval <= 20:  # Pas plus de 20 divisions
                    return interval
            return max(1, int(max_time / 20))
        
        time_step = get_nice_time_intervals(max_time)
        time_ticks = np.arange(0, int(max_time) + time_step + 1, time_step)
        
        # Grille verticale et horizontale très foncée (comme create_gantt_figure)
        ax.set_xticks(time_ticks)
        ax.grid(True, axis='x', alpha=1.0, linestyle='-', linewidth=1.2, color='#6c757d')
        ax.grid(True, axis='y', alpha=0.8, linestyle='-', linewidth=1.0, color='#6c757d')
        ax.set_axisbelow(True)
        
        # Créer un mapping des dates dues vers les couleurs des tâches
        due_date_colors = {}
        if due_dates:
            for job_idx, due_date in enumerate(due_dates):
                if due_date and due_date > 0:
                    job_color = colors[job_idx % len(colors)]
                    due_date_colors[due_date] = (job_color, job_idx)
        
        # Afficher les dates dues empilées AU-DESSUS de la première machine (comme create_gantt_figure)
        if due_date_colors:
            # Créer des étiquettes normales pour l'axe x
            x_labels = [str(int(tick)) for tick in time_ticks]
            ax.set_xticklabels(x_labels)
            
            # Obtenir les limites actuelles de l'axe y
            y_min, y_max = ax.get_ylim()
            
            # Grouper les dates dues par position pour les empiler
            due_dates_at_position = {}
            
            for due_date, (color, job_idx) in due_date_colors.items():
                if due_date <= max_time:
                    if due_date not in due_dates_at_position:
                        due_dates_at_position[due_date] = []
                    
                    # Nom du job (Job 1, Job 2, etc.)
                    job_name = f'Job {job_idx+1}'
                    due_dates_at_position[due_date].append((color, job_name))
            
            # Afficher les dates dues empilées AU-DESSUS de la première machine
            max_stack_height = 0
            for due_date, job_info_list in due_dates_at_position.items():
                # Ajouter une ligne verticale pour marquer la date due
                main_color = job_info_list[0][0]  # Couleur du premier job
                ax.axvline(x=due_date, color=main_color, linestyle='--', linewidth=2, alpha=0.8, zorder=5)
                
                # Empiler les dates dues verticalement AU-DESSUS de la première machine
                # Comme l'axe Y est inversé, nous devons utiliser des valeurs négatives pour aller "au-dessus"
                for i, (color, job_name) in enumerate(job_info_list):
                    # Position au-dessus de la première machine (valeurs négatives car axe inversé)
                    y_position = -0.8 - (i * 0.5)
                    
                    # Créer une boîte colorée avec le nom du job et la date due
                    bbox_props = dict(boxstyle="round,pad=0.3", facecolor=color, alpha=0.8, edgecolor='black')
                    ax.text(due_date, y_position, f'{job_name}: {due_date}', 
                           ha='center', va='center', fontsize=9, color='white', weight='bold',
                           bbox=bbox_props, zorder=10)
                    
                    max_stack_height = max(max_stack_height, 0.8 + (i + 1) * 0.5)
            
            # Ajuster les limites de l'axe Y pour faire de la place aux due dates
            if max_stack_height > 0:
                extension = max_stack_height + 0.2
                # Étendre vers le haut (valeurs négatives car axe inversé)
                ax.set_ylim(-extension, len(machine_display_names) - 0.5)

    # Améliorer les axes (comme create_gantt_figure)
    ax.set_xlim(0, result["makespan"])
    ax.set_xlabel("Temps", fontsize=12, fontweight='bold')
    ax.set_ylabel("Machines", fontsize=12, fontweight='bold')
    
    # S'assurer que toutes les machines sont visibles (si pas de dates dues)
    if not due_date_colors:
        ax.set_ylim(-0.5, len(machine_display_names) - 0.5)
    
    # Titre avec style
    ax.set_title("Flowshop Flexible - Machines Multiples", fontsize=14, fontweight='bold', pad=20)
    
    # Créer la légende pour les tâches (si pas trop de jobs)
    if len(jobs_data) <= 8:  # Limiter la légende si trop de jobs
        legend_elements = []
        for i in range(len(jobs_data)):
            # Utiliser la même logique de couleur que pour les barres
            color = colors[i % len(colors)]
            legend_elements.append(patches.Patch(color=color, label=f'Job {i+1}'))
        
        # Positionner la légende en haut à droite
        ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1, 1), 
                 frameon=True, fancybox=True, shadow=True, fontsize=9)
    
    # Ajuster les marges
    plt.tight_layout()
    
    # Ajouter une bordure autour du graphique
    for spine in ax.spines.values():
        spine.set_edgecolor('#dee2e6')
        spine.set_linewidth(1)
    
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

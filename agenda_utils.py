from datetime import datetime, timedelta

def generer_agenda_json(result, start_datetime_str, opening_hours, weekend_days, jours_feries, unite="heures", machine_names=None, job_names=None):
    base_datetime = datetime.fromisoformat(start_datetime_str)
    unit_multipliers = {"minutes": 1, "heures": 60, "jours": 1440}
    minute_multiplier = unit_multipliers.get(unite, 60)

    # Configurer jours exclus
    weekend_indices = {
        "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4,
        "samedi": 5, "dimanche": 6
    }
    weekend_indexes = {weekend_indices[d] for d in weekend_days if d in weekend_indices}
    feries = {datetime.fromisoformat(d).date() for d in jours_feries if d}

    # Convertir heures d'ouverture
    open_hour = int(opening_hours["start"].split(":")[0])
    open_min = int(opening_hours["start"].split(":")[1])
    close_hour = int(opening_hours["end"].split(":")[0])
    close_min = int(opening_hours["end"].split(":")[1])
    max_daily_minutes = (close_hour * 60 + close_min) - (open_hour * 60 + open_min)

    # Groupes = machines
    groups = [
        {"id": int(mid), "title": machine_names[int(mid)] if machine_names else f"Machine {mid}"}
        for mid in result["machines"].keys()
    ]

    items = []

    # Fonction pour trouver le prochain créneau disponible
    def find_next_available_slot(current_dt, duration_minutes):
        while True:
            current_day = current_dt.date()
            weekday = current_dt.weekday()
            
            # Vérifier si c'est un jour ouvré
            if current_day not in feries and weekday not in weekend_indexes:
                # Ajuster à l'heure d'ouverture si nécessaire
                day_start = current_dt.replace(hour=open_hour, minute=open_min, second=0, microsecond=0)
                day_end = current_dt.replace(hour=close_hour, minute=close_min, second=0, microsecond=0)
                
                # Si on est avant l'ouverture, commencer à l'ouverture
                if current_dt < day_start:
                    current_dt = day_start
                
                # Vérifier si la tâche rentre dans la journée
                time_until_close = int((day_end - current_dt).total_seconds() / 60)
                if duration_minutes <= time_until_close:
                    return current_dt
            
            # Passer au jour suivant à l'heure d'ouverture
            current_dt = (current_dt + timedelta(days=1)).replace(hour=open_hour, minute=open_min, second=0, microsecond=0)

    # Suivre le temps par machine pour respecter les contraintes Flowshop
    machine_current_time = {}
    
    for machine_id_str, tasks in result["machines"].items():
        machine_id = int(machine_id_str)
        machine_current_time[machine_id] = base_datetime
        
        for idx, task in enumerate(tasks):
            duration_minutes = task["duration"] * minute_multiplier
            
            # Pour Flowshop: une tâche ne peut pas commencer avant que la précédente soit finie
            # ET pas avant que la même tâche soit finie sur la machine précédente
            start_time = machine_current_time[machine_id]
            
            # Trouver le prochain créneau disponible
            actual_start = find_next_available_slot(start_time, duration_minutes)
            actual_end = actual_start + timedelta(minutes=duration_minutes)
            
            # Gérer les pauses déjeuner (12h-13h par défaut)
            lunch_start = actual_start.replace(hour=12, minute=0, second=0, microsecond=0)
            lunch_end = actual_start.replace(hour=13, minute=0, second=0, microsecond=0)
            
            # Si la tâche chevauche la pause déjeuner, l'ajuster
            if actual_start < lunch_end and actual_end > lunch_start:
                if actual_start < lunch_start:
                    # Diviser la tâche avant et après la pause
                    first_part_end = lunch_start
                    first_part_duration = int((first_part_end - actual_start).total_seconds() / 60)
                    second_part_start = lunch_end
                    second_part_duration = duration_minutes - first_part_duration
                    
                    if first_part_duration > 0:
                        job_label = job_names[task["job"]] if job_names and isinstance(task["job"], int) else f"Job {task['job']}"
                        items.append({
                            "id": f"{machine_id}_{idx}_part1",
                            "group": machine_id,
                            "title": f"{job_label} (1/2)",
                            "start_time": actual_start.isoformat(),
                            "end_time": first_part_end.isoformat(),
                            "job_info": task,
                            "task_type": "production"
                        })
                    
                    if second_part_duration > 0:
                        actual_start = second_part_start
                        actual_end = actual_start + timedelta(minutes=second_part_duration)
                        job_label = job_names[task["job"]] if job_names and isinstance(task["job"], int) else f"Job {task['job']}"
                        items.append({
                            "id": f"{machine_id}_{idx}_part2",
                            "group": machine_id,
                            "title": f"{job_label} (2/2)",
                            "start_time": actual_start.isoformat(),
                            "end_time": actual_end.isoformat(),
                            "job_info": task,
                            "task_type": "production"
                        })
                else:
                    # Décaler toute la tâche après la pause
                    actual_start = lunch_end
                    actual_end = actual_start + timedelta(minutes=duration_minutes)
                    job_label = job_names[task["job"]] if job_names and isinstance(task["job"], int) else f"Job {task['job']}"
                    items.append({
                        "id": f"{machine_id}_{idx}",
                        "group": machine_id,
                        "title": job_label,
                        "start_time": actual_start.isoformat(),
                        "end_time": actual_end.isoformat(),
                        "job_info": task,
                        "task_type": "production"
                    })
            else:
                # Pas de conflit avec la pause déjeuner
                job_label = job_names[task["job"]] if job_names and isinstance(task["job"], int) else f"Job {task['job']}"
                items.append({
                    "id": f"{machine_id}_{idx}",
                    "group": machine_id,
                    "title": job_label,
                    "start_time": actual_start.isoformat(),
                    "end_time": actual_end.isoformat(),
                    "job_info": task,
                    "task_type": "production"
                })
            
            # Mettre à jour le temps de la machine
            machine_current_time[machine_id] = actual_end

    return {
        "groups": groups,
        "items": items,
        "opening_hours": opening_hours,
        "total_machines": len(groups),
        "planning_period": {
            "start": base_datetime.isoformat(),
            "estimated_end": max(machine_current_time.values()).isoformat() if machine_current_time else base_datetime.isoformat()
        }
    }



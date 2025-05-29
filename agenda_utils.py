from datetime import datetime, timedelta
import pytz

def generer_agenda_json(result, start_datetime_str, opening_hours, weekend_days, jours_feries, unite="heures"):
    base_datetime = datetime.fromisoformat(start_datetime_str)
    unit_multipliers = {"minutes": 1, "heures": 60, "jours": 1440}
    minute_multiplier = unit_multipliers.get(unite, 60)

    # Préparer groupes
    groups = [
        {"id": int(mid), "title": f"Machine {mid}"} for mid in result["machines"].keys()
    ]

    # Convertir jours fériés et congés en datetime.date
    feries = {datetime.fromisoformat(d).date() for d in jours_feries}
    weekends = {"samedi": 5, "dimanche": 6}
    weekend_indexes = {weekends[d] for d in weekend_days if d in weekends}

    # Créer les items (tâches)
    items = []
    for machine_id, tasks in result["machines"].items():
        for idx, t in enumerate(tasks):
            start_offset_min = t["start"] * minute_multiplier
            end_offset_min = (t["start"] + t["duration"]) * minute_multiplier

            # Convertir en datetime
            start_dt = base_datetime + timedelta(minutes=start_offset_min)
            end_dt = base_datetime + timedelta(minutes=end_offset_min)

            # Vérifier si la tâche tombe sur un jour exclu
            if start_dt.date() in feries or start_dt.weekday() in weekend_indexes:
                continue  # Sauter cette tâche

            job_name = t.get("job_name", f"Job {t['job']}")
            items.append({
                "id": f"{machine_id}_{idx}",
                "group": int(machine_id),
                "title": job_name,
                "start_time": start_dt.isoformat(),
                "end_time": end_dt.isoformat()
            })

    return {"groups": groups, "items": items}

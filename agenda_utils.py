from datetime import datetime, timedelta

def generer_agenda_json(result, start_datetime_str, opening_hours, weekend_days, jours_feries, unite="heures", machine_names=None, job_names=None):
    base_datetime = datetime.fromisoformat(start_datetime_str)
    unit_multipliers = {"minutes": 1, "heures": 60, "jours": 1440}
    minute_multiplier = unit_multipliers.get(unite, 60)

    weekend_indices = {
        "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4,
        "samedi": 5, "dimanche": 6
    }
    weekend_indexes = {weekend_indices[d] for d in weekend_days if d in weekend_indices}
    feries = {datetime.fromisoformat(d).date() for d in jours_feries}

    # Groupes = machines
    groups = [
        {"id": int(mid), "title": machine_names[int(mid)] if machine_names else f"Machine {mid}"}
        for mid in result["machines"].keys()
    ]

    # Items = tâches
    items = []
    for machine_id, tasks in result["machines"].items():
        for idx, t in enumerate(tasks):
            start_offset_min = t["start"] * minute_multiplier
            end_offset_min = (t["start"] + t["duration"]) * minute_multiplier

            start_dt = base_datetime + timedelta(minutes=start_offset_min)
            end_dt = base_datetime + timedelta(minutes=end_offset_min)

            if start_dt.date() in feries or start_dt.weekday() in weekend_indexes:
                continue

            job_label = job_names[t["job"]] if job_names else f"Job {t['job']}"
            items.append({
                "id": f"{machine_id}_{idx}",
                "group": int(machine_id),
                "title": job_label,
                "start_time": start_dt.isoformat(),
                "end_time": end_dt.isoformat()
            })

    return {"groups": groups, "items": items}


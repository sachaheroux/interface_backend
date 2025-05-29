from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io

def generer_agenda_reel(result, start_datetime_str, opening_hours, weekend_days, jours_feries, unite="heures"):
    start_datetime = datetime.fromisoformat(start_datetime_str)
    open_start = datetime.strptime(opening_hours["start"], "%H:%M").time()
    open_end = datetime.strptime(opening_hours["end"], "%H:%M").time()
    delta_unite = {"minutes": timedelta(minutes=1), "heures": timedelta(hours=1), "jours": timedelta(days=1)}[unite]

    jours_feries_dt = [datetime.strptime(j, "%Y-%m-%d").date() for j in jours_feries]
    weekend_indices = {"lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4, "samedi": 5, "dimanche": 6}
    jours_exclus = [weekend_indices[j] for j in weekend_days]

    def trouver_prochaine_heure_disponible(dt):
        while True:
            jour = dt.date()
            if (dt.weekday() in jours_exclus or jour in jours_feries_dt or not (open_start <= dt.time() <= open_end)):
                dt += timedelta(minutes=1)
                if dt.time() > open_end:
                    dt = datetime.combine(dt.date() + timedelta(days=1), open_start)
                continue
            break
        return dt

    fig, ax = plt.subplots(figsize=(12, 5))
    colors = ["#4f46e5", "#f59e0b", "#10b981", "#ef4444", "#6366f1", "#8b5cf6", "#14b8a6", "#f97316"]
    y_labels = []
    bars = []

    for m_idx, (machine, tasks) in enumerate(result["machines"].items()):
        for t in tasks:
            job_id = t["job"]
            start_offset = t["start"]
            duration_units = t["duration"]

            start_dt = start_datetime
            units_passed = 0
            while units_passed < start_offset:
                start_dt += delta_unite
                start_dt = trouver_prochaine_heure_disponible(start_dt)
                units_passed += 1

            end_dt = start_dt
            units_used = 0
            while units_used < duration_units:
                end_dt += delta_unite
                end_dt = trouver_prochaine_heure_disponible(end_dt)
                units_used += 1

            label = f"Job {job_id} sur {machine}"
            y = len(y_labels)
            y_labels.append(label)
            ax.barh(y, end_dt - start_dt, left=start_dt, color=colors[job_id % len(colors)])
            ax.text(start_dt + (end_dt - start_dt) / 2, y, f"J{job_id}", va="center", ha="center", color="white", fontsize=8)

    ax.set_yticks(range(len(y_labels)))
    ax.set_yticklabels(y_labels)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%m %H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    ax.set_xlabel("Temps réel")
    ax.set_title("Agenda réel - SPT")
    fig.autofmt_xdate()
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf

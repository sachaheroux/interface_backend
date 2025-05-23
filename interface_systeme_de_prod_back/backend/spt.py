from collections import defaultdict
from operator import itemgetter


def schedule(jobs_data, due_dates):
    machine_time = defaultdict(int)  # Temps courant de chaque machine
    job_time = defaultdict(int)      # Temps courant pour chaque job
    machines = defaultdict(list)     # Planning machine : tâches ordonnées
    completion_times = {}            # Temps de complétion de chaque job

    # 1. Calcul des durées totales par job (SPT)
    job_sums = [(j, sum(t for _, t in job)) for j, job in enumerate(jobs_data)]
    sorted_jobs = sorted(job_sums, key=itemgetter(1))
    sequence = [j for j, _ in sorted_jobs]

    cumulative_delay = 0

    for j in sequence:
        job = jobs_data[j]

        for i, (m, t) in enumerate(job):
            start_time = max(machine_time[m], job_time[j])
            end_time = start_time + t

            machines[m].append({
                "job": j,
                "task": i,
                "start": start_time,
                "duration": t
            })

            machine_time[m] = end_time
            job_time[j] = end_time

        completion_times[j] = job_time[j]

        # Calcul du retard si en retard par rapport à due_date
        delay = max(completion_times[j] - due_dates[j], 0)
        cumulative_delay += delay

    makespan = max(machine_time.values())
    flowtime = sum(completion_times.values()) / len(completion_times)

    return {
        "makespan": makespan,
        "flowtime": flowtime,
        "retard_cumule": cumulative_delay,
        "completion_times": completion_times,
        "machines": machines
    }

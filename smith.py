import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

def smith_algorithm(jobs):
    if not jobs or not all(len(job) == 2 for job in jobs):
        raise ValueError("Chaque job doit être une liste de deux éléments [durée, due_date].")

    # Tri des jobs par date d'échéance croissante
    sorted_jobs = sorted(enumerate(jobs, start=1), key=lambda x: x[1][1])

    total_execution_time = sum(job[1][0] for job in sorted_jobs)
    sequence = []

    while sorted_jobs:
        admissible_jobs = [job for job in sorted_jobs if job[1][1] >= total_execution_time]
        if admissible_jobs:
            max_job = max(admissible_jobs, key=lambda x: x[1][0])
            sequence.insert(0, max_job[0])
            sorted_jobs.remove(max_job)
            total_execution_time -= max_job[1][0]
        else:
            raise ValueError("Aucun job admissible trouvé. Tous les jobs ont une date due trop courte.")

    flowtime = sum((len(sequence) - i) * jobs[job - 1][0] for i, job in enumerate(sequence)) / len(sequence)
    numerator = sum((len(sequence) - i) * jobs[job - 1][0] for i, job in enumerate(sequence))
    denominator = sum(job[0] for job in jobs)
    N = numerator / denominator if denominator else 0

    cumulative_delay = 0
    for i, job in enumerate(sequence):
        executed = sum(jobs[j - 1][0] for j in sequence[:i + 1])
        if executed > jobs[job - 1][1]:
            cumulative_delay += executed - jobs[job - 1][1]

    return {
        "sequence": sequence,
        "flowtime": flowtime,
        "N": N,
        "cumulative_delay": cumulative_delay
    }

def generate_gantt(sequence, jobs, unite="heures", job_names=None):
    fig, ax = plt.subplots(figsize=(8, 2))
    colors = plt.cm.get_cmap('tab10', len(jobs))

    cumulative_time = 0
    for i, job in enumerate(sequence):
        idx = job - 1
        duration = jobs[idx][0]
        label = job_names[idx] if job_names and idx < len(job_names) else f"Job {job}"

        ax.barh(1, duration, left=cumulative_time, height=0.3, color=colors(i), edgecolor='black')
        ax.text(cumulative_time + duration / 2, 1, label, ha='center', va='center', color='white', fontsize=8)
        cumulative_time += duration

    ax.set_xlim(0, cumulative_time)
    ax.set_xlabel(f"Temps ({unite})")
    ax.set_yticks([1])
    ax.set_yticklabels(["Séquence"])
    ax.spines[['left', 'top', 'right']].set_visible(False)
    ax.invert_yaxis()

    legend_elements = [
        mpatches.Patch(color=colors(i), label=job_names[sequence[i] - 1] if job_names else f"Job {sequence[i]}")
        for i in range(len(sequence))
    ]
    ax.legend(handles=legend_elements, bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.subplots_adjust(right=0.8)
    return fig


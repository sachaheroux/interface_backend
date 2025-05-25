import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches

def smith_algorithm(jobs):
    if not jobs or not all(len(job) == 2 for job in jobs):
        raise ValueError("Chaque job doit être une liste de deux éléments [durée, due_date].")

    # Tri des jobs par date d'échéance croissante
    sorted_jobs = sorted(enumerate(jobs, start=1), key=lambda x: x[1][1])

    # Calcul de τ
    total_execution_time = sum(job[1][0] for job in sorted_jobs)

    # Séquence des jobs
    sequence = []

    while sorted_jobs:
        admissible_jobs = [job for job in sorted_jobs if job[1][1] >= total_execution_time]

        if admissible_jobs:
            max_execution_time_job = max(admissible_jobs, key=lambda x: x[1][0])
            sequence.insert(0, max_execution_time_job[0])  # Insertion au début de la séquence
            sorted_jobs.remove(max_execution_time_job)
            total_execution_time -= max_execution_time_job[1][0]
        else:
            break

    if not sequence:
        raise ValueError("Aucune séquence valide générée. Vérifiez les dates dues des jobs.")

    # Calcul du flowtime
    flowtime = sum((len(sequence) - i) * jobs[job-1][0] for i, job in enumerate(sequence)) / len(sequence)

    # Calcul du nombre de jobs
    numerator = sum((len(sequence) - i) * jobs[job-1][0] for i, job in enumerate(sequence))
    denominator = sum(job[0] for job in jobs)
    N = numerator / denominator if denominator else 0

    # Calcul du retard cumulé
    cumulative_delay = 0
    for i, job in enumerate(sequence):
        sum_execution_time = sum(jobs[j-1][0] for j in sequence[:i + 1])
        if sum_execution_time > jobs[job-1][1]:
            cumulative_delay += sum_execution_time - jobs[job-1][1]

    return {
        "sequence": sequence,
        "flowtime": flowtime,
        "N": N,
        "cumulative_delay": cumulative_delay
    }

def generate_gantt(sequence, jobs):
    fig, ax = plt.subplots(figsize=(8, 2))

    y_ticks = [1]
    y_labels = ["Jobs"]
    colors = plt.cm.get_cmap('tab10', len(jobs))

    cumulative_time = 0
    for i, job in enumerate(sequence):
        job_execution_time = jobs[job-1][0]
        ax.barh(y_ticks[0], job_execution_time, left=cumulative_time, height=0.2, color=colors(i), edgecolor='black')
        ax.text(cumulative_time + job_execution_time/2, y_ticks[0], str(job_execution_time), ha='center', va='center', color='white', fontsize=8)
        cumulative_time += job_execution_time

    ax.set_xlim(0, cumulative_time)
    ax.set_xlabel("Temps de fabrication")
    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels)
    ax.spines['left'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.invert_yaxis()

    legend_elements = [mpatches.Patch(color=colors(i), label=f"Job {sequence[i]}") for i in range(len(sequence))]
    ax.legend(handles=legend_elements, bbox_to_anchor=(1.05, 1), loc='upper left')

    plt.subplots_adjust(right=0.8)
    return fig

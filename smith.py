import matplotlib.pyplot as plt
from typing import List, Tuple
from matplotlib import cm
from collections import namedtuple
import numpy as np
from collections import deque, defaultdict

Job = namedtuple("Job", ["duration", "due_date"])

def smith_algorithm(jobs_data: List[Tuple[float, float]]):
    jobs = [Job(*j) for j in jobs_data]
    sorted_jobs = sorted(enumerate(jobs, start=1), key=lambda x: x[1].due_date)
    total_execution_time = sum(job.duration for _, job in sorted_jobs)
    sequence = []

    queue = deque(sorted_jobs)

    while queue:
        admissible_jobs = [job for job in queue if job[1].due_date >= total_execution_time]
        if admissible_jobs:
            max_job = max(admissible_jobs, key=lambda x: x[1].duration)
            sequence.insert(0, max_job[0])
            queue.remove(max_job)
            total_execution_time -= max_job[1].duration
        else:
            break

    flowtime = sum((len(sequence) - i) * jobs[job - 1].duration for i, job in enumerate(sequence)) / len(sequence)
    numerator = sum((len(sequence) - i) * jobs[job - 1].duration for i, job in enumerate(sequence))
    denominator = sum(job.duration for job in jobs)
    N = numerator / denominator

    cumulative_delay = 0
    for i, job in enumerate(sequence):
        sum_exec_time = sum(jobs[j - 1].duration for j in sequence[:i + 1])
        if sum_exec_time > jobs[job - 1].due_date:
            cumulative_delay += sum_exec_time - jobs[job - 1].due_date

    return {
        "sequence": sequence,
        "flowtime": flowtime,
        "N": N,
        "cumulative_delay": cumulative_delay
    }

def generate_gantt(sequence: List[int], jobs_data: List[Tuple[float, float]]):
    jobs = [Job(*j) for j in jobs_data]
    colors = cm.get_cmap('tab10', len(jobs))
    fig, ax = plt.subplots(figsize=(8, 2))

    time = 0
    for i, job_id in enumerate(sequence):
        dur = jobs[job_id - 1].duration
        ax.barh(1, dur, left=time, color=colors(i), edgecolor='black', height=0.3)
        ax.text(time + dur/2, 1, f"{dur}", ha='center', va='center', color='white', fontsize=8)
        time += dur

    ax.set_xlim(0, time)
    ax.set_yticks([1])
    ax.set_yticklabels(["Jobs"])
    ax.set_xlabel("Temps de fabrication")
    ax.invert_yaxis()

    patches = [plt.Rectangle((0, 0), 1, 1, color=colors(i), edgecolor='black', label=f"Job {sequence[i]}") for i in range(len(sequence))]
    ax.legend(handles=patches, bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.subplots_adjust(right=0.8)

    return fig
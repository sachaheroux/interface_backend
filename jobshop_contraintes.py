import collections
from ortools.sat.python import cp_model


def planifier_jobshop_contraintes(job_names, machine_names, jobs_data, due_dates):
    machines_count = 1 + max(task[0] for job in jobs_data for task in job)
    all_machines = range(machines_count)
    horizon = sum(task[1] for job in jobs_data for task in job)

    model = cp_model.CpModel()
    task_type = collections.namedtuple('task_type', 'start end interval')
    assigned_task_type = collections.namedtuple('assigned_task_type',
                                                'start job index duration')

    all_tasks = {}
    machine_to_intervals = collections.defaultdict(list)

    for job_id, job in enumerate(jobs_data):
        for task_id, task in enumerate(job):
            machine = task[0]
            duration = task[1]
            suffix = '_%i_%i' % (job_id, task_id)
            start_var = model.NewIntVar(0, horizon, 'start' + suffix)
            end_var = model.NewIntVar(0, horizon, 'end' + suffix)
            interval_var = model.NewIntervalVar(start_var, duration, end_var,
                                                'interval' + suffix)
            all_tasks[job_id, task_id] = task_type(start=start_var,
                                                   end=end_var,
                                                   interval=interval_var)
            machine_to_intervals[machine].append(interval_var)

    for machine in all_machines:
        model.AddNoOverlap(machine_to_intervals[machine])

    for job_id, job in enumerate(jobs_data):
        for task_id in range(len(job) - 1):
            model.Add(all_tasks[job_id, task_id +
                                1].start >= all_tasks[job_id, task_id].end)

    obj_var = model.NewIntVar(0, horizon, 'makespan')
    model.AddMaxEquality(obj_var, [
        all_tasks[job_id, len(job) - 1].end
        for job_id, job in enumerate(jobs_data)
    ])
    model.Minimize(obj_var)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        assigned_jobs = collections.defaultdict(list)
        completion_times = [0]*len(jobs_data)  # completion time for each job
        total_delay = 0  # cumulative delay of jobs

        for job_id, job in enumerate(jobs_data):
            for task_id, task in enumerate(job):
                machine = task[0]
                assigned_jobs[machine].append(
                    assigned_task_type(start=solver.Value(
                        all_tasks[job_id, task_id].start),
                                       job=job_id,
                                       index=task_id,
                                       duration=task[1]))
                completion_times[job_id] = max(completion_times[job_id], solver.Value(all_tasks[job_id, task_id].end))

        makespan = solver.ObjectiveValue()
        flowtime = sum(completion_times) / len(jobs_data)

        for i, completion_time in enumerate(completion_times):
            delay = max(0, completion_time - due_dates[i])
            total_delay += delay

        return {
            "makespan": makespan,
            "flowtime": flowtime,
            "retard_cumule": total_delay,
            "completion_times": completion_times,
            "planification": {machine_names[machine]: tasks for machine, tasks in assigned_jobs.items()}
        }
    else:
        raise Exception('No solution found.') 
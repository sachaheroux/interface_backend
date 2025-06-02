from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from typing import List
import matplotlib.pyplot as plt
import io

import spt
import edd
import johnson
import johnson_modifie
import smith
import contraintes
import jobshop_spt
import jobshop_edd
from validation import validate_jobs_data, ExtendedRequest, JohnsonRequest, JohnsonModifieRequest, SmithRequest, JobshopSPTRequest
from agenda_utils import generer_agenda_json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------- Gantt utilitaire -----------

def create_gantt_figure(result, title: str, unite="heures", job_names=None, machine_names=None):
    fig, ax = plt.subplots(figsize=(10, 3))
    colors = ["#4f46e5", "#f59e0b", "#10b981", "#ef4444", "#6366f1", "#8b5cf6", "#14b8a6", "#f97316"]

    for m_idx, (m, tasks) in enumerate(result["machines"].items()):
        label = machine_names[int(m)] if machine_names else f"Machine {int(m)}"
        for t in tasks:
            job_idx = t["job"] if isinstance(t["job"], int) else job_names.index(t["job"])
            job_label = job_names[job_idx] if job_names else f"J{job_idx}"
            color = colors[job_idx % len(colors)]
            ax.barh(label, t["duration"], left=t["start"], color=color)
            ax.text(t["start"] + t["duration"] / 2, label, job_label,
                    va="center", ha="center", color="white", fontsize=8)

    ax.set_xlabel(f"Temps ({unite})")
    ax.invert_yaxis()
    ax.set_title(title)
    plt.tight_layout()
    return fig

# ----------- Jobshop SPT -----------

@app.post("/jobshop/spt")
def run_jobshop_spt(request: JobshopSPTRequest):
    try:
        result = jobshop_spt.planifier_jobshop_spt(request.job_names, request.machine_names, request.jobs_data, request.due_dates)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/jobshop/spt/gantt")
def run_jobshop_spt_gantt(request: JobshopSPTRequest):
    try:
        result = jobshop_spt.planifier_jobshop_spt(request.job_names, request.machine_names, request.jobs_data, request.due_dates)
        machines_dict = {}
        for t in result["schedule"]:
            m_idx = request.machine_names.index(t["machine"])
            machines_dict.setdefault(m_idx, []).append({
                "job": t["job"],
                "start": t["start"],
                "duration": t["end"] - t["start"]
            })
        result_formatted = {"machines": machines_dict}
        fig = create_gantt_figure(result_formatted, "Diagramme de Gantt - Jobshop SPT",
                                  unite=request.unite,
                                  job_names=request.job_names,
                                  machine_names=request.machine_names)
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------- Jobshop EDD -----------

@app.post("/jobshop/edd")
def run_jobshop_edd(request: JobshopSPTRequest):
    try:
        result = jobshop_edd.planifier_jobshop_edd(request.job_names, request.machine_names, request.jobs_data, request.due_dates)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/jobshop/edd/gantt")
def run_jobshop_edd_gantt(request: JobshopSPTRequest):
    try:
        result = jobshop_edd.planifier_jobshop_edd(request.job_names, request.machine_names, request.jobs_data, request.due_dates)
        machines_dict = {}
        for t in result["schedule"]:
            m_idx = request.machine_names.index(t["machine"])
            machines_dict.setdefault(m_idx, []).append({
                "job": t["job"],
                "start": t["start"],
                "duration": t["end"] - t["start"]
            })
        result_formatted = {"machines": machines_dict}
        fig = create_gantt_figure(result_formatted, "Diagramme de Gantt - Jobshop EDD",
                                  unite=request.unite,
                                  job_names=request.job_names,
                                  machine_names=request.machine_names)
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------- Algorithme SPT -----------

@app.post("/spt")
def run_spt(request: ExtendedRequest):
    try:
        validate_jobs_data(request.jobs_data, request.due_dates)
        result = spt.schedule(request.jobs_data, request.due_dates)
        return {
            "makespan": result["makespan"],
            "flowtime": result["flowtime"],
            "retard_cumule": result["retard_cumule"],
            "completion_times": result["completion_times"],
            "planification": {request.machine_names[int(m)]: tasks for m, tasks in result["machines"].items()}
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/spt/gantt")
def run_spt_gantt(request: ExtendedRequest):
    try:
        validate_jobs_data(request.jobs_data, request.due_dates)
        result = spt.schedule(request.jobs_data, request.due_dates)
        fig = create_gantt_figure(result, "Diagramme de Gantt - Flowshop SPT",
                                  unite=request.unite,
                                  job_names=request.job_names,
                                  machine_names=request.machine_names)
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/spt/agenda")
def run_spt_agenda(request: ExtendedRequest):
    try:
        validate_jobs_data(request.jobs_data, request.due_dates)
        result = spt.schedule(request.jobs_data, request.due_dates)
        agenda_json = generer_agenda_json(
            result=result,
            start_datetime_str=request.agenda_start_datetime,
            opening_hours=request.opening_hours,
            weekend_days=request.weekend_days,
            jours_feries=request.jours_feries,
            unite=request.unite,
            machine_names=request.machine_names,
            job_names=request.job_names
        )
        return JSONResponse(content=agenda_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------- EDD -----------

@app.post("/edd")
def run_edd(request: ExtendedRequest):
    try:
        validate_jobs_data(request.jobs_data, request.due_dates)
        result = edd.schedule(request.jobs_data, request.due_dates)
        return {
            "makespan": result["makespan"],
            "flowtime": result["flowtime"],
            "retard_cumule": result["retard_cumule"],
            "completion_times": result["completion_times"],
            "planification": {request.machine_names[int(m)]: tasks for m, tasks in result["machines"].items()}
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/edd/gantt")
def run_edd_gantt(request: ExtendedRequest):
    try:
        validate_jobs_data(request.jobs_data, request.due_dates)
        result = edd.schedule(request.jobs_data, request.due_dates)
        fig = create_gantt_figure(result, "Diagramme de Gantt - Flowshop EDD",
                                  unite=request.unite,
                                  job_names=request.job_names,
                                  machine_names=request.machine_names)
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------- Johnson -----------

@app.post("/johnson")
def run_johnson(request: JohnsonRequest):
    try:
        result = johnson.schedule(request.jobs_data, request.due_dates)
        return {
            "sequence": result["sequence"],
            "makespan": result["makespan"],
            "flowtime": result["flowtime"],
            "retard_cumule": result["retard_cumule"],
            "completion_times": result["completion_times"],
            "planification": {request.machine_names[int(m)]: tasks for m, tasks in result["machines"].items()}
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/johnson/gantt")
def run_johnson_gantt(request: JohnsonRequest):
    try:
        result = johnson.schedule(request.jobs_data, request.due_dates)
        fig = create_gantt_figure(result, "Diagramme de Gantt - Johnson",
                                  unite=request.unite,
                                  job_names=request.job_names,
                                  machine_names=request.machine_names)
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------- Johnson Modifié -----------

@app.post("/johnson_modifie")
def run_johnson_modifie(request: JohnsonModifieRequest):
    try:
        result = johnson_modifie.schedule(request.jobs_data, request.due_dates)
        return {
            "sequence": result["sequence"],
            "makespan": result["makespan"],
            "flowtime": result["flowtime"],
            "retard_cumule": result["retard_cumule"],
            "completion_times": result["completion_times"],
            "planification": {request.machine_names[int(m)]: tasks for m, tasks in result["machines"].items()}
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/johnson_modifie/gantt")
def run_johnson_modifie_gantt(request: JohnsonModifieRequest):
    try:
        result = johnson_modifie.schedule(request.jobs_data, request.due_dates)
        fig = create_gantt_figure(result, "Diagramme de Gantt - Johnson modifié",
                                  unite=request.unite,
                                  job_names=request.job_names,
                                  machine_names=request.machine_names)
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------- Smith -----------

@app.post("/smith")
def run_smith(request: SmithRequest):
    try:
        result = smith.smith_algorithm(request.jobs)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/smith/gantt")
def run_smith_gantt(request: SmithRequest):
    try:
        result = smith.smith_algorithm(request.jobs)
        fig = smith.generate_gantt(result["sequence"], request.jobs,
                                   unite=request.unite,
                                   job_names=request.job_names)
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------- Contraintes -----------

@app.post("/contraintes")
def run_contraintes(request: ExtendedRequest):
    try:
        validate_jobs_data(request.jobs_data, request.due_dates)
        result = contraintes.schedule(request.jobs_data, request.due_dates)
        return {
            "makespan": result["makespan"],
            "flowtime": result["flowtime"],
            "retard_cumule": result["retard_cumule"],
            "completion_times": result["completion_times"],
            "planification": {request.machine_names[int(m)]: tasks for m, tasks in result["machines"].items()}
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/contraintes/gantt")
def run_contraintes_gantt(request: ExtendedRequest):
    try:
        validate_jobs_data(request.jobs_data, request.due_dates)
        result = contraintes.schedule(request.jobs_data, request.due_dates)
        fig = create_gantt_figure(result, "Diagramme de Gantt - Contraintes (CP)",
                                  unite=request.unite,
                                  job_names=request.job_names,
                                  machine_names=request.machine_names)
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))









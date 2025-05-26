from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List
import spt
import edd
import johnson
import johnson_modifie
import smith
import contraintes
from validation import validate_jobs_data
import matplotlib.pyplot as plt
import io

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SPTRequest(BaseModel):
    jobs_data: List[List[List[float]]]
    due_dates: List[float]

class JohnsonRequest(BaseModel):
    jobs_data: List[List[float]]
    due_dates: List[float]

class SmithRequest(BaseModel):
    jobs: List[List[float]]

@app.post("/spt")
def run_spt(request: SPTRequest):
    try:
        validate_jobs_data(request.jobs_data, request.due_dates)
        result = spt.schedule(request.jobs_data, request.due_dates)

        planification = {
            f"Machine {machine}": tasks
            for machine, tasks in result["machines"].items()
        }

        return {
            "makespan": result["makespan"],
            "flowtime": result["flowtime"],
            "retard_cumule": result["retard_cumule"],
            "completion_times": result["completion_times"],
            "planification": planification
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/spt/gantt")
def run_spt_gantt(request: SPTRequest):
    try:
        validate_jobs_data(request.jobs_data, request.due_dates)
        result = spt.schedule(request.jobs_data, request.due_dates)

        fig, ax = plt.subplots(figsize=(10, 3))
        colors = ["#4f46e5", "#f59e0b", "#10b981", "#ef4444", "#6366f1"]

        for m, tasks in result["machines"].items():
            for t in tasks:
                ax.barh(f"Machine {m}", t["duration"], left=t["start"], color=colors[t["job"] % len(colors)])
                ax.text(t["start"] + t["duration"] / 2, f"Machine {m}", f"J{t['job']}",
                        va="center", ha="center", color="white", fontsize=8)

        ax.set_xlabel("Temps")
        ax.invert_yaxis()
        ax.set_title("Diagramme de Gantt - Flowshop SPT")

        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/edd")
def run_edd(request: SPTRequest):
    try:
        validate_jobs_data(request.jobs_data, request.due_dates)
        result = edd.schedule(request.jobs_data, request.due_dates)

        planification = {
            f"Machine {machine}": tasks
            for machine, tasks in result["machines"].items()
        }

        return {
            "makespan": result["makespan"],
            "flowtime": result["flowtime"],
            "retard_cumule": result["retard_cumule"],
            "completion_times": result["completion_times"],
            "planification": planification
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/edd/gantt")
def run_edd_gantt(request: SPTRequest):
    try:
        validate_jobs_data(request.jobs_data, request.due_dates)
        result = edd.schedule(request.jobs_data, request.due_dates)

        fig, ax = plt.subplots(figsize=(10, 3))
        colors = ["#4f46e5", "#f59e0b", "#10b981", "#ef4444", "#6366f1"]

        for m, tasks in result["machines"].items():
            for t in tasks:
                ax.barh(f"Machine {m}", t["duration"], left=t["start"], color=colors[t["job"] % len(colors)])
                ax.text(t["start"] + t["duration"] / 2, f"Machine {m}", f"J{t['job']}",
                        va="center", ha="center", color="white", fontsize=8)

        ax.set_xlabel("Temps")
        ax.invert_yaxis()
        ax.set_title("Diagramme de Gantt - Flowshop EDD")

        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/johnson")
def run_johnson(request: JohnsonRequest):
    try:
        result = johnson.schedule(request.jobs_data, request.due_dates)

        planification = {
            f"Machine {machine}": tasks
            for machine, tasks in result["machines"].items()
        }

        return {
            "sequence": result["sequence"],
            "makespan": result["makespan"],
            "flowtime": result["flowtime"],
            "retard_cumule": result["retard_cumule"],
            "completion_times": result["completion_times"],
            "planification": planification
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/johnson/gantt")
def run_johnson_gantt(request: JohnsonRequest):
    try:
        result = johnson.schedule(request.jobs_data, request.due_dates)

        fig, ax = plt.subplots(figsize=(10, 3))
        colors = ["#4f46e5", "#f59e0b", "#10b981", "#ef4444", "#6366f1"]

        for m, tasks in result["machines"].items():
            for t in tasks:
                ax.barh(f"Machine {m+1}", t["duration"], left=t["start"], color=colors[t["job"] % len(colors)])
                ax.text(t["start"] + t["duration"] / 2, f"Machine {m+1}", f"J{t['job']+1}",
                        va="center", ha="center", color="white", fontsize=8)

        ax.set_xlabel("Temps")
        ax.invert_yaxis()
        ax.set_title("Diagramme de Gantt - Johnson")

        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/johnson_modifie")
def run_johnson_modifie(request: JohnsonRequest):
    try:
        result = johnson_modifie.schedule(request.jobs_data, request.due_dates)

        planification = {
            f"Machine {machine}": tasks
            for machine, tasks in result["machines"].items()
        }

        return {
            "sequence": result["sequence"],
            "makespan": result["makespan"],
            "flowtime": result["flowtime"],
            "retard_cumule": result["retard_cumule"],
            "completion_times": result["completion_times"],
            "planification": planification
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/johnson_modifie/gantt")
def run_johnson_modifie_gantt(request: JohnsonRequest):
    try:
        result = johnson_modifie.schedule(request.jobs_data, request.due_dates)

        fig, ax = plt.subplots(figsize=(10, 3))
        colors = ["#4f46e5", "#f59e0b", "#10b981", "#ef4444", "#6366f1"]

        for m, tasks in result["machines"].items():
            for t in tasks:
                ax.barh(f"Machine {m+1}", t["duration"], left=t["start"], color=colors[t["job"] % len(colors)])
                ax.text(t["start"] + t["duration"] / 2, f"Machine {m+1}", f"J{t['job']+1}",
                        va="center", ha="center", color="white", fontsize=8)

        ax.set_xlabel("Temps")
        ax.invert_yaxis()
        ax.set_title("Diagramme de Gantt - Johnson modifié")

        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

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
        fig = smith.generate_gantt(result["sequence"], request.jobs)

        buf = io.BytesIO()
        plt.tight_layout()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/contraintes")
def run_contraintes(request: SPTRequest):
    try:
        validate_jobs_data(request.jobs_data, request.due_dates)
        result = contraintes.schedule(request.jobs_data, request.due_dates)

        planification = {
            f"Machine {m}": tasks for m, tasks in result["machines"].items()
        }

        return {
            "makespan": result["makespan"],
            "flowtime": result["flowtime"],
            "retard_cumule": result["retard_cumule"],
            "completion_times": result["completion_times"],
            "planification": planification
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/contraintes/gantt")
def run_contraintes_gantt(request: SPTRequest):
    try:
        validate_jobs_data(request.jobs_data, request.due_dates)
        result = contraintes.schedule(request.jobs_data, request.due_dates)

        fig, ax = plt.subplots(figsize=(10, 3))
        colors = ["#4f46e5", "#f59e0b", "#10b981", "#ef4444", "#6366f1", "#8b5cf6", "#14b8a6", "#f97316"]

        for m, tasks in result["machines"].items():
            for t in tasks:
                ax.barh(f"Machine {m}", t["duration"], left=t["start"], color=colors[t["job"] % len(colors)])
                ax.text(t["start"] + t["duration"] / 2, f"Machine {m}", f"J{t['job']}",
                        va="center", ha="center", color="white", fontsize=8)

        ax.set_xlabel("Temps")
        ax.invert_yaxis()
        ax.set_title("Diagramme de Gantt - Contraintes (CP)")

        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


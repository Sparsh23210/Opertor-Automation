import uuid
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from backend.config import settings, resolve_safe_path
from backend.database.session import SessionLocal, init_system_db
from backend.database.models import TaskModel, EvidenceModel, ArtifactModel, ApprovalModel
from backend.tools.registry import registry
from backend.engine.executor import run_task_execution
from backend.engine.approvals import approve_step_action, reject_step_action, cancel_task_execution
from backend.test_portal import portal_router

# Ensure DB tables are initialized
init_system_db()

app = FastAPI(
    title="Company Automation - Autonomous Operations Operator",
    description="Production-grade AI Employee & Autonomous Company Operations Operator",
    version="1.0.0"
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount local browser automation test portal
app.include_router(portal_router)

# Request schemas
class CreateTaskRequest(BaseModel):
    request: str = Field(..., description="Natural language request for company operation")
    auto_run: bool = Field(default=True, description="Whether to immediately trigger execution")

class ApprovalActionRequest(BaseModel):
    approval_id: str
    notes: Optional[str] = ""

# Endpoints
@app.get("/api/health")
def get_health():
    db = SessionLocal()
    try:
        task_count = db.query(TaskModel).count()
        return {
            "status": "healthy",
            "execution_mode": settings.EXECUTION_MODE,
            "registered_tools_count": len(registry.list_tools()),
            "tasks_count": task_count,
            "reference_date": settings.REFERENCE_DATE,
            "gemini_configured": bool(settings.GEMINI_API_KEY),
            "gemini_model": settings.GEMINI_MODEL
        }
    finally:
        db.close()

@app.get("/api/tools")
def get_tools():
    return {"tools": registry.list_tools()}

@app.get("/api/policies")
def get_policies():
    policies = []
    if settings.POLICIES_DIR.exists():
        for f in settings.POLICIES_DIR.glob("*.md"):
            policies.append({
                "filename": f.name,
                "title": f.stem.replace("_", " ").title(),
                "size_bytes": f.stat().st_size
            })
    return {"policies": policies}

@app.post("/api/tasks")
def create_task(req: CreateTaskRequest):
    request_text = req.request.strip()
    if not request_text:
        raise HTTPException(status_code=400, detail="Task request cannot be empty.")

    task_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        new_task = TaskModel(
            id=task_id,
            original_request=request_text,
            normalized_goal="Evaluating request intent...",
            status="pending"
        )
        db.add(new_task)
        db.commit()
        db.refresh(new_task)
        task_dict = new_task.to_dict()
    finally:
        db.close()

    if req.auto_run:
        task_dict = run_task_execution(task_id)

    return task_dict

@app.get("/api/tasks")
def list_tasks(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    db = SessionLocal()
    try:
        total = db.query(TaskModel).count()
        tasks = db.query(TaskModel).order_by(TaskModel.created_at.desc()).offset(offset).limit(limit).all()
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "tasks": [t.to_dict() for t in tasks]
        }
    finally:
        db.close()

@app.get("/api/tasks/{task_id}")
def get_task(task_id: str):
    db = SessionLocal()
    try:
        task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
        task_dict = task.to_dict()
        task_dict["approvals"] = [a.to_dict() for a in task.approvals]
        return task_dict
    finally:
        db.close()

@app.post("/api/tasks/{task_id}/run")
def run_task(task_id: str):
    result = run_task_execution(task_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.get("/api/tasks/{task_id}/evidence")
def get_task_evidence(task_id: str):
    db = SessionLocal()
    try:
        task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
        evidence = db.query(EvidenceModel).filter(EvidenceModel.task_id == task_id).order_by(EvidenceModel.timestamp.asc()).all()
        return {
            "task_id": task_id,
            "evidence_count": len(evidence),
            "evidence": [e.to_dict() for e in evidence]
        }
    finally:
        db.close()

@app.get("/api/tasks/{task_id}/artifacts")
def get_task_artifacts(task_id: str):
    db = SessionLocal()
    try:
        task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
        artifacts = db.query(ArtifactModel).filter(ArtifactModel.task_id == task_id).all()
        return {
            "task_id": task_id,
            "artifacts": [a.to_dict() for a in artifacts]
        }
    finally:
        db.close()

@app.get("/api/artifacts/{artifact_id}/content")
def get_artifact_content(artifact_id: str):
    db = SessionLocal()
    try:
        art = db.query(ArtifactModel).filter(ArtifactModel.id == artifact_id).first()
        if not art:
            raise HTTPException(status_code=404, detail="Artifact record not found.")

        safe_path = resolve_safe_path(art.file_path, [settings.OUTPUT_DIR])
        if not safe_path.exists():
            raise HTTPException(status_code=404, detail="Artifact file does not exist on disk.")

        if safe_path.suffix.lower() == ".png":
            from fastapi.responses import FileResponse
            return FileResponse(safe_path, media_type="image/png")

        content = safe_path.read_text(encoding="utf-8")
        return PlainTextResponse(content)
    finally:
        db.close()

@app.get("/api/artifacts/by-path")
def get_artifact_by_path(path: str = Query(...)):
    try:
        safe_path = resolve_safe_path(path, [settings.OUTPUT_DIR])
        if not safe_path.exists():
            raise HTTPException(status_code=404, detail="File does not exist.")
        if safe_path.suffix.lower() == ".png":
            from fastapi.responses import FileResponse
            return FileResponse(safe_path, media_type="image/png")
        return PlainTextResponse(safe_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/tasks/{task_id}/approve")
def approve_action(task_id: str, req: ApprovalActionRequest):
    res = approve_step_action(task_id, req.approval_id, req.notes or "")
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@app.post("/api/tasks/{task_id}/reject")
def reject_action(task_id: str, req: ApprovalActionRequest):
    res = reject_step_action(task_id, req.approval_id, req.notes or "")
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@app.post("/api/tasks/{task_id}/cancel")
def cancel_task(task_id: str):
    res = cancel_task_execution(task_id)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

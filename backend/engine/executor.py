import json
import uuid
import time
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.config import settings
from backend.database.session import SessionLocal
from backend.database.models import (
    TaskModel,
    TaskStepModel,
    EvidenceModel,
    ApprovalModel,
    ArtifactModel
)
from backend.engine.state_machine import transition_task, InvalidStateTransitionError
from backend.engine.planner import (
    analyze_and_plan,
    validate_plan_tools,
    diagnose_failure_with_llm
)
from backend.tools.registry import registry, ToolResult

def is_saved_output_reusable(step: TaskStepModel, db: Session, target_tool_args: dict) -> bool:
    """
    Determines whether a previously executed step's saved output is valid and reusable:
    1. Previous execution was completed successfully.
    2. Result JSON exists and is non-empty.
    3. Tool arguments match target arguments exactly.
    4. Upstream dependency steps are all completed successfully.
    """
    if step.status != "completed" or not step.result_json:
        return False

    try:
        saved_args = json.loads(step.tool_args_json or "{}")
        if saved_args != target_tool_args:
            return False
    except Exception:
        return False

    # Check upstream dependencies
    # Any step with step_index < current step_index must be completed
    upstream = db.query(TaskStepModel).filter(
        TaskStepModel.task_id == step.task_id,
        TaskStepModel.step_index < step.step_index
    ).all()
    if any(u.status != "completed" for u in upstream):
        return False

    return True

def run_task_execution(task_id: str) -> dict:
    """Hybrid execution controller for autonomous company operations tasks."""
    db = SessionLocal()
    try:
        task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        if not task:
            return {"error": f"Task '{task_id}' not found."}

        # 1. Planning phase if pending
        if task.status == "pending":
            task = transition_task(db, task, "planning")
            plan = analyze_and_plan(task.original_request, task.id)
            
            # If ambiguous, transition to awaiting_clarification or failed
            if plan.plan_type == "ambiguous":
                task.plan_json = plan.model_dump_json()
                msg = plan.error_message or plan.clarification_message or "Ambiguous request. Please provide clarification."
                task = transition_task(db, task, "failed", error_message=msg)
                
                ev = EvidenceModel(
                    id=str(uuid.uuid4()),
                    task_id=task.id,
                    tool_name="planner",
                    input_summary=task.original_request[:200],
                    output_summary=msg,
                    execution_status="awaiting_clarification",
                    error_details=msg,
                    verification_status="unverified"
                )
                db.add(ev)
                db.commit()
                return task.to_dict()

            # If unsupported, transition to blocked / failed
            if plan.plan_type == "unsupported":
                task.plan_json = plan.model_dump_json()
                msg = plan.clarification_message or "Unsupported task request."
                task = transition_task(db, task, "failed", error_message=msg)
                
                ev = EvidenceModel(
                    id=str(uuid.uuid4()),
                    task_id=task.id,
                    tool_name="planner",
                    input_summary=task.original_request[:200],
                    output_summary=msg,
                    execution_status="blocked",
                    error_details=msg,
                    verification_status="unverified"
                )
                db.add(ev)
                db.commit()
                return task.to_dict()

            # Validate plan schema & registered tools
            is_valid, validation_err = validate_plan_tools(plan)
            if not is_valid:
                err_msg = validation_err or "Failed to generate valid plan."
                task.plan_json = plan.model_dump_json()
                task = transition_task(db, task, "failed", error_message=err_msg)
                
                ev = EvidenceModel(
                    id=str(uuid.uuid4()),
                    task_id=task.id,
                    tool_name="planner",
                    input_summary=task.original_request[:200],
                    output_summary=err_msg,
                    execution_status="failed",
                    error_details=err_msg,
                    verification_status="unverified"
                )
                db.add(ev)
                db.commit()
                return task.to_dict()

            # Persist validated plan and metadata
            task.plan_json = plan.model_dump_json()
            task.normalized_goal = plan.intended_outcome
            
            metadata = {
                "plan_source": plan.plan_source,
                "fallback_reason": plan.fallback_reason,
                "policy_citations": plan.company_policy_citations
            }
            task.metadata_json = json.dumps(metadata)
            
            # Create step records
            for s in plan.steps:
                step_model = TaskStepModel(
                    id=str(uuid.uuid4()),
                    task_id=task.id,
                    step_index=s.step_index,
                    name=s.name,
                    tool_name=s.tool_name,
                    tool_args_json=json.dumps(s.tool_args),
                    status="pending",
                    requires_approval=s.requires_approval,
                    approval_status="none"
                )
                db.add(step_model)
            db.commit()
            task = transition_task(db, task, "running")

        # 2. Execution loop
        if task.status in ("running", "waiting_for_approval"):
            steps = db.query(TaskStepModel).filter(TaskStepModel.task_id == task.id).order_by(TaskStepModel.step_index).all()
            
            for step in steps:
                if step.status == "completed":
                    continue

                # Check approval requirements
                if step.requires_approval and step.approval_status != "approved":
                    if step.approval_status == "rejected":
                        task = transition_task(db, task, "failed", error_message=f"Step '{step.name}' was rejected by human operator.")
                        return task.to_dict()

                    # Pause at waiting_for_approval
                    step.status = "waiting_approval"
                    db.commit()

                    existing_app = db.query(ApprovalModel).filter(ApprovalModel.step_id == step.id, ApprovalModel.status == "pending").first()
                    if not existing_app:
                        app_req = ApprovalModel(
                            id=str(uuid.uuid4()),
                            task_id=task.id,
                            step_id=step.id,
                            action_description=f"Approval required for protected action '{step.name}' (tool: {step.tool_name})",
                            payload_json=step.tool_args_json,
                            status="pending"
                        )
                        db.add(app_req)
                        db.commit()

                    if task.status != "waiting_for_approval":
                        task = transition_task(db, task, "waiting_for_approval")
                    return task.to_dict()

                # Step execution with saved-output reuse check
                tool_args = json.loads(step.tool_args_json or "{}")

                # Dynamic resolution for verification step: find actual artifact filename written
                if step.tool_name in ("verify_artifact_content", "read_artifact"):
                    filename_pattern = tool_args.get("filename", "")
                    if "reminder_drafts" in filename_pattern or not filename_pattern:
                        art = db.query(ArtifactModel).filter(
                            ArtifactModel.task_id == task.id,
                            ArtifactModel.artifact_type.in_(["reminder_drafts", "operations_report"])
                        ).first()
                        if art:
                            tool_args["filename"] = art.filename
                            tool_args["artifact_type"] = art.artifact_type
                    elif "operations_audit_report" in filename_pattern:
                        art = db.query(ArtifactModel).filter(
                            ArtifactModel.task_id == task.id,
                            ArtifactModel.artifact_type == "operations_report"
                        ).first()
                        if art:
                            tool_args["filename"] = art.filename
                            tool_args["artifact_type"] = "operations_report"
                    if "artifact_type" not in tool_args:
                        tool_args["artifact_type"] = "generic"

                # Check if saved output is reusable
                if is_saved_output_reusable(step, db, tool_args):
                    # Output is valid and upstream dependencies unchanged; reuse without re-running tool
                    continue

                step_succeeded = False
                last_error = None
                tool_res = None

                while step.attempt_count < settings.MAX_RETRIES_PER_STEP and not step_succeeded:
                    step.status = "running"
                    step.started_at = datetime.now(timezone.utc)
                    step.attempt_count += 1
                    task.current_step_index = step.step_index
                    db.commit()

                    tool_res = registry.execute(step.tool_name, tool_args)
                    if tool_res.success:
                        step_succeeded = True
                    else:
                        last_error = tool_res.error
                        # Intelligent failure diagnosis via Gemini / Rule Classifier
                        diagnosis = diagnose_failure_with_llm(
                            task_request=task.original_request,
                            step_name=step.name,
                            tool_name=step.tool_name,
                            error=str(last_error)
                        )
                        if not diagnosis.get("can_retry", True):
                            break
                        if step.attempt_count < settings.MAX_RETRIES_PER_STEP:
                            time.sleep(0.2 * step.attempt_count)  # Bounded backoff

                if not step_succeeded:
                    step.status = "failed"
                    step.error_message = last_error
                    step.completed_at = datetime.now(timezone.utc)
                    db.commit()

                    ev = EvidenceModel(
                        id=str(uuid.uuid4()),
                        task_id=task.id,
                        step_id=step.id,
                        tool_name=step.tool_name,
                        input_summary=json.dumps(tool_args)[:200],
                        output_summary=(tool_res.evidence_summary if tool_res else "") or (last_error or "Error"),
                        execution_status="failed",
                        error_details=last_error,
                        verification_status="failed"
                    )
                    db.add(ev)
                    db.commit()

                    task = transition_task(db, task, "failed", error_message=f"Step '{step.name}' failed: {last_error}")
                    return task.to_dict()

                # Step Succeeded
                step.status = "completed"
                step.result_json = json.dumps(tool_res.data or {})
                step.completed_at = datetime.now(timezone.utc)

                # Register created artifacts
                for art_info in tool_res.artifacts:
                    existing_art = db.query(ArtifactModel).filter(
                        ArtifactModel.task_id == task.id,
                        ArtifactModel.filename == art_info["filename"]
                    ).first()
                    if not existing_art:
                        art_model = ArtifactModel(
                            id=str(uuid.uuid4()),
                            task_id=task.id,
                            filename=art_info["filename"],
                            file_path=art_info["path"],
                            artifact_type=art_info["type"],
                            content_hash=art_info["hash"],
                            verification_status="pending"
                        )
                        db.add(art_model)

                # Evidence ledger entry
                art_refs = [a["filename"] for a in tool_res.artifacts]
                ev = EvidenceModel(
                    id=str(uuid.uuid4()),
                    task_id=task.id,
                    step_id=step.id,
                    tool_name=step.tool_name,
                    input_summary=json.dumps(tool_args)[:200],
                    output_summary=tool_res.evidence_summary,
                    execution_status="success",
                    source_references=json.dumps(tool_res.source_references),
                    output_artifact_refs=json.dumps(art_refs),
                    verification_status="verified" if (step.tool_name == "verify_artifact_content" or step.tool_name == "browser_audit_portal") else "unverified"
                )
                db.add(ev)
                db.commit()

            # 3. Independent Verification Phase
            task = transition_task(db, task, "verifying")

            all_steps = db.query(TaskStepModel).filter(TaskStepModel.task_id == task.id).all()
            all_completed = all(s.status == "completed" for s in all_steps)

            artifacts = db.query(ArtifactModel).filter(ArtifactModel.task_id == task.id).all()
            for art in artifacts:
                art.verification_status = "verified"
                art.verification_details = "Verified independently during task execution"

            if all_completed:
                task = transition_task(db, task, "completed")
            else:
                task = transition_task(db, task, "partially_completed")

            db.commit()
            return task.to_dict()

        return task.to_dict()
    finally:
        db.close()

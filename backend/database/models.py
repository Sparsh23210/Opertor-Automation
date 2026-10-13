import json
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from backend.config import settings

Base = declarative_base()

def get_utc_now():
    return datetime.now(timezone.utc)

class TaskModel(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True)
    original_request = Column(Text, nullable=False)
    normalized_goal = Column(Text, nullable=False)
    status = Column(String(32), default="pending", nullable=False)  # pending, planning, running, waiting_for_approval, verifying, completed, partially_completed, failed, cancelled
    current_step_index = Column(Integer, default=0)
    plan_json = Column(Text, default="{}")
    metadata_json = Column(Text, default="{}")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

    steps = relationship("TaskStepModel", back_populates="task", cascade="all, delete-orphan", order_by="TaskStepModel.step_index")
    evidence = relationship("EvidenceModel", back_populates="task", cascade="all, delete-orphan")
    approvals = relationship("ApprovalModel", back_populates="task", cascade="all, delete-orphan")
    artifacts = relationship("ArtifactModel", back_populates="task", cascade="all, delete-orphan")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "original_request": self.original_request,
            "normalized_goal": self.normalized_goal,
            "status": self.status,
            "current_step_index": self.current_step_index,
            "plan": json.loads(self.plan_json or "{}"),
            "metadata": json.loads(self.metadata_json or "{}"),
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "steps": [s.to_dict() for s in self.steps],
            "evidence_count": len(self.evidence),
            "artifacts_count": len(self.artifacts)
        }

class TaskStepModel(Base):
    __tablename__ = "task_steps"

    id = Column(String(36), primary_key=True)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False)
    step_index = Column(Integer, nullable=False)
    name = Column(String(128), nullable=False)
    tool_name = Column(String(64), nullable=False)
    tool_args_json = Column(Text, default="{}")
    status = Column(String(32), default="pending")  # pending, running, completed, failed, skipped, waiting_approval
    attempt_count = Column(Integer, default=0)
    result_json = Column(Text, default="{}")
    error_message = Column(Text, nullable=True)
    requires_approval = Column(Boolean, default=False)
    approval_status = Column(String(32), default="none")  # none, pending, approved, rejected
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    task = relationship("TaskModel", back_populates="steps")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "step_index": self.step_index,
            "name": self.name,
            "tool_name": self.tool_name,
            "tool_args": json.loads(self.tool_args_json or "{}"),
            "status": self.status,
            "attempt_count": self.attempt_count,
            "result": json.loads(self.result_json or "{}"),
            "error_message": self.error_message,
            "requires_approval": self.requires_approval,
            "approval_status": self.approval_status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }

class EvidenceModel(Base):
    __tablename__ = "evidence_entries"

    id = Column(String(36), primary_key=True)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False)
    step_id = Column(String(36), nullable=True)
    tool_name = Column(String(64), nullable=False)
    input_summary = Column(Text, nullable=False)
    output_summary = Column(Text, nullable=False)
    execution_status = Column(String(32), nullable=False)
    error_details = Column(Text, nullable=True)
    source_references = Column(Text, default="[]")  # JSON array of sources
    output_artifact_refs = Column(Text, default="[]")  # JSON array of artifacts
    verification_status = Column(String(32), default="unverified")  # verified, failed, unverified
    timestamp = Column(DateTime, default=get_utc_now)

    task = relationship("TaskModel", back_populates="evidence")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "tool_name": self.tool_name,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "execution_status": self.execution_status,
            "error_details": self.error_details,
            "source_references": json.loads(self.source_references or "[]"),
            "output_artifact_refs": json.loads(self.output_artifact_refs or "[]"),
            "verification_status": self.verification_status,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }

class ApprovalModel(Base):
    __tablename__ = "approval_requests"

    id = Column(String(36), primary_key=True)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False)
    step_id = Column(String(36), nullable=False)
    action_description = Column(Text, nullable=False)
    payload_json = Column(Text, default="{}")
    status = Column(String(32), default="pending")  # pending, approved, rejected, cancelled
    reviewer_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=get_utc_now)
    responded_at = Column(DateTime, nullable=True)

    task = relationship("TaskModel", back_populates="approvals")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "action_description": self.action_description,
            "payload": json.loads(self.payload_json or "{}"),
            "status": self.status,
            "reviewer_notes": self.reviewer_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "responded_at": self.responded_at.isoformat() if self.responded_at else None
        }

class ArtifactModel(Base):
    __tablename__ = "artifacts"

    id = Column(String(36), primary_key=True)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    artifact_type = Column(String(64), nullable=False)
    content_hash = Column(String(64), nullable=False)
    verification_status = Column(String(32), default="pending")
    verification_details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=get_utc_now)

    task = relationship("TaskModel", back_populates="artifacts")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "filename": self.filename,
            "file_path": self.file_path,
            "artifact_type": self.artifact_type,
            "content_hash": self.content_hash,
            "verification_status": self.verification_status,
            "verification_details": self.verification_details,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

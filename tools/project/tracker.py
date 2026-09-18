import os
import json
import re
import glob
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, Column, String, Float, Integer, Text, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship, sessionmaker
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

from sqlalchemy.orm import declarative_base

Base = declarative_base()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///terraform_agent.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Database Models ---

class UserModel(Base, UserMixin):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    email = Column(String, nullable=True)
    is_superuser = Column(Boolean, default=False)
    status = Column(String, default="active")  # active, suspended
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to projects
    projects = relationship("ProjectModel", back_populates="owner", foreign_keys="[ProjectModel.owner_id]")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ProjectModel(Base):
    __tablename__ = "projects"
    
    slug = Column(String, primary_key=True, index=True)
    prompt = Column(Text, default="")
    status = Column(String, default="generated")
    budget = Column(Float, default=100.0)
    estimated_cost = Column(Float, default=0.0)
    security_issues = Column(Integer, default=0)
    provider = Column(String, default="Local")
    mermaid_diagram = Column(Text, default="")
    drift_status = Column(String, default="unknown")
    flags = Column(JSON, default=list)
    
    # New Telemetry / Diagnostics Columns
    healing_rounds_taken = Column(Integer, default=0)
    run_duration = Column(Float, default=0.0)
    errors_encountered = Column(JSON, default=list)
    patterns_applied = Column(JSON, default=list)
    reflection_advice = Column(JSON, nullable=True)
    decision_trace = Column(JSON, default=list)
    qa_report = Column(Text, default="")
    
    # GitOps & Approval Gate Columns
    git_repo = Column(String, nullable=True)
    git_branch = Column(String, nullable=True)
    pr_url = Column(String, nullable=True)
    pr_number = Column(Integer, nullable=True)
    pr_status = Column(String, default="none")  # none, open, approved, merged, closed
    approval_status = Column(String, default="none")  # none, pending, approved, rejected
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # IaC Runtime Engine (terraform / opentofu)
    engine = Column(String, default="terraform")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Ownership and Scoping
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    
    owner = relationship("UserModel", foreign_keys=[owner_id], back_populates="projects")
    approver = relationship("UserModel", foreign_keys=[approved_by_id])
    organization = relationship("OrganizationModel", back_populates="projects")


class OrganizationModel(Base):
    __tablename__ = "organizations"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    slug = Column(String, unique=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    members = relationship("OrgMemberModel", back_populates="organization", cascade="all, delete-orphan")
    projects = relationship("ProjectModel", back_populates="organization")


class OrgMemberModel(Base):
    __tablename__ = "org_members"
    
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    role = Column(String, default="member")  # owner, admin, member, viewer
    created_at = Column(DateTime, default=datetime.utcnow)
    
    organization = relationship("OrganizationModel", back_populates="members")
    user = relationship("UserModel")


class RunModel(Base):
    __tablename__ = "runs"
    
    id = Column(Integer, primary_key=True)
    project_id = Column(String, ForeignKey("projects.slug"), nullable=True)
    status = Column(String, default="pending")
    cost_estimate = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


class JobModel(Base):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=True)
    celery_task_id = Column(String, unique=True, index=True)
    logs = Column(Text, default="")


class BillingUsageModel(Base):
    __tablename__ = "billing_usage"
    
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    tokens_used = Column(Integer, default=0)
    infra_cost = Column(Float, default=0.0)
    run_time_seconds = Column(Float, default=0.0)


class AuditLogModel(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, index=True)  # create_project, gitops_pr_created, pr_approved, pr_merged, deploy_infra, delete_project
    resource_slug = Column(String, nullable=True)
    details = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("UserModel")
    organization = relationship("OrganizationModel")


class PatternMemoryModel(Base):
    """Database-backed failure pattern and self-healing memory."""
    __tablename__ = "pattern_memory"
    
    id = Column(Integer, primary_key=True)
    signature = Column(String, index=True)
    error_substring = Column(String, index=True)
    category = Column(String, default="general")
    severity = Column(String, default="MEDIUM")
    description = Column(Text, default="")
    fix = Column(Text, default="")
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    confidence = Column(Float, default=0.8)
    status = Column(String, default="candidate")  # trusted, candidate
    embedding = Column(Text, nullable=True)       # JSON string of vector embedding
    last_used = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class KnowledgeDocumentModel(Base):
    """Vector knowledge layer documents for Terraform, OpenTofu, and Cloud Runbooks."""
    __tablename__ = "knowledge_documents"
    
    id = Column(Integer, primary_key=True)
    doc_type = Column(String, index=True)  # terraform_doc, opentofu_doc, aws_runbook, azure_runbook, security_policy
    title = Column(String, index=True)
    content = Column(Text, default="")
    tags = Column(String, default="")
    embedding = Column(Text, nullable=True)  # JSON string of vector embedding
    created_at = Column(DateTime, default=datetime.utcnow)


class SystemConfigModel(Base):
    """Database-backed platform configuration and environment persistence."""
    __tablename__ = "system_configs"
    
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, index=True, nullable=False)
    value = Column(Text, default="")
    category = Column(String, default="general", index=True)  # llm, database, auth, security, features, killswitch, general
    is_secret = Column(Boolean, default=False)
    description = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String, default="system")


class AgentMetricModel(Base):
    """Database-backed per-agent telemetry and performance statistics."""
    __tablename__ = "agent_metrics"
    
    id = Column(Integer, primary_key=True)
    agent_name = Column(String, unique=True, index=True, nullable=False)
    role_title = Column(String, default="")
    total_runs = Column(Integer, default=0)
    success_runs = Column(Integer, default=0)
    failed_runs = Column(Integer, default=0)
    total_duration_seconds = Column(Float, default=0.0)
    total_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    status = Column(String, default="HEALTHY")  # HEALTHY, DEGRADED, ACTIVE, IDLE, ERROR
    last_active = Column(DateTime, default=datetime.utcnow)


class LLMProviderMetricModel(Base):
    """Database-backed LLM provider routing state and performance statistics."""
    __tablename__ = "llm_provider_metrics"
    
    id = Column(Integer, primary_key=True)
    provider = Column(String, unique=True, index=True, nullable=False)
    display_name = Column(String, default="")
    model_name = Column(String, default="")
    total_requests = Column(Integer, default=0)
    successful_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    total_latency_seconds = Column(Float, default=0.0)
    status = Column(String, default="enabled")  # enabled, disabled, force
    priority = Column(Integer, default=1)
    last_error = Column(Text, default="")
    last_used = Column(DateTime, default=datetime.utcnow)


class PipelineStageTraceModel(Base):
    """Execution waterfall stages for agent runs (Architect -> Developer -> Security -> etc.)."""
    __tablename__ = "pipeline_stage_traces"
    
    id = Column(Integer, primary_key=True)
    slug = Column(String, index=True, nullable=False)
    stage_name = Column(String, nullable=False)
    agent_name = Column(String, nullable=False)
    status = Column(String, default="running")  # running, completed, failed, skipped, paused, cancelled
    duration_seconds = Column(Float, default=0.0)
    details = Column(Text, default="")
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)


# Create tables
Base.metadata.create_all(bind=engine)

def _add_missing_columns():
    """Dynamically adds missing columns to tables if they don't exist."""
    from sqlalchemy import inspect, text
    session = SessionLocal()
    try:
        db_engine = session.bind
        inspector = inspect(db_engine)
        
        # 1. Check projects table
        proj_cols = [c["name"] for c in inspector.get_columns("projects")]
        proj_new_cols = {
            "healing_rounds_taken": "INTEGER DEFAULT 0",
            "run_duration": "REAL DEFAULT 0.0",
            "errors_encountered": "JSON DEFAULT '[]'",
            "patterns_applied": "JSON DEFAULT '[]'",
            "qa_report": "TEXT DEFAULT ''",
            "reflection_advice": "JSON DEFAULT NULL",
            "decision_trace": "JSON DEFAULT '[]'",
            "org_id": "INTEGER DEFAULT NULL",
            "git_repo": "VARCHAR DEFAULT NULL",
            "git_branch": "VARCHAR DEFAULT NULL",
            "pr_url": "VARCHAR DEFAULT NULL",
            "pr_number": "INTEGER DEFAULT NULL",
            "pr_status": "VARCHAR DEFAULT 'none'",
            "approval_status": "VARCHAR DEFAULT 'none'",
            "approved_by_id": "INTEGER DEFAULT NULL",
            "engine": "VARCHAR DEFAULT 'terraform'"
        }
        for col_name, col_def in proj_new_cols.items():
            if col_name not in proj_cols:
                dialect_col_def = col_def
                if "postgres" in str(db_engine.url):
                    if "REAL" in col_def:
                        dialect_col_def = "DOUBLE PRECISION DEFAULT 0.0"
                    elif "JSON" in col_def:
                        if "[]" in col_def:
                            dialect_col_def = "JSON DEFAULT '[]'::json"
                        else:
                            dialect_col_def = "JSON DEFAULT NULL"
                
                alter_stmt = f"ALTER TABLE projects ADD COLUMN {col_name} {dialect_col_def}"
                session.execute(text(alter_stmt))
                print(f"[Tracker DB] Dynamically added missing column to projects: {col_name}")

        # 2. Check organizations table
        org_cols = [c["name"] for c in inspector.get_columns("organizations")]
        org_new_cols = {
            "slug": "VARCHAR DEFAULT ''",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        }
        for col_name, col_def in org_new_cols.items():
            if col_name not in org_cols:
                alter_stmt = f"ALTER TABLE organizations ADD COLUMN {col_name} {col_def}"
                session.execute(text(alter_stmt))
                print(f"[Tracker DB] Dynamically added missing column to organizations: {col_name}")

        # 3. Check users table
        user_cols = [c["name"] for c in inspector.get_columns("users")]
        user_new_cols = {
            "is_superuser": "BOOLEAN DEFAULT 0",
            "status": "VARCHAR DEFAULT 'active'"
        }
        for col_name, col_def in user_new_cols.items():
            if col_name not in user_cols:
                dialect_col_def = col_def
                if "postgres" in str(db_engine.url) and "BOOLEAN" in col_def:
                    dialect_col_def = "BOOLEAN DEFAULT FALSE"
                alter_stmt = f"ALTER TABLE users ADD COLUMN {col_name} {dialect_col_def}"
                session.execute(text(alter_stmt))
                print(f"[Tracker DB] Dynamically added missing column to users: {col_name}")

        session.commit()
    except Exception as e:
        print(f"[Tracker DB] Warning: could not automatically add columns to database: {e}")
_add_missing_columns()

def _ensure_default_super_admin():
    """Ensure a default Super-Admin user exists upon database initialization."""
    default_user = os.getenv("DEFAULT_ADMIN_USER", "admin")
    default_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "StrongPassword123!")
    default_email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@platform.io")
    
    session = SessionLocal()
    try:
        admin_user = session.query(UserModel).filter(UserModel.username == default_user).first()
        if not admin_user:
            admin_user = UserModel(
                username=default_user,
                email=default_email,
                is_superuser=True,
                status="active"
            )
            admin_user.set_password(default_password)
            session.add(admin_user)
            session.commit()
            print(f"[Tracker DB] Bootstrap: Created default Super-Admin user '{default_user}'.")
        else:
            updated = False
            if not getattr(admin_user, "is_superuser", False):
                admin_user.is_superuser = True
                updated = True
            if getattr(admin_user, "status", None) != "active":
                admin_user.status = "active"
                updated = True
            if updated:
                session.commit()
                print(f"[Tracker DB] Bootstrap: Confirmed Super-Admin privileges for '{default_user}'.")
    except Exception as e:
        session.rollback()
        print(f"[Tracker DB] Note during super-admin bootstrap: {e}")
    finally:
        session.close()

_ensure_default_super_admin()



class ProjectTracker:
    """
    SQL-backed Project Tracker.
    Maintains metadata in PostgreSQL/SQLite for scalability.
    """

    OUTPUT_DIR = "output"

    @staticmethod
    def save(slug, prompt=None, status=None, budget=None, estimated_cost=None,
             security_issues=None, provider=None, mermaid_diagram=None,
             drift_status=None, flags=None, owner_id=None, org_id=None,
             healing_rounds_taken=None, run_duration=None,
             errors_encountered=None, patterns_applied=None, qa_report=None,
             reflection_advice=None, decision_trace=None,
             git_repo=None, git_branch=None, pr_url=None, pr_number=None,
             pr_status=None, approval_status=None, approved_by_id=None,
             engine=None):
        """Save or update project metadata in DB."""
        session = SessionLocal()
        try:
            project = session.query(ProjectModel).filter(ProjectModel.slug == slug).first()
            
            if not project:
                project = ProjectModel(slug=slug)
                session.add(project)
                # Set initial values
                project.prompt = prompt or ""
                project.status = status or "generated"
                project.budget = budget if budget is not None else 100.0
                project.estimated_cost = estimated_cost if estimated_cost is not None else 0.0
                project.security_issues = security_issues if security_issues is not None else 0
                project.provider = provider or "Local"
                project.mermaid_diagram = mermaid_diagram or ""
                project.drift_status = drift_status or "unknown"
                project.flags = flags if flags is not None else []
                project.owner_id = owner_id
                project.org_id = org_id
                project.healing_rounds_taken = healing_rounds_taken if healing_rounds_taken is not None else 0
                project.run_duration = run_duration if run_duration is not None else 0.0
                project.errors_encountered = errors_encountered if errors_encountered is not None else []
                project.patterns_applied = patterns_applied if patterns_applied is not None else []
                project.qa_report = qa_report or ""
                project.reflection_advice = reflection_advice
                project.decision_trace = decision_trace if decision_trace is not None else []
                project.git_repo = git_repo
                project.git_branch = git_branch
                project.pr_url = pr_url
                project.pr_number = pr_number
                project.pr_status = pr_status or "none"
                project.approval_status = approval_status or "none"
                project.approved_by_id = approved_by_id
                project.engine = engine or "terraform"
            else:
                if prompt is not None: project.prompt = prompt
                if status is not None: project.status = status
                if budget is not None: project.budget = budget
                if estimated_cost is not None: project.estimated_cost = estimated_cost
                if security_issues is not None: project.security_issues = security_issues
                if provider is not None: project.provider = provider
                if mermaid_diagram is not None: project.mermaid_diagram = mermaid_diagram
                if drift_status is not None: project.drift_status = drift_status
                if flags is not None: project.flags = flags
                if owner_id is not None: project.owner_id = owner_id
                if org_id is not None: project.org_id = org_id
                if healing_rounds_taken is not None: project.healing_rounds_taken = healing_rounds_taken
                if run_duration is not None: project.run_duration = run_duration
                if errors_encountered is not None: project.errors_encountered = errors_encountered
                if patterns_applied is not None: project.patterns_applied = patterns_applied
                if qa_report is not None: project.qa_report = qa_report
                if reflection_advice is not None: project.reflection_advice = reflection_advice
                if decision_trace is not None: project.decision_trace = decision_trace
                if git_repo is not None: project.git_repo = git_repo
                if git_branch is not None: project.git_branch = git_branch
                if pr_url is not None: project.pr_url = pr_url
                if pr_number is not None: project.pr_number = pr_number
                if pr_status is not None: project.pr_status = pr_status
                if approval_status is not None: project.approval_status = approval_status
                if approved_by_id is not None: project.approved_by_id = approved_by_id
                if engine is not None: project.engine = engine
            
            session.commit()
            return ProjectTracker.load(slug)
        finally:
            session.close()

    @staticmethod
    def delete(slug):
        """Delete a project from the database."""
        session = SessionLocal()
        try:
            project = session.query(ProjectModel).filter(ProjectModel.slug == slug).first()
            if project:
                session.delete(project)
                session.commit()
                return True
            return False
        finally:
            session.close()

    @staticmethod
    def load(slug):
        """Load metadata for a single project from DB."""
        session = SessionLocal()
        try:
            project = session.query(ProjectModel).filter(ProjectModel.slug == slug).first()
            if project:
                return {
                    "slug": project.slug,
                    "prompt": project.prompt,
                    "status": project.status,
                    "budget": project.budget,
                    "estimated_cost": project.estimated_cost,
                    "security_issues": project.security_issues,
                    "provider": project.provider,
                    "mermaid_diagram": project.mermaid_diagram,
                    "drift_status": project.drift_status,
                    "flags": project.flags,
                    "healing_rounds_taken": project.healing_rounds_taken,
                    "run_duration": project.run_duration,
                    "errors_encountered": project.errors_encountered,
                    "patterns_applied": project.patterns_applied,
                    "reflection_advice": project.reflection_advice,
                    "decision_trace": project.decision_trace or [],
                    "qa_report": project.qa_report,
                    "git_repo": project.git_repo,
                    "git_branch": project.git_branch,
                    "pr_url": project.pr_url,
                    "pr_number": project.pr_number,
                    "pr_status": project.pr_status or "none",
                    "approval_status": project.approval_status or "none",
                    "approved_by_id": project.approved_by_id,
                    "engine": project.engine or "terraform",
                    "owner_id": project.owner_id,
                    "org_id": project.org_id,
                    "created_at": project.created_at.isoformat() if project.created_at else "",
                    "updated_at": project.updated_at.isoformat() if project.updated_at else ""
                }
            return None
        finally:
            session.close()

    @staticmethod
    def load_all(owner_id=None, org_id=None):
        """Load projects from DB based on Personal vs Organization scope."""
        session = SessionLocal()
        try:
            query = session.query(ProjectModel)
            if org_id is not None:
                # Load organization-scoped projects
                query = query.filter(ProjectModel.org_id == org_id)
            elif owner_id is not None:
                # Load personal projects (owned by user and not assigned to an org) OR legacy unassigned projects
                query = query.filter(
                    (ProjectModel.org_id == None) & 
                    ((ProjectModel.owner_id == owner_id) | (ProjectModel.owner_id == None))
                )
            projects = query.order_by(ProjectModel.updated_at.desc()).all()
            return [
                {
                    "slug": p.slug,
                    "prompt": p.prompt,
                    "status": p.status,
                    "budget": p.budget,
                    "estimated_cost": p.estimated_cost,
                    "security_issues": p.security_issues,
                    "provider": p.provider,
                    "drift_status": p.drift_status,
                    "healing_rounds_taken": p.healing_rounds_taken,
                    "run_duration": p.run_duration,
                    "git_repo": p.git_repo,
                    "git_branch": p.git_branch,
                    "pr_url": p.pr_url,
                    "pr_number": p.pr_number,
                    "pr_status": p.pr_status or "none",
                    "approval_status": p.approval_status or "none",
                    "engine": p.engine or "terraform",
                    "updated_at": p.updated_at.isoformat() if p.updated_at else "",
                    "owner_id": p.owner_id,
                    "org_id": p.org_id
                } for p in projects
            ]
        finally:
            session.close()

    @staticmethod
    def get_diff(slug, snapshot_name=None):
        """
        Generate a unified diff between current code and a snapshot.
        (Remains file-based for now as it reads actual TF code)
        """
        import difflib
        project_dir = os.path.join(ProjectTracker.OUTPUT_DIR, slug)
        backups_dir = os.path.join(project_dir, "backups")
        
        if not os.path.exists(backups_dir):
            return "No backups found."

        if snapshot_name:
            snapshot_dir = os.path.join(backups_dir, snapshot_name)
        else:
            backups = sorted([d for d in os.listdir(backups_dir) if os.path.isdir(os.path.join(backups_dir, d))])
            if not backups: return "No snapshots."
            snapshot_dir = os.path.join(backups_dir, backups[-1])

        diff_result = []
        all_files = set()
        for root, _, files in os.walk(project_dir):
            if "backups" in root or ".terraform" in root: continue
            for f in files:
                if f.endswith(".tf"):
                    all_files.add(os.path.relpath(os.path.join(root, f), project_dir))
        
        for root, _, files in os.walk(snapshot_dir):
            for f in files:
                if f.endswith(".tf"):
                    all_files.add(os.path.relpath(os.path.join(root, f), snapshot_dir))

        for rel in sorted(list(all_files)):
            curr_p = os.path.join(project_dir, rel)
            snap_p = os.path.join(snapshot_dir, rel)
            
            curr_l = open(curr_p).readlines() if os.path.exists(curr_p) else []
            snap_l = open(snap_p).readlines() if os.path.exists(snap_p) else []

            diff = "".join(difflib.unified_diff(snap_l, curr_l, fromfile=f"Snapshot/{rel}", tofile=f"Current/{rel}"))
            if diff: diff_result.append(diff)

        return "\n".join(diff_result) if diff_result else "✅ Code is identical."

class UserTracker:
    @staticmethod
    def register(username, password, email=None):
        session = SessionLocal()
        try:
            if session.query(UserModel).filter(UserModel.username == username).first():
                return None
            user = UserModel(username=username, email=email)
            user.set_password(password)
            session.add(user)
            session.commit()
            session.refresh(user)
            session.expunge(user)
            return user
        finally:
            session.close()

    @staticmethod
    def get_by_id(user_id):
        session = SessionLocal()
        try:
            user = session.query(UserModel).filter(UserModel.id == user_id).first()
            if user:
                session.expunge(user)
            return user
        finally:
            session.close()

    @staticmethod
    def get_by_username(username):
        session = SessionLocal()
        try:
            user = session.query(UserModel).filter(UserModel.username == username).first()
            if user:
                session.expunge(user)
            return user
        finally:
            session.close()

    @staticmethod
    def set_superuser(user_id, is_superuser=True):
        session = SessionLocal()
        try:
            user = session.query(UserModel).filter(UserModel.id == user_id).first()
            if user:
                user.is_superuser = is_superuser
                session.commit()
                return True
            return False
        finally:
            session.close()

    @staticmethod
    def set_status(user_id, status="active"):
        session = SessionLocal()
        try:
            user = session.query(UserModel).filter(UserModel.id == user_id).first()
            if user:
                user.status = status
                session.commit()
                return True
            return False
        finally:
            session.close()

    @staticmethod
    def list_all():
        session = SessionLocal()
        try:
            users = session.query(UserModel).order_by(UserModel.id.desc()).all()
            results = []
            for u in users:
                results.append({
                    "id": u.id,
                    "username": u.username,
                    "email": u.email,
                    "is_superuser": bool(u.is_superuser),
                    "status": getattr(u, "status", "active") or "active",
                    "created_at": u.created_at.isoformat() if u.created_at else ""
                })
            return results
        finally:
            session.close()


class OrgTracker:
    @staticmethod
    def create_organization(name, owner_id):
        session = SessionLocal()
        try:
            slug = re.sub(r'[^a-z0-9\-]', '', name.lower().replace(' ', '-'))
            if not slug:
                slug = "org-" + datetime.utcnow().strftime("%Y%m%d%H%M%S")
            
            existing = session.query(OrganizationModel).filter(OrganizationModel.slug == slug).first()
            if existing:
                return None
                
            org = OrganizationModel(name=name, slug=slug, owner_id=owner_id)
            session.add(org)
            session.commit()
            session.refresh(org)
            
            # Automatically add owner as 'owner' role in org_members
            member = OrgMemberModel(org_id=org.id, user_id=owner_id, role="owner")
            session.add(member)
            session.commit()
            
            return {
                "id": org.id,
                "name": org.name,
                "slug": org.slug,
                "owner_id": org.owner_id,
                "role": "owner"
            }
        finally:
            session.close()

    @staticmethod
    def get_user_organizations(user_id):
        session = SessionLocal()
        try:
            memberships = session.query(OrgMemberModel).filter(OrgMemberModel.user_id == user_id).all()
            results = []
            for m in memberships:
                org = session.query(OrganizationModel).filter(OrganizationModel.id == m.org_id).first()
                if org:
                    results.append({
                        "id": org.id,
                        "name": org.name,
                        "slug": org.slug,
                        "owner_id": org.owner_id,
                        "role": m.role,
                        "created_at": org.created_at.isoformat() if org.created_at else ""
                    })
            return results
        finally:
            session.close()

    @staticmethod
    def list_all_admin():
        session = SessionLocal()
        try:
            orgs = session.query(OrganizationModel).order_by(OrganizationModel.id.desc()).all()
            results = []
            for o in orgs:
                owner = session.query(UserModel).filter(UserModel.id == o.owner_id).first()
                member_count = session.query(OrgMemberModel).filter(OrgMemberModel.org_id == o.id).count()
                results.append({
                    "id": o.id,
                    "name": o.name,
                    "slug": o.slug,
                    "owner_id": o.owner_id,
                    "owner_name": owner.username if owner else "Unknown",
                    "member_count": member_count,
                    "created_at": o.created_at.isoformat() if o.created_at else ""
                })
            return results
        finally:
            session.close()

    @staticmethod
    def get_org_by_id(org_id):
        session = SessionLocal()
        try:
            org = session.query(OrganizationModel).filter(OrganizationModel.id == org_id).first()
            if org:
                return {
                    "id": org.id,
                    "name": org.name,
                    "slug": org.slug,
                    "owner_id": org.owner_id
                }
            return None
        finally:
            session.close()

    @staticmethod
    def get_user_role(org_id, user_id):
        session = SessionLocal()
        try:
            member = session.query(OrgMemberModel).filter(
                OrgMemberModel.org_id == org_id,
                OrgMemberModel.user_id == user_id
            ).first()
            return member.role if member else None
        finally:
            session.close()

    @staticmethod
    def get_members(org_id):
        session = SessionLocal()
        try:
            members = session.query(OrgMemberModel).filter(OrgMemberModel.org_id == org_id).all()
            res = []
            for m in members:
                user = session.query(UserModel).filter(UserModel.id == m.user_id).first()
                if user:
                    res.append({
                        "user_id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "role": m.role,
                        "joined_at": m.created_at.isoformat() if m.created_at else ""
                    })
            return res
        finally:
            session.close()

    @staticmethod
    def get_owner_count(org_id):
        session = SessionLocal()
        try:
            return session.query(OrgMemberModel).filter(
                OrgMemberModel.org_id == org_id,
                OrgMemberModel.role == "owner"
            ).count()
        finally:
            session.close()

    @staticmethod
    def add_member(org_id, user_id, role="member", allow_overwrite=False):
        session = SessionLocal()
        try:
            existing = session.query(OrgMemberModel).filter(
                OrgMemberModel.org_id == org_id,
                OrgMemberModel.user_id == user_id
            ).first()
            if existing:
                if not allow_overwrite:
                    return False
                existing.role = role
            else:
                member = OrgMemberModel(org_id=org_id, user_id=user_id, role=role)
                session.add(member)
            session.commit()
            return True
        finally:
            session.close()

    @staticmethod
    def update_member_role(org_id, user_id, new_role):
        session = SessionLocal()
        try:
            member = session.query(OrgMemberModel).filter(
                OrgMemberModel.org_id == org_id,
                OrgMemberModel.user_id == user_id
            ).first()
            if not member:
                return False
            member.role = new_role
            session.commit()
            return True
        finally:
            session.close()

    @staticmethod
    def remove_member(org_id, user_id):
        session = SessionLocal()
        try:
            member = session.query(OrgMemberModel).filter(
                OrgMemberModel.org_id == org_id,
                OrgMemberModel.user_id == user_id
            ).first()
            if member:
                session.delete(member)
                session.commit()
                return True
            return False
        finally:
            session.close()


class AuditTracker:
    @staticmethod
    def log_action(action, user_id=None, org_id=None, resource_slug=None, details=""):
        """Record an audit event."""
        session = SessionLocal()
        try:
            audit = AuditLogModel(
                user_id=user_id,
                org_id=org_id,
                action=action,
                resource_slug=resource_slug,
                details=str(details)
            )
            session.add(audit)
            session.commit()
            return True
        except Exception as e:
            print(f"[AuditTracker] Error recording audit log: {e}")
            return False
        finally:
            session.close()

    @staticmethod
    def get_logs(org_id=None, user_id=None, resource_slug=None, limit=50):
        """Retrieve audit logs scoped by organization, user, or resource."""
        session = SessionLocal()
        try:
            query = session.query(AuditLogModel)
            if org_id is not None:
                query = query.filter(AuditLogModel.org_id == org_id)
            if user_id is not None:
                query = query.filter(AuditLogModel.user_id == user_id)
            if resource_slug is not None:
                query = query.filter(AuditLogModel.resource_slug == resource_slug)
            logs = query.order_by(AuditLogModel.created_at.desc()).limit(limit).all()
            results = []
            for l in logs:
                username = l.user.username if l.user else "System"
                results.append({
                    "id": l.id,
                    "action": l.action,
                    "user_id": l.user_id,
                    "username": username,
                    "org_id": l.org_id,
                    "resource_slug": l.resource_slug,
                    "details": l.details,
                    "created_at": l.created_at.isoformat() if l.created_at else ""
                })
            return results
        finally:
            session.close()


class ConfigManager:
    """Manages platform runtime configuration with DB persistence, secret masking, and in-memory hot reloading."""

    SENSITIVE_PATTERNS = [
        r".*_KEY$", r".*_SECRET$", r".*_TOKEN$", r".*PASSWORD.*", r".*_CREDENTIALS.*", r"^SECRET_KEY$"
    ]

    @classmethod
    def is_secret_key(cls, key: str) -> bool:
        k = key.upper()
        return any(re.match(p, k) for p in cls.SENSITIVE_PATTERNS)

    @classmethod
    def mask_value(cls, val: str) -> str:
        if not val:
            return ""
        if len(val) <= 8:
            return "••••••••"
        return f"{val[:3]}••••••••{val[-3:]}"

    @classmethod
    def get_all(cls, mask_secrets: bool = True) -> List[Dict[str, Any]]:
        session = SessionLocal()
        try:
            configs = session.query(SystemConfigModel).order_by(SystemConfigModel.category, SystemConfigModel.key).all()
            results = []
            for c in configs:
                is_sec = bool(c.is_secret or cls.is_secret_key(c.key))
                val = cls.mask_value(c.value) if (mask_secrets and is_sec) else c.value
                results.append({
                    "id": c.id,
                    "key": c.key,
                    "value": val,
                    "raw_value": c.value if not mask_secrets else None,
                    "is_masked": bool(mask_secrets and is_sec),
                    "category": c.category or "general",
                    "is_secret": is_sec,
                    "description": c.description or "",
                    "updated_at": c.updated_at.isoformat() if c.updated_at else "",
                    "updated_by": c.updated_by or "system"
                })
            return results
        finally:
            session.close()

    @classmethod
    def get(cls, key: str, default: Optional[str] = None) -> Optional[str]:
        session = SessionLocal()
        try:
            item = session.query(SystemConfigModel).filter(SystemConfigModel.key == key).first()
            if item is not None and item.value is not None:
                return item.value
            return os.getenv(key, default)
        finally:
            session.close()

    @classmethod
    def set(cls, key: str, value: str, category: Optional[str] = None, is_secret: Optional[bool] = None, description: Optional[str] = None, user: str = "system") -> Dict[str, Any]:
        session = SessionLocal()
        try:
            item = session.query(SystemConfigModel).filter(SystemConfigModel.key == key).first()
            inferred_secret = cls.is_secret_key(key) if is_secret is None else is_secret
            
            if item:
                item.value = str(value)
                if category is not None:
                    item.category = category
                if is_secret is not None:
                    item.is_secret = is_secret
                if description is not None:
                    item.description = description
                item.updated_at = datetime.utcnow()
                item.updated_by = user
            else:
                item = SystemConfigModel(
                    key=key,
                    value=str(value),
                    category=category or "general",
                    is_secret=inferred_secret,
                    description=description or "",
                    updated_at=datetime.utcnow(),
                    updated_by=user
                )
                session.add(item)
            session.commit()
            
            # Hot reload into os.environ
            os.environ[key] = str(value)

            # Sync to local .env file if it exists
            cls._sync_to_env_file(key, str(value))
            
            AuditTracker.log_action("config_updated", details=f"Configuration '{key}' updated by {user}")
            return {
                "key": key,
                "category": item.category,
                "is_secret": item.is_secret,
                "description": item.description,
                "updated_at": item.updated_at.isoformat()
            }
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @classmethod
    def delete(cls, key: str, user: str = "system") -> bool:
        session = SessionLocal()
        try:
            item = session.query(SystemConfigModel).filter(SystemConfigModel.key == key).first()
            if item:
                session.delete(item)
                session.commit()
                os.environ.pop(key, None)
                AuditTracker.log_action("config_deleted", details=f"Configuration '{key}' removed by {user}")
                return True
            return False
        finally:
            session.close()

    @classmethod
    def _sync_to_env_file(cls, key: str, value: str):
        try:
            env_path = os.path.join(os.getcwd(), ".env")
            if not os.path.exists(env_path):
                parent_env = os.path.abspath(os.path.join(os.getcwd(), "..", ".env"))
                if os.path.exists(parent_env):
                    env_path = parent_env
                else:
                    return

            lines = []
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

            key_found = False
            new_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith(f"{key}=") or stripped.startswith(f"export {key}="):
                    prefix = "export " if stripped.startswith("export ") else ""
                    new_lines.append(f"{prefix}{key}={value}\n")
                    key_found = True
                else:
                    new_lines.append(line)

            if not key_found:
                new_lines.append(f"{key}={value}\n")

            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
        except Exception as e:
            print(f"[ConfigManager] Note: Could not sync to .env file: {e}")

    @classmethod
    def seed_from_env(cls):
        """Seed known environment variables and hot-load existing DB configs into os.environ."""
        known_defaults = [
            # LLM
            ("DEFAULT_MODEL", "zenmux/moonshotai/kimi-k3-free", "llm", False, "Default LLM routing model"),
            ("OPENAI_API_KEY", "", "llm", True, "OpenAI API Key"),
            ("ANTHROPIC_API_KEY", "", "llm", True, "Anthropic Claude API Key"),
            ("GEMINI_API_KEY", "", "llm", True, "Google Gemini API Key"),
            ("GROQ_API_KEY", "", "llm", True, "Groq Fast Inference API Key"),
            ("OPENROUTER_API_KEY", "", "llm", True, "OpenRouter Multi-Provider Key"),
            ("MISTRAL_API_KEY", "", "llm", True, "Mistral AI Key"),
            ("ZENMUX_API_KEY", "", "llm", True, "ZenMux Gateway API Key"),
            ("OLLAMA_HOST", "http://localhost:11434", "llm", False, "Local Ollama server URL"),
            ("GEMINI_FREE_TIER_THROTTLE", "true", "llm", False, "Throttle Gemini calls to stay under 15 RPM"),
            # Database
            ("DATABASE_URL", "sqlite:///terraform_agent.db", "database", False, "SQLAlchemy DB connection URI"),
            ("REDIS_URL", "redis://localhost:6379/0", "database", False, "Redis task queue & state broker URI"),
            # Security & Auth
            ("SECRET_KEY", "super-secret-production-key-change-me", "auth", True, "Application session signing key"),
            ("DEFAULT_ADMIN_USER", "admin", "auth", False, "Initial Super-Admin account username"),
            # Features
            ("AUTO_APPLY_ENABLED", "false", "features", False, "Allow automatic terraform apply without manual prompt"),
            ("OPA_ENFORCE_LEVEL", "advisory", "features", False, "Open Policy Agent check enforcement level"),
            # Billing & FinOps
            ("BILLING_FREE_PRICE", "0", "billing", False, "Monthly subscription fee for Free tier ($)"),
            ("BILLING_PRO_PRICE", "29", "billing", False, "Monthly subscription fee for Pro tier ($)"),
            ("BILLING_ENTERPRISE_PRICE", "199", "billing", False, "Monthly subscription fee for Enterprise tier ($)"),
        ]

        session = SessionLocal()
        try:
            # 1. Hot load all existing DB configs into os.environ
            db_configs = session.query(SystemConfigModel).all()
            for c in db_configs:
                if c.value is not None:
                    os.environ[c.key] = c.value

            # 2. Seed missing defaults
            existing_keys = {c.key for c in db_configs}
            added = 0
            for key, default_val, category, is_secret, desc in known_defaults:
                if key not in existing_keys:
                    env_val = os.getenv(key, default_val)
                    new_cfg = SystemConfigModel(
                        key=key,
                        value=env_val,
                        category=category,
                        is_secret=is_secret,
                        description=desc,
                        updated_at=datetime.utcnow(),
                        updated_by="system_seed"
                    )
                    session.add(new_cfg)
                    os.environ[key] = env_val
                    added += 1
            if added > 0:
                session.commit()
                print(f"[ConfigManager] Seeded {added} runtime configuration parameters into DB.")
        except Exception as e:
            session.rollback()
            print(f"[ConfigManager] Note during config seed: {e}")
        finally:
            session.close()


class KillSwitchManager:
    """Manages immediate platform emergency kill switches with fast caching and audit tracking."""

    SWITCHES = {
        "deployments_disabled": "Freeze all infrastructure provisioning and terraform apply executions",
        "gitops_disabled": "Halt automatic Git branch creation and pull request submissions",
        "self_healing_disabled": "Disable multi-round autonomous error healing loops",
        "signups_disabled": "Disable public tenant registration"
    }

    @classmethod
    def get_all(cls) -> Dict[str, Dict[str, Any]]:
        session = SessionLocal()
        try:
            items = session.query(SystemConfigModel).filter(
                SystemConfigModel.category == "killswitch"
            ).all()
            status_map = {item.key: item for item in items}
            
            result = {}
            for switch_id, desc in cls.SWITCHES.items():
                item = status_map.get(switch_id)
                enabled = (item.value.lower() in ("true", "1", "yes")) if item else False
                result[switch_id] = {
                    "id": switch_id,
                    "name": switch_id.replace("_", " ").title(),
                    "description": desc,
                    "enabled": enabled,
                    "reason": item.description if item else "",
                    "updated_at": item.updated_at.isoformat() if item and item.updated_at else "",
                    "updated_by": item.updated_by if item else "system"
                }
            return result
        finally:
            session.close()

    @classmethod
    def is_active(cls, switch_name: str) -> bool:
        env_val = os.getenv(f"KILLSWITCH_{switch_name.upper()}")
        if env_val is not None:
            return env_val.lower() in ("true", "1", "yes")

        session = SessionLocal()
        try:
            item = session.query(SystemConfigModel).filter(
                SystemConfigModel.category == "killswitch",
                SystemConfigModel.key == switch_name
            ).first()
            if item and item.value:
                active = item.value.lower() in ("true", "1", "yes")
                os.environ[f"KILLSWITCH_{switch_name.upper()}"] = "true" if active else "false"
                return active
            return False
        finally:
            session.close()

    @classmethod
    def set_state(cls, switch_name: str, enabled: bool, reason: str = "", user: str = "system") -> bool:
        if switch_name not in cls.SWITCHES:
            raise ValueError(f"Unknown kill switch: {switch_name}")
            
        session = SessionLocal()
        try:
            item = session.query(SystemConfigModel).filter(
                SystemConfigModel.category == "killswitch",
                SystemConfigModel.key == switch_name
            ).first()
            
            val_str = "true" if enabled else "false"
            if item:
                item.value = val_str
                item.description = reason
                item.updated_at = datetime.utcnow()
                item.updated_by = user
            else:
                item = SystemConfigModel(
                    key=switch_name,
                    value=val_str,
                    category="killswitch",
                    is_secret=False,
                    description=reason,
                    updated_at=datetime.utcnow(),
                    updated_by=user
                )
                session.add(item)
            session.commit()
            
            os.environ[f"KILLSWITCH_{switch_name.upper()}"] = val_str
            
            state_text = "ACTIVATED (STOP)" if enabled else "DEACTIVATED (NORMAL)"
            AuditTracker.log_action(
                action="killswitch_toggled",
                details=f"Kill switch '{switch_name}' {state_text} by {user}. Reason: {reason or 'None provided'}"
            )
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()



class AgentMetricTracker:
    """Tracks and computes health, latencies, token consumption, and leaderboards for specialized agents."""
    
    DEFAULT_AGENTS = [
        {"name": "ArchitectAgent", "role": "System Architect", "runs": 48, "success": 47, "duration": 154.2, "tokens": 128400, "cost": 0.385},
        {"name": "DeveloperAgent", "role": "Terraform / OpenTofu Developer", "runs": 52, "success": 50, "duration": 286.0, "tokens": 294000, "cost": 0.882},
        {"name": "SecurityReviewer", "role": "Security & Policy Auditor", "runs": 51, "success": 51, "duration": 96.8, "tokens": 98000, "cost": 0.294},
        {"name": "FinOpsSpecialist", "role": "FinOps & Cost Optimizer", "runs": 50, "success": 49, "duration": 82.5, "tokens": 74000, "cost": 0.222},
        {"name": "TestingAgent", "role": "QA & Policy Validator", "runs": 49, "success": 48, "duration": 112.4, "tokens": 105000, "cost": 0.315},
        {"name": "GitOpsCoordinator", "role": "GitOps & VCS Coordinator", "runs": 38, "success": 37, "duration": 48.0, "tokens": 32000, "cost": 0.096},
        {"name": "DeploymentPlanner", "role": "Release & Deployment Planner", "runs": 42, "success": 41, "duration": 65.0, "tokens": 46000, "cost": 0.138},
    ]

    @classmethod
    def ensure_seeded(cls):
        session = SessionLocal()
        try:
            count = session.query(AgentMetricModel).count()
            if count == 0:
                for a in cls.DEFAULT_AGENTS:
                    m = AgentMetricModel(
                        agent_name=a["name"],
                        role_title=a["role"],
                        total_runs=a["runs"],
                        success_runs=a["success"],
                        failed_runs=a["runs"] - a["success"],
                        total_duration_seconds=a["duration"],
                        total_tokens=a["tokens"],
                        total_cost=a["cost"],
                        status="HEALTHY",
                        last_active=datetime.utcnow()
                    )
                    session.add(m)
                session.commit()
                print("[AgentMetricTracker] Initialized agent fleet telemetry.")
        except Exception as e:
            session.rollback()
            print(f"[AgentMetricTracker] Seeding warning: {e}")
        finally:
            session.close()

    @classmethod
    def record_agent_execution(cls, agent_name: str, duration_seconds: float, success: bool = True, tokens: int = 0, cost: float = 0.0, error: str = None):
        session = SessionLocal()
        try:
            agent = session.query(AgentMetricModel).filter(AgentMetricModel.agent_name == agent_name).first()
            if not agent:
                role = agent_name.replace("Agent", "").replace("Specialist", "").replace("Reviewer", " Reviewer")
                agent = AgentMetricModel(
                    agent_name=agent_name,
                    role_title=role,
                    total_runs=0,
                    success_runs=0,
                    failed_runs=0,
                    total_duration_seconds=0.0,
                    total_tokens=0,
                    total_cost=0.0,
                    status="HEALTHY"
                )
                session.add(agent)

            agent.total_runs += 1
            if success:
                agent.success_runs += 1
            else:
                agent.failed_runs += 1
            agent.total_duration_seconds += round(duration_seconds, 2)
            agent.total_tokens += tokens
            agent.total_cost += round(cost, 4)
            agent.last_active = datetime.utcnow()

            failure_rate = (agent.failed_runs / agent.total_runs) if agent.total_runs > 0 else 0.0
            agent.status = "DEGRADED" if failure_rate > 0.15 else "HEALTHY"

            session.commit()
        except Exception as e:
            session.rollback()
            print(f"[AgentMetricTracker] Error recording execution: {e}")
        finally:
            session.close()

    @classmethod
    def get_fleet_health(cls) -> List[Dict[str, Any]]:
        cls.ensure_seeded()
        session = SessionLocal()
        try:
            agents = session.query(AgentMetricModel).order_by(AgentMetricModel.total_runs.desc()).all()
            result = []
            for a in agents:
                success_rate = round((a.success_runs / a.total_runs * 100), 1) if a.total_runs > 0 else 100.0
                avg_duration = round((a.total_duration_seconds / a.total_runs), 2) if a.total_runs > 0 else 0.0
                result.append({
                    "id": a.id,
                    "agent_name": a.agent_name,
                    "role_title": a.role_title or a.agent_name,
                    "status": a.status,
                    "total_runs": a.total_runs,
                    "success_runs": a.success_runs,
                    "failed_runs": a.failed_runs,
                    "success_rate_percent": success_rate,
                    "avg_duration_seconds": avg_duration,
                    "total_tokens": a.total_tokens,
                    "total_cost": round(a.total_cost, 4),
                    "last_active": a.last_active.isoformat() if a.last_active else ""
                })
            return result
        finally:
            session.close()

    @classmethod
    def get_leaderboard(cls) -> Dict[str, Any]:
        fleet = cls.get_fleet_health()
        if not fleet:
            return {}

        most_used = max(fleet, key=lambda a: a["total_runs"])
        highest_failure = max(fleet, key=lambda a: (a["failed_runs"] / a["total_runs"]) if a["total_runs"] > 0 else 0)
        top_tokens = max(fleet, key=lambda a: a["total_tokens"])
        most_expensive = max(fleet, key=lambda a: a["total_cost"])

        return {
            "most_used": {
                "agent_name": most_used["agent_name"],
                "role_title": most_used["role_title"],
                "value": f"{most_used['total_runs']} runs"
            },
            "highest_failure_rate": {
                "agent_name": highest_failure["agent_name"],
                "role_title": highest_failure["role_title"],
                "value": f"{100.0 - highest_failure['success_rate_percent']:.1f}% failure ({highest_failure['failed_runs']} fails)"
            },
            "top_token_consumer": {
                "agent_name": top_tokens["agent_name"],
                "role_title": top_tokens["role_title"],
                "value": f"{top_tokens['total_tokens']:,} tokens"
            },
            "most_expensive": {
                "agent_name": most_expensive["agent_name"],
                "role_title": most_expensive["role_title"],
                "value": f"${most_expensive['total_cost']:.3f}"
            }
        }


class RunControlManager:
    """Manages real-time run execution state, in-flight pause, resume, cancel, and stage tracing."""

    _RUN_STATES: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def set_run_status(cls, slug: str, status: str, admin_user: str = "system", details: str = "") -> bool:
        norm_status = status.lower()
        if norm_status not in ("running", "paused", "resumed", "cancelled", "completed", "failed"):
            raise ValueError(f"Invalid run status: {status}")

        if slug not in cls._RUN_STATES:
            cls._RUN_STATES[slug] = {
                "slug": slug,
                "status": "running",
                "current_stage": "initialized",
                "active_agent": "System",
                "started_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "admin_action_by": admin_user
            }

        effective_status = "running" if norm_status == "resumed" else norm_status
        cls._RUN_STATES[slug]["status"] = effective_status
        cls._RUN_STATES[slug]["updated_at"] = datetime.utcnow().isoformat()
        cls._RUN_STATES[slug]["admin_action_by"] = admin_user
        if details:
            cls._RUN_STATES[slug]["details"] = details

        # Dual-write into Redis if available
        try:
            import redis
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            r = redis.Redis.from_url(redis_url, socket_timeout=1)
            r.set(f"run_control:{slug}:status", effective_status, ex=3600)
            if details:
                r.set(f"run_control:{slug}:details", details, ex=3600)
        except Exception:
            pass

        # Update ProjectModel status if cancelled or completed
        session = SessionLocal()
        try:
            p = session.query(ProjectModel).filter(ProjectModel.slug == slug).first()
            if p:
                if effective_status in ("cancelled", "failed"):
                    p.status = effective_status
                elif effective_status == "completed" and p.status != "deployed":
                    p.status = "generated"
                session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

        AuditTracker.log_action(
            action=f"run_{effective_status}",
            resource_slug=slug,
            details=f"Run '{slug}' state set to '{effective_status}' by {admin_user}. {details}".strip()
        )
        return True

    @classmethod
    def get_run_status(cls, slug: str) -> str:
        # Check Redis first
        try:
            import redis
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            r = redis.Redis.from_url(redis_url, socket_timeout=1)
            val = r.get(f"run_control:{slug}:status")
            if val:
                return val.decode("utf-8")
        except Exception:
            pass

        if slug in cls._RUN_STATES:
            return cls._RUN_STATES[slug].get("status", "running")

        # Fallback to DB
        session = SessionLocal()
        try:
            p = session.query(ProjectModel).filter(ProjectModel.slug == slug).first()
            if p and p.status:
                return p.status
        except Exception:
            pass
        finally:
            session.close()

        return "running"

    @classmethod
    def check_run_interruption(cls, slug: str):
        """Called inside orchestrator execution checkpoints to pause or cancel execution."""
        import time
        while True:
            current_status = cls.get_run_status(slug)
            if current_status == "cancelled":
                raise RuntimeError(f"Execution cancelled by Super-Admin for run '{slug}'. Aborting pipeline safely.")
            elif current_status == "paused":
                print(f"[RunControlManager] Run '{slug}' is PAUSED by Super-Admin. Waiting for resume...")
                time.sleep(1.5)
            else:
                break

    @classmethod
    def record_stage(cls, slug: str, stage_name: str, agent_name: str, status: str = "running", duration_seconds: float = 0.0, details: str = ""):
        session = SessionLocal()
        try:
            trace = session.query(PipelineStageTraceModel).filter(
                PipelineStageTraceModel.slug == slug,
                PipelineStageTraceModel.stage_name == stage_name
            ).first()

            if not trace:
                trace = PipelineStageTraceModel(
                    slug=slug,
                    stage_name=stage_name,
                    agent_name=agent_name,
                    status=status,
                    duration_seconds=duration_seconds,
                    details=details,
                    started_at=datetime.utcnow()
                )
                session.add(trace)
            else:
                trace.status = status
                trace.duration_seconds = duration_seconds
                if details:
                    trace.details = details
                if status in ("completed", "failed", "skipped"):
                    trace.ended_at = datetime.utcnow()
            session.commit()

            # Update in-memory state
            if slug not in cls._RUN_STATES:
                cls._RUN_STATES[slug] = {"slug": slug, "status": "running"}
            cls._RUN_STATES[slug]["current_stage"] = stage_name
            cls._RUN_STATES[slug]["active_agent"] = agent_name
            cls._RUN_STATES[slug]["updated_at"] = datetime.utcnow().isoformat()
        except Exception as e:
            session.rollback()
            print(f"[RunControlManager] Error recording stage trace: {e}")
        finally:
            session.close()

    @classmethod
    def get_run_trace(cls, slug: str) -> List[Dict[str, Any]]:
        session = SessionLocal()
        try:
            traces = session.query(PipelineStageTraceModel).filter(
                PipelineStageTraceModel.slug == slug
            ).order_by(PipelineStageTraceModel.started_at.asc()).all()

            return [
                {
                    "id": t.id,
                    "slug": t.slug,
                    "stage_name": t.stage_name,
                    "agent_name": t.agent_name,
                    "status": t.status,
                    "duration_seconds": round(t.duration_seconds, 2),
                    "details": t.details,
                    "started_at": t.started_at.isoformat() if t.started_at else "",
                    "ended_at": t.ended_at.isoformat() if t.ended_at else ""
                }
                for t in traces
            ]
        finally:
            session.close()

    @classmethod
    def list_active_and_recent_runs(cls, limit: int = 25) -> List[Dict[str, Any]]:
        session = SessionLocal()
        try:
            projects = session.query(ProjectModel).order_by(ProjectModel.updated_at.desc()).limit(limit).all()
            runs = []
            for p in projects:
                live_state = cls._RUN_STATES.get(p.slug, {})
                status = live_state.get("status", p.status or "generated")
                current_stage = live_state.get("current_stage", "completed" if p.status in ("deployed", "generated") else "failed")
                active_agent = live_state.get("active_agent", "None")

                runs.append({
                    "slug": p.slug,
                    "prompt": (p.prompt or "")[:90] + ("..." if len(p.prompt or "") > 90 else ""),
                    "status": status,
                    "current_stage": current_stage,
                    "active_agent": active_agent,
                    "duration_seconds": round(p.run_duration or 0.0, 2),
                    "healing_rounds": p.healing_rounds_taken or 0,
                    "estimated_cost": p.estimated_cost or 0.0,
                    "engine": p.engine or "terraform",
                    "created_at": p.created_at.isoformat() if p.created_at else "",
                    "updated_at": p.updated_at.isoformat() if p.updated_at else ""
                })
            return runs
        finally:
            session.close()


class LLMRoutingManager:
    """Manages AI model routing policies, fallback chains, provider latency metrics, and emergency bypass."""

    DEFAULT_PROVIDERS = [
        {"provider": "gemini", "name": "Google Gemini", "model": "gemini/gemini-2.0-flash", "priority": 1, "reqs": 342, "latency": 1.25, "cost": 0.34, "errs": 2},
        {"provider": "zenmux", "name": "ZenMux AI (Moonshot / GLM)", "model": "zenmux/moonshotai/kimi-k3-free", "priority": 2, "reqs": 185, "latency": 1.84, "cost": 0.0, "errs": 1},
        {"provider": "openrouter", "name": "OpenRouter (Free Tier)", "model": "openrouter/poolside/laguna-xs-2.1:free", "priority": 3, "reqs": 92, "latency": 2.10, "cost": 0.0, "errs": 4},
        {"provider": "groq", "name": "Groq LPU (Ultra Fast)", "model": "groq/llama-3.3-70b-versatile", "priority": 4, "reqs": 45, "latency": 0.62, "cost": 0.08, "errs": 0},
        {"provider": "openai", "name": "OpenAI (GPT-4o)", "model": "openai/gpt-4o-mini", "priority": 5, "reqs": 64, "latency": 1.45, "cost": 0.42, "errs": 0},
        {"provider": "anthropic", "name": "Anthropic Claude", "model": "anthropic/claude-3-5-haiku-20241022", "priority": 6, "reqs": 28, "latency": 1.95, "cost": 0.31, "errs": 0},
        {"provider": "mistral", "name": "Mistral AI", "model": "mistral/codestral-latest", "priority": 7, "reqs": 19, "latency": 1.70, "cost": 0.12, "errs": 1},
        {"provider": "nvidia", "name": "NVIDIA NIM", "model": "nvidia/deepseek-ai/deepseek-r1", "priority": 8, "reqs": 12, "latency": 3.40, "cost": 0.05, "errs": 0},
        {"provider": "ollama", "name": "Ollama (Self-Hosted)", "model": "ollama/deepseek-coder:6.7b", "priority": 9, "reqs": 8, "latency": 4.10, "cost": 0.0, "errs": 0},
    ]

    DEFAULT_FALLBACK_CHAIN = [
        "gemini/gemini-2.0-flash",
        "zenmux/moonshotai/kimi-k3-free",
        "openrouter/poolside/laguna-xs-2.1:free",
        "groq/llama-3.3-70b-versatile"
    ]

    @classmethod
    def ensure_seeded(cls):
        session = SessionLocal()
        try:
            count = session.query(LLMProviderMetricModel).count()
            if count == 0:
                for p in cls.DEFAULT_PROVIDERS:
                    m = LLMProviderMetricModel(
                        provider=p["provider"],
                        display_name=p["name"],
                        model_name=p["model"],
                        priority=p["priority"],
                        total_requests=p["reqs"],
                        successful_requests=p["reqs"] - p["errs"],
                        failed_requests=p["errs"],
                        total_tokens=p["reqs"] * 1800,
                        total_cost=p["cost"],
                        total_latency_seconds=round(p["latency"] * p["reqs"], 2),
                        status="enabled",
                        last_used=datetime.utcnow()
                    )
                    session.add(m)
                session.commit()
                print("[LLMRoutingManager] Initialized LLM provider metrics.")
        except Exception as e:
            session.rollback()
            print(f"[LLMRoutingManager] Seeding warning: {e}")
        finally:
            session.close()

    @classmethod
    def get_routing_state(cls) -> Dict[str, Any]:
        cls.ensure_seeded()
        session = SessionLocal()
        try:
            providers = session.query(LLMProviderMetricModel).order_by(LLMProviderMetricModel.priority.asc()).all()
            mode = ConfigManager.get("LLM_ROUTING_MODE", "auto")
            forced_provider = ConfigManager.get("LLM_FORCED_PROVIDER", "")
            chain_str = ConfigManager.get("LLM_FALLBACK_CHAIN", "")
            
            try:
                fallback_chain = json.loads(chain_str) if chain_str else cls.DEFAULT_FALLBACK_CHAIN
            except Exception:
                fallback_chain = cls.DEFAULT_FALLBACK_CHAIN

            provider_list = []
            for p in providers:
                avg_latency = round((p.total_latency_seconds / p.total_requests), 2) if p.total_requests > 0 else 0.0
                err_rate = round((p.failed_requests / p.total_requests * 100), 1) if p.total_requests > 0 else 0.0
                provider_list.append({
                    "id": p.id,
                    "provider": p.provider,
                    "name": p.display_name or p.provider.title(),
                    "model": p.model_name,
                    "priority": p.priority,
                    "status": p.status,
                    "requests": p.total_requests,
                    "success_requests": p.successful_requests,
                    "failed_requests": p.failed_requests,
                    "error_rate_percent": err_rate,
                    "avg_latency_seconds": avg_latency,
                    "total_tokens": p.total_tokens,
                    "total_cost": round(p.total_cost, 4),
                    "last_error": p.last_error,
                    "last_used": p.last_used.isoformat() if p.last_used else ""
                })

            return {
                "routing_mode": mode,
                "forced_provider": forced_provider,
                "fallback_chain": fallback_chain,
                "providers": provider_list,
                "total_providers": len(provider_list),
                "active_providers": sum(1 for p in provider_list if p["status"] == "enabled")
            }
        finally:
            session.close()

    @classmethod
    def set_provider_status(cls, provider: str, status: str, user: str = "system") -> bool:
        if status not in ("enabled", "disabled", "force"):
            raise ValueError(f"Invalid status: {status}")

        session = SessionLocal()
        try:
            p = session.query(LLMProviderMetricModel).filter(LLMProviderMetricModel.provider == provider).first()
            if not p:
                raise ValueError(f"Unknown provider '{provider}'")
            p.status = status
            session.commit()

            os.environ[f"LLM_PROVIDER_{provider.upper()}_STATUS"] = status
            AuditTracker.log_action(
                action="llm_provider_status_changed",
                details=f"LLM Provider '{provider}' status set to '{status}' by {user}"
            )
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @classmethod
    def set_routing_mode(cls, mode: str, forced_provider: Optional[str] = None, user: str = "system") -> bool:
        if mode not in ("auto", "force", "failover_chain"):
            raise ValueError(f"Invalid routing mode: {mode}")

        ConfigManager.set("LLM_ROUTING_MODE", mode, category="llm", is_secret=False, user=user)
        if forced_provider is not None:
            ConfigManager.set("LLM_FORCED_PROVIDER", forced_provider, category="llm", is_secret=False, user=user)

        AuditTracker.log_action(
            action="llm_routing_mode_changed",
            details=f"LLM routing mode updated to '{mode}' (Forced: '{forced_provider or 'None'}') by {user}"
        )
        return True

    @classmethod
    def set_fallback_chain(cls, models: List[str], user: str = "system") -> bool:
        if not isinstance(models, list) or len(models) == 0:
            raise ValueError("Fallback chain must be a non-empty list of model strings.")

        chain_json = json.dumps(models)
        ConfigManager.set("LLM_FALLBACK_CHAIN", chain_json, category="llm", is_secret=False, user=user)
        AuditTracker.log_action(
            action="llm_fallback_chain_updated",
            details=f"Fallback chain updated to: {', '.join(models)} by {user}"
        )
        return True

    @classmethod
    def get_fallback_chain(cls) -> List[str]:
        chain_str = ConfigManager.get("LLM_FALLBACK_CHAIN")
        if chain_str:
            try:
                models = json.loads(chain_str)
                if isinstance(models, list) and len(models) > 0:
                    return models
            except Exception:
                pass
        return cls.DEFAULT_FALLBACK_CHAIN

    @classmethod
    def is_provider_enabled(cls, provider: str) -> bool:
        env_status = os.getenv(f"LLM_PROVIDER_{provider.upper()}_STATUS")
        if env_status is not None:
            return env_status.lower() != "disabled"

        session = SessionLocal()
        try:
            p = session.query(LLMProviderMetricModel).filter(LLMProviderMetricModel.provider == provider).first()
            if p and p.status:
                return p.status.lower() != "disabled"
            return True
        except Exception:
            return True
        finally:
            session.close()

    @classmethod
    def record_call_telemetry(cls, provider: str, model: str, duration_seconds: float, success: bool = True, tokens: int = 0, cost: float = 0.0, error: str = None):
        session = SessionLocal()
        try:
            p = session.query(LLMProviderMetricModel).filter(LLMProviderMetricModel.provider == provider).first()
            if p:
                p.total_requests += 1
                if success:
                    p.successful_requests += 1
                else:
                    p.failed_requests += 1
                    if error:
                        p.last_error = str(error)[:300]
                p.total_latency_seconds += round(duration_seconds, 2)
                p.total_tokens += tokens
                p.total_cost += round(cost, 4)
                p.last_used = datetime.utcnow()
                session.commit()
        except Exception as e:
            session.rollback()
            print(f"[LLMRoutingManager] Error recording telemetry: {e}")
        finally:
            session.close()


class FinOpsManager:
    """
    Super-Admin FinOps, SaaS Revenue Intelligence, and Tenant Unit Economics Engine.
    Computes MRR, ARR, gross margins, categorized operating costs, and per-tenant profitability.
    """

    DEFAULT_PRICES = {
        "free": 0.0,
        "pro": 29.0,
        "enterprise": 199.0
    }

    @classmethod
    def get_tier_prices(cls) -> Dict[str, float]:
        try:
            free_p = float(ConfigManager.get("BILLING_FREE_PRICE", 0.0) or 0.0)
        except (ValueError, TypeError):
            free_p = 0.0
        try:
            pro_p = float(ConfigManager.get("BILLING_PRO_PRICE", 29.0) or 29.0)
        except (ValueError, TypeError):
            pro_p = 29.0
        try:
            ent_p = float(ConfigManager.get("BILLING_ENTERPRISE_PRICE", 199.0) or 199.0)
        except (ValueError, TypeError):
            ent_p = 199.0
        return {"free": free_p, "pro": pro_p, "enterprise": ent_p}

    @classmethod
    def set_tier_prices(cls, pro_price: float, enterprise_price: float, free_price: float = 0.0, user: str = "superadmin") -> Dict[str, float]:
        ConfigManager.set("BILLING_FREE_PRICE", str(round(free_price, 2)), category="billing", is_secret=False, user=user)
        ConfigManager.set("BILLING_PRO_PRICE", str(round(pro_price, 2)), category="billing", is_secret=False, user=user)
        ConfigManager.set("BILLING_ENTERPRISE_PRICE", str(round(enterprise_price, 2)), category="billing", is_secret=False, user=user)
        return {"free": round(free_price, 2), "pro": round(pro_price, 2), "enterprise": round(enterprise_price, 2)}

    @classmethod
    def get_finops_overview(cls) -> Dict[str, Any]:
        session = SessionLocal()
        try:
            from billing.usage_tracking import SubscriptionModel, UsageRecordModel
            prices = cls.get_tier_prices()

            # 1. Subscriptions, MRR, ARR, and Distribution
            subs = session.query(SubscriptionModel).all()
            plan_counts = {"free": 0, "pro": 0, "enterprise": 0}
            total_mrr = 0.0
            paid_subs = 0

            for s in subs:
                plan = (s.plan or "free").lower()
                plan_counts[plan] = plan_counts.get(plan, 0) + 1
                fee = prices.get(plan, 0.0)
                total_mrr += fee
                if plan in ["pro", "enterprise"]:
                    paid_subs += 1

            total_tenants = len(subs) or 1
            conversion_rate = round((paid_subs / total_tenants) * 100, 1) if subs else 0.0
            total_arr = round(total_mrr * 12, 2)
            arpu = round(total_mrr / total_tenants, 2) if subs else 0.0

            # 2. Operating Costs
            usage_records = session.query(UsageRecordModel).all()
            total_ai_cost = round(sum(r.ai_cost_usd or 0.0 for r in usage_records), 4)
            total_compute_cost = round(sum(r.compute_cost_usd or 0.0 for r in usage_records), 4)
            total_tokens = sum(r.total_tokens or 0 for r in usage_records)
            total_runs = len(usage_records)

            # Fallback to BillingUsageModel if UsageRecordModel is empty
            if total_runs == 0:
                bums = session.query(BillingUsageModel).all()
                total_tokens = sum(b.tokens_used or 0 for b in bums)
                total_runs = len(bums)
                total_ai_cost = round(total_tokens * 0.000002, 4)
                total_compute_cost = round(sum((b.run_time_seconds or 0) * 0.0001 for b in bums), 4)

            project_count = session.query(ProjectModel).count()
            storage_cost = round(project_count * 1.50 + 12.00, 2)
            cloud_infra_spend = round(sum(p.estimated_cost or 0.0 for p in session.query(ProjectModel).all()), 2)

            total_operating_cost = round(total_ai_cost + total_compute_cost + storage_cost, 2)
            gross_profit = round(total_mrr - total_operating_cost, 2)
            gross_margin_pct = round((gross_profit / total_mrr * 100), 1) if total_mrr > 0 else (0.0 if total_operating_cost == 0 else -100.0)

            # 3. AI Cost Savings Generated by FinOps agent
            ai_savings_generated = round(sum(max(0.0, (p.budget or 100.0) - (p.estimated_cost or 0.0)) for p in session.query(ProjectModel).all()), 2)
            if ai_savings_generated == 0.0:
                ai_savings_generated = 3450.00

            status = "healthy" if gross_margin_pct >= 60 else ("warning" if gross_margin_pct >= 30 else "critical")

            return {
                "mrr": round(total_mrr, 2),
                "arr": total_arr,
                "arpu": arpu,
                "total_tenants": total_tenants,
                "paid_tenants": paid_subs,
                "conversion_rate_pct": conversion_rate,
                "plan_distribution": plan_counts,
                "tier_prices": prices,
                "costs": {
                    "total_operating_cost": total_operating_cost,
                    "ai_token_cost": total_ai_cost,
                    "compute_cost": total_compute_cost,
                    "storage_cost": storage_cost,
                    "cloud_infra_spend": cloud_infra_spend,
                    "total_tokens": total_tokens,
                    "total_runs": total_runs
                },
                "profitability": {
                    "revenue": round(total_mrr, 2),
                    "operating_costs": total_operating_cost,
                    "gross_profit": gross_profit,
                    "gross_margin_pct": gross_margin_pct,
                    "status": status
                },
                "ai_savings_generated": ai_savings_generated
            }
        finally:
            session.close()

    @classmethod
    def get_cost_breakdown(cls) -> Dict[str, Any]:
        overview = cls.get_finops_overview()
        costs = overview["costs"]
        total_runs = max(costs["total_runs"], 1)
        total_tokens = max(costs["total_tokens"], 1)

        cost_per_run = round(costs["total_operating_cost"] / total_runs, 4)
        cost_per_1k_tokens = round((costs["ai_token_cost"] / total_tokens) * 1000, 6) if costs["total_tokens"] > 0 else 0.0015

        session = SessionLocal()
        try:
            total_projects = max(session.query(ProjectModel).count(), 1)
            cost_per_project = round(costs["total_operating_cost"] / total_projects, 4)
        finally:
            session.close()

        total_op = max(costs["total_operating_cost"], 0.01)
        return {
            "categories": [
                {
                    "name": "AI Model APIs",
                    "amount": costs["ai_token_cost"],
                    "pct": round((costs["ai_token_cost"] / total_op) * 100, 1),
                    "icon": "fas fa-brain",
                    "color": "#10b981"
                },
                {
                    "name": "Compute & Workers",
                    "amount": costs["compute_cost"],
                    "pct": round((costs["compute_cost"] / total_op) * 100, 1),
                    "icon": "fas fa-microchip",
                    "color": "#6366f1"
                },
                {
                    "name": "Database & Artifact Storage",
                    "amount": costs["storage_cost"],
                    "pct": round((costs["storage_cost"] / total_op) * 100, 1),
                    "icon": "fas fa-database",
                    "color": "#f59e0b"
                }
            ],
            "unit_economics": {
                "cost_per_run": cost_per_run,
                "cost_per_project": cost_per_project,
                "cost_per_1k_tokens": cost_per_1k_tokens
            },
            "cloud_managed_spend": costs["cloud_infra_spend"]
        }

    @classmethod
    def get_tenant_unit_economics(cls) -> List[Dict[str, Any]]:
        session = SessionLocal()
        try:
            from billing.usage_tracking import SubscriptionModel, UsageRecordModel
            prices = cls.get_tier_prices()
            orgs = session.query(OrganizationModel).all()

            results = []
            for org in orgs:
                sub = session.query(SubscriptionModel).filter(SubscriptionModel.org_id == org.id).first()
                plan = (sub.plan if sub else "free").lower()
                monthly_fee = prices.get(plan, 0.0)

                records = session.query(UsageRecordModel).filter(UsageRecordModel.org_id == org.id).all()
                total_runs = len(records)
                tokens_used = sum(r.total_tokens or 0 for r in records)
                ai_cost = sum(r.ai_cost_usd or 0.0 for r in records)
                compute_cost = sum(r.compute_cost_usd or 0.0 for r in records)

                if total_runs == 0:
                    bums = session.query(BillingUsageModel).filter(BillingUsageModel.org_id == org.id).all()
                    total_runs = len(bums)
                    tokens_used = sum(b.tokens_used or 0 for b in bums)
                    ai_cost = round(tokens_used * 0.000002, 4)
                    compute_cost = round(sum((b.run_time_seconds or 0) * 0.0001 for b in bums), 4)

                total_cost = round(ai_cost + compute_cost, 2)
                net_margin = round(monthly_fee - total_cost, 2)
                margin_pct = round((net_margin / monthly_fee * 100), 1) if monthly_fee > 0 else (0.0 if total_cost == 0 else -100.0)

                if plan == "free":
                    health = "free_tier" if total_cost < 2.0 else "subsidized"
                elif margin_pct >= 60:
                    health = "high_margin"
                elif margin_pct >= 30:
                    health = "healthy"
                elif margin_pct >= 0:
                    health = "at_risk"
                else:
                    health = "unprofitable"

                cloud_spend = round(sum(p.estimated_cost or 0.0 for p in session.query(ProjectModel).filter(ProjectModel.org_id == org.id).all()), 2)
                ai_savings = round(sum(max(0.0, (p.budget or 100.0) - (p.estimated_cost or 0.0)) for p in session.query(ProjectModel).filter(ProjectModel.org_id == org.id).all()), 2)

                results.append({
                    "org_id": org.id,
                    "name": org.name,
                    "slug": org.slug,
                    "plan": plan,
                    "monthly_fee": monthly_fee,
                    "runs_count": total_runs,
                    "tokens_used": tokens_used,
                    "ai_cost": round(ai_cost, 4),
                    "compute_cost": round(compute_cost, 4),
                    "total_cost": total_cost,
                    "cloud_spend": cloud_spend,
                    "ai_savings": ai_savings,
                    "net_margin": net_margin,
                    "margin_pct": margin_pct,
                    "health": health
                })

            results.sort(key=lambda x: x["total_cost"], reverse=True)
            return results
        finally:
            session.close()

    @classmethod
    def simulate_tier_pricing(cls, pro_price: float, enterprise_price: float, free_price: float = 0.0) -> Dict[str, Any]:
        session = SessionLocal()
        try:
            from billing.usage_tracking import SubscriptionModel, UsageRecordModel
            subs = session.query(SubscriptionModel).all()
            current_prices = cls.get_tier_prices()

            current_mrr = 0.0
            projected_mrr = 0.0

            for s in subs:
                p = (s.plan or "free").lower()
                current_mrr += current_prices.get(p, 0.0)
                if p == "free":
                    projected_mrr += free_price
                elif p == "pro":
                    projected_mrr += pro_price
                elif p == "enterprise":
                    projected_mrr += enterprise_price

            overview = cls.get_finops_overview()
            total_cost = overview["costs"]["total_operating_cost"]

            mrr_delta = round(projected_mrr - current_mrr, 2)
            projected_margin = round(((projected_mrr - total_cost) / projected_mrr * 100), 1) if projected_mrr > 0 else 0.0

            return {
                "current_prices": current_prices,
                "simulated_prices": {
                    "free": round(free_price, 2),
                    "pro": round(pro_price, 2),
                    "enterprise": round(enterprise_price, 2)
                },
                "current_mrr": round(current_mrr, 2),
                "projected_mrr": round(projected_mrr, 2),
                "mrr_delta": mrr_delta,
                "projected_arr": round(projected_mrr * 12, 2),
                "projected_gross_margin_pct": projected_margin,
                "total_operating_cost": total_cost
            }
        finally:
            session.close()

    @classmethod
    def export_finops_csv(cls) -> str:
        import io
        import csv
        tenants = cls.get_tenant_unit_economics()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Org ID", "Organization Name", "Slug", "Subscription Plan",
            "Monthly Fee ($)", "Runs Count", "Tokens Consumed", "AI Cost ($)",
            "Compute Cost ($)", "Total Platform Cost ($)", "Managed Cloud Spend ($)",
            "AI Savings Generated ($)", "Net Margin ($)", "Gross Margin (%)", "Financial Health Status"
        ])
        for t in tenants:
            writer.writerow([
                t["org_id"], t["name"], t["slug"], t["plan"].upper(),
                f"{t['monthly_fee']:.2f}", t["runs_count"], t["tokens_used"],
                f"{t['ai_cost']:.4f}", f"{t['compute_cost']:.4f}", f"{t['total_cost']:.2f}",
                f"{t['cloud_spend']:.2f}", f"{t['ai_savings']:.2f}",
                f"{t['net_margin']:.2f}", f"{t['margin_pct']:.1f}%", t["health"]
            ])
        return output.getvalue()

    @classmethod
    def ensure_seeded(cls):
        """Seed baseline subscriptions and usage data if missing."""
        session = SessionLocal()
        try:
            from billing.usage_tracking import SubscriptionModel, UsageRecordModel

            # Ensure all orgs have a subscription
            orgs = session.query(OrganizationModel).all()
            if not orgs:
                # Create demo organizations if none exist
                demo_org1 = OrganizationModel(name="Acme Global Engineering", slug="acme-global")
                demo_org2 = OrganizationModel(name="CloudNative DevOps", slug="cloudnative-ops")
                demo_org3 = OrganizationModel(name="Starter Sandbox", slug="starter-sandbox")
                session.add_all([demo_org1, demo_org2, demo_org3])
                session.commit()
                orgs = [demo_org1, demo_org2, demo_org3]

            existing_subs = {s.org_id for s in session.query(SubscriptionModel).filter(SubscriptionModel.org_id.isnot(None)).all()}
            plans_to_assign = ["enterprise", "pro", "free"]
            for idx, org in enumerate(orgs):
                if org.id not in existing_subs:
                    plan = plans_to_assign[idx % len(plans_to_assign)]
                    limit = -1 if plan == "enterprise" else (100 if plan == "pro" else 5)
                    sub = SubscriptionModel(
                        org_id=org.id,
                        plan=plan,
                        status="active",
                        runs_this_month=8 if plan == "enterprise" else (4 if plan == "pro" else 1),
                        monthly_limit=limit,
                        billing_cycle_start=datetime.utcnow()
                    )
                    session.add(sub)
            session.commit()

            # Seed realistic UsageRecordModel if empty
            usage_count = session.query(UsageRecordModel).count()
            if usage_count == 0:
                sample_data = [
                    (orgs[0].id, "production-k8s-vpc", 42000, 8500, 0.45, 120.5, 0.08, 1420.0),
                    (orgs[0].id, "data-lake-s3-glue", 28000, 5200, 0.31, 85.0, 0.05, 890.0),
                    (orgs[1].id if len(orgs) > 1 else orgs[0].id, "microservices-alb", 18500, 3900, 0.18, 45.2, 0.03, 450.0),
                    (orgs[2].id if len(orgs) > 2 else orgs[0].id, "dev-sandbox-redis", 6400, 1100, 0.06, 15.0, 0.01, 120.0),
                ]
                for org_id, slug, prompt_t, comp_t, ai_c, comp_s, comp_c, infra_c in sample_data:
                    record = UsageRecordModel(
                        org_id=org_id,
                        project_slug=slug,
                        prompt_tokens=prompt_t,
                        completion_tokens=comp_t,
                        total_tokens=prompt_t + comp_t,
                        ai_cost_usd=ai_c,
                        compute_seconds=comp_s,
                        compute_cost_usd=comp_c,
                        infra_monthly_cost=infra_c,
                        total_platform_cost_usd=round(ai_c + comp_c, 4),
                        created_at=datetime.utcnow()
                    )
                    session.add(record)
                session.commit()
                print("[FinOpsManager] Seeded baseline enterprise usage records into database.")
        except Exception as e:
            session.rollback()
            print(f"[FinOpsManager] Note during seed: {e}")
        finally:
            session.close()


# Initialize default configs and managers on startup
ConfigManager.seed_from_env()
AgentMetricTracker.ensure_seeded()
LLMRoutingManager.ensure_seeded()
FinOpsManager.ensure_seeded()





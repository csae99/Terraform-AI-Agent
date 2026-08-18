import os
import json
import re
import glob
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Float, Integer, Text, DateTime, JSON, ForeignKey
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
            "approved_by_id": "INTEGER DEFAULT NULL"
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

        session.commit()
    except Exception as e:
        print(f"[Tracker DB] Warning: could not automatically add columns to database: {e}")
    finally:
        session.close()

_add_missing_columns()


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
             pr_status=None, approval_status=None, approved_by_id=None):
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
    def add_member(org_id, user_id, role="member"):
        session = SessionLocal()
        try:
            existing = session.query(OrgMemberModel).filter(
                OrgMemberModel.org_id == org_id,
                OrgMemberModel.user_id == user_id
            ).first()
            if existing:
                existing.role = role
            else:
                member = OrgMemberModel(org_id=org_id, user_id=user_id, role=role)
                session.add(member)
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
    def get_logs(org_id=None, user_id=None, limit=50):
        """Retrieve audit logs scoped by organization or user."""
        session = SessionLocal()
        try:
            query = session.query(AuditLogModel)
            if org_id is not None:
                query = query.filter(AuditLogModel.org_id == org_id)
            elif user_id is not None:
                query = query.filter(AuditLogModel.user_id == user_id)
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



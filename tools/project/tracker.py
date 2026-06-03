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
    projects = relationship("ProjectModel", back_populates="owner")

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
    qa_report = Column(Text, default="")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Ownership
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner = relationship("UserModel", back_populates="projects")

# Create tables
Base.metadata.create_all(bind=engine)

def _add_missing_columns():
    """Dynamically adds missing columns to projects table if they don't exist."""
    from sqlalchemy import inspect, text
    session = SessionLocal()
    try:
        db_engine = session.bind
        inspector = inspect(db_engine)
        columns = [c["name"] for c in inspector.get_columns("projects")]
        new_cols = {
            "healing_rounds_taken": "INTEGER DEFAULT 0",
            "run_duration": "REAL DEFAULT 0.0",
            "errors_encountered": "JSON DEFAULT '[]'",
            "patterns_applied": "JSON DEFAULT '[]'",
            "qa_report": "TEXT DEFAULT ''",
            "reflection_advice": "JSON DEFAULT NULL"
        }
        for col_name, col_def in new_cols.items():
            if col_name not in columns:
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
                print(f"[Tracker DB] Dynamically added missing column: {col_name}")
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
    def save(slug, prompt=None, status=None, budget=None,
             estimated_cost=None, security_issues=None, provider=None, 
             flags=None, mermaid_diagram=None, drift_status=None, owner_id=None,
             healing_rounds_taken=None, run_duration=None, errors_encountered=None,
             patterns_applied=None, qa_report=None, reflection_advice=None):
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
                project.healing_rounds_taken = healing_rounds_taken if healing_rounds_taken is not None else 0
                project.run_duration = run_duration if run_duration is not None else 0.0
                project.errors_encountered = errors_encountered if errors_encountered is not None else []
                project.patterns_applied = patterns_applied if patterns_applied is not None else []
                project.qa_report = qa_report or ""
                project.reflection_advice = reflection_advice
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
                if healing_rounds_taken is not None: project.healing_rounds_taken = healing_rounds_taken
                if run_duration is not None: project.run_duration = run_duration
                if errors_encountered is not None: project.errors_encountered = errors_encountered
                if patterns_applied is not None: project.patterns_applied = patterns_applied
                if qa_report is not None: project.qa_report = qa_report
                if reflection_advice is not None: project.reflection_advice = reflection_advice
            
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
                    "qa_report": project.qa_report,
                    "created_at": project.created_at.isoformat(),
                    "updated_at": project.updated_at.isoformat()
                }
            return None
        finally:
            session.close()

    @staticmethod
    def load_all(owner_id=None):
        """Load all projects from DB. Optionally filter by owner."""
        session = SessionLocal()
        try:
            query = session.query(ProjectModel)
            if owner_id:
                # Show projects owned by user OR unassigned projects (legacy/CLI)
                query = query.filter((ProjectModel.owner_id == owner_id) | (ProjectModel.owner_id == None))
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
                    "updated_at": p.updated_at.isoformat(),
                    "owner_id": p.owner_id
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

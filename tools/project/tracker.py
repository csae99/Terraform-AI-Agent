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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Ownership
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner = relationship("UserModel", back_populates="projects")

# Create tables
Base.metadata.create_all(bind=engine)


class ProjectTracker:
    """
    SQL-backed Project Tracker.
    Maintains metadata in PostgreSQL/SQLite for scalability.
    """

    OUTPUT_DIR = "output"

    @staticmethod
    def save(slug, prompt="", status="generated", budget=0.0,
             estimated_cost=0.0, security_issues=0, provider="Local", 
             flags=None, mermaid_diagram="", drift_status="unknown", owner_id=None):
        """Save or update project metadata in DB."""
        session = SessionLocal()
        try:
            project = session.query(ProjectModel).filter(ProjectModel.slug == slug).first()
            
            if not project:
                project = ProjectModel(slug=slug)
                session.add(project)
            
            if prompt: project.prompt = prompt
            if status: project.status = status
            if budget: project.budget = budget
            project.estimated_cost = estimated_cost
            project.security_issues = security_issues
            if provider: project.provider = provider
            if mermaid_diagram: project.mermaid_diagram = mermaid_diagram
            if drift_status: project.drift_status = drift_status
            if flags is not None: project.flags = flags
            if owner_id: project.owner_id = owner_id
            
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

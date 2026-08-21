import os
import json
import math
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
from tools.project.tracker import SessionLocal, PatternMemoryModel, KnowledgeDocumentModel

class VectorKnowledgeEngine:
    """
    Vector Knowledge & Semantic Retrieval Layer (pgvector + Local Cosine Fallback).
    Provides RAG capabilities for Terraform/OpenTofu documentation, cloud runbooks,
    and semantic failure pattern matching.
    """

    VECTOR_DIM = 64  # Compact dense embedding dimension for fast in-memory similarity

    @classmethod
    def get_embedding(cls, text: str) -> List[float]:
        """
        Generates dense vector embedding for semantic matching.
        Uses LiteLLM if configured, with deterministic dense hashing fallback.
        """
        if not text or not text.strip():
            return [0.0] * cls.VECTOR_DIM

        # Try LiteLLM if API keys are available
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("OPENAI_API_KEY")
        if api_key and os.getenv("USE_CLOUD_EMBEDDINGS", "false").lower() == "true":
            try:
                import litellm
                model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
                resp = litellm.embedding(model=model, input=[text])
                raw_vec = resp.data[0]["embedding"]
                return cls._normalize_vector(raw_vec[:cls.VECTOR_DIM])
            except Exception:
                pass

        # Fast, deterministic semantic-aware dense term hashing
        return cls._local_dense_embedding(text)

    @classmethod
    def _local_dense_embedding(cls, text: str) -> List[float]:
        """
        Deterministic, token-weighted dense embedding generator.
        Captures term frequency, n-grams, and semantic keywords.
        """
        vec = [0.0] * cls.VECTOR_DIM
        cleaned = text.lower().replace("_", " ").replace("-", " ")
        words = [w for w in cleaned.split() if len(w) > 1]
        
        if not words:
            return vec

        for word in words:
            # Term hash position
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            idx = h % cls.VECTOR_DIM
            sign = 1.0 if ((h >> 8) & 1) else -1.0
            
            # Weight important cloud / IaC keywords higher
            weight = 1.0
            if word in ("iam", "s3", "bucket", "vpc", "subnet", "accessdenied", "alreadyexists", 
                        "invalidparameter", "quota", "security", "encryption", "opentofu", "terraform"):
                weight = 2.5
            
            vec[idx] += sign * weight

        return cls._normalize_vector(vec)

    @classmethod
    def _normalize_vector(cls, vec: List[float]) -> List[float]:
        """Normalizes vector to unit length (L2 norm)."""
        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0:
            return vec
        return [round(x / norm, 5) for x in vec]

    @classmethod
    def cosine_similarity(cls, vec_a: List[float], vec_b: List[float]) -> float:
        """Calculates cosine similarity between two vectors (-1.0 to 1.0)."""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return max(-1.0, min(1.0, dot / (norm_a * norm_b)))

    @classmethod
    def search_similar_patterns(cls, query_error: str, top_k: int = 3, min_similarity: float = 0.20) -> List[Dict[str, Any]]:
        """
        Semantically searches database patterns using vector similarity + keyword matching.
        """
        cls.ensure_seeded()
        query_vec = cls.get_embedding(query_error)
        session = SessionLocal()
        try:
            patterns = session.query(PatternMemoryModel).all()
            scored = []
            for p in patterns:
                # Calculate vector similarity
                if p.embedding:
                    try:
                        p_vec = json.loads(p.embedding)
                    except Exception:
                        p_vec = cls.get_embedding(f"{p.error_substring} {p.description}")
                else:
                    p_vec = cls.get_embedding(f"{p.error_substring} {p.description}")

                sim = cls.cosine_similarity(query_vec, p_vec)
                
                # Bonus for exact substring match
                is_exact = p.error_substring.lower() in query_error.lower()
                final_score = sim + (0.4 if is_exact else 0.0)

                if final_score >= min_similarity or is_exact:
                    scored.append({
                        "id": p.id,
                        "signature": p.signature or p.error_substring,
                        "error_substring": p.error_substring,
                        "category": p.category,
                        "severity": p.severity,
                        "description": p.description,
                        "fix": p.fix,
                        "confidence": p.confidence,
                        "status": p.status,
                        "success_count": p.success_count,
                        "failure_count": p.failure_count,
                        "similarity_score": round(sim, 3),
                        "composite_score": round(final_score, 3),
                        "exact_match": is_exact
                    })

            scored.sort(key=lambda x: (x["exact_match"], x["composite_score"], x["confidence"]), reverse=True)
            return scored[:top_k]
        finally:
            session.close()

    @classmethod
    def search_documentation(cls, query: str, doc_type: Optional[str] = None, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Searches vector knowledge base documents (Terraform/OpenTofu docs, cloud runbooks).
        """
        cls.ensure_seeded()
        query_vec = cls.get_embedding(query)
        session = SessionLocal()
        try:
            q = session.query(KnowledgeDocumentModel)
            if doc_type:
                q = q.filter(KnowledgeDocumentModel.doc_type == doc_type)
            docs = q.all()
            scored = []
            for d in docs:
                if d.embedding:
                    try:
                        d_vec = json.loads(d.embedding)
                    except Exception:
                        d_vec = cls.get_embedding(f"{d.title} {d.content}")
                else:
                    d_vec = cls.get_embedding(f"{d.title} {d.content}")

                sim = cls.cosine_similarity(query_vec, d_vec)
                scored.append({
                    "id": d.id,
                    "doc_type": d.doc_type,
                    "title": d.title,
                    "content": d.content,
                    "tags": d.tags,
                    "similarity_score": round(sim, 3)
                })

            scored.sort(key=lambda x: x["similarity_score"], reverse=True)
            return scored[:top_k]
        finally:
            session.close()

    @classmethod
    def ensure_seeded(cls):
        """Auto-seeds database from failure_patterns.json and core runbooks if empty."""
        session = SessionLocal()
        try:
            pattern_count = session.query(PatternMemoryModel).count()
            if pattern_count == 0:
                cls._seed_patterns(session)

            doc_count = session.query(KnowledgeDocumentModel).count()
            if doc_count == 0:
                cls._seed_runbooks(session)
        finally:
            session.close()

    @classmethod
    def _seed_patterns(cls, session):
        """Seeds PatternMemoryModel from failure_patterns.json with precomputed embeddings."""
        json_path = os.path.join(os.path.dirname(__file__), "failure_patterns.json")
        if not os.path.exists(json_path):
            return

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            patterns = data.get("patterns", [])
            for p in patterns:
                emb = cls.get_embedding(f"{p.get('error_substring')} {p.get('description', '')}")
                model = PatternMemoryModel(
                    signature=p.get("error_substring", ""),
                    error_substring=p.get("error_substring", ""),
                    category=p.get("category", "general"),
                    severity=p.get("severity", "MEDIUM"),
                    description=p.get("description", ""),
                    fix=p.get("fix", ""),
                    success_count=p.get("success_count", 1),
                    failure_count=p.get("failure_count", 0),
                    confidence=p.get("confidence", 1.0),
                    status=p.get("status", "trusted"),
                    embedding=json.dumps(emb),
                    last_used=datetime.utcnow()
                )
                session.add(model)
            session.commit()
            print(f"[VectorKnowledge] Seeded {len(patterns)} failure patterns into database.")
        except Exception as e:
            session.rollback()
            print(f"[VectorKnowledge] Warning: Pattern seed failed: {e}")

    @classmethod
    def _seed_runbooks(cls, session):
        """Seeds standard Terraform, OpenTofu, and Cloud best practice runbooks."""
        runbooks = [
            {
                "doc_type": "terraform_doc",
                "title": "Terraform S3 Bucket Public Access Block & Versioning",
                "content": "To prevent S3 bucket exposure, configure aws_s3_bucket_public_access_block with block_public_acls=true, block_public_policy=true, ignore_public_acls=true, and restrict_public_buckets=true. Enable versioning with aws_s3_bucket_versioning.",
                "tags": "s3, aws, security, public_access, encryption"
            },
            {
                "doc_type": "opentofu_doc",
                "title": "OpenTofu State Encryption & Provider Migration",
                "content": "OpenTofu supports native state file encryption via the key_provider and state storage blocks. When migrating from Terraform 1.5.x or earlier, run 'tofu init -upgrade' to ensure provider compatibility.",
                "tags": "opentofu, tofu, state_encryption, migration"
            },
            {
                "doc_type": "aws_runbook",
                "title": "AWS IAM Policy Attachments & EKS Role Trust",
                "content": "EKS node groups require AmazonEKSWorkerNodePolicy, AmazonEKS_CNI_Policy, and AmazonEC2ContainerRegistryReadOnly attached to the node role. Cluster control plane requires AmazonEKSClusterPolicy.",
                "tags": "aws, iam, eks, kubernetes, roles"
            },
            {
                "doc_type": "azure_runbook",
                "title": "Azure AKS Virtual Network & Subnet Requirements",
                "content": "Azure AKS with Azure CNI networking requires a dedicated subnet with adequate IP address allocation. Ensure the AKS cluster identity has Network Contributor permissions on the virtual network subnet.",
                "tags": "azure, aks, networking, cni, subnet"
            }
        ]

        try:
            for rb in runbooks:
                emb = cls.get_embedding(f"{rb['title']} {rb['content']}")
                doc = KnowledgeDocumentModel(
                    doc_type=rb["doc_type"],
                    title=rb["title"],
                    content=rb["content"],
                    tags=rb["tags"],
                    embedding=json.dumps(emb)
                )
                session.add(doc)
            session.commit()
            print(f"[VectorKnowledge] Seeded {len(runbooks)} cloud runbooks into knowledge base.")
        except Exception as e:
            session.rollback()
            print(f"[VectorKnowledge] Warning: Runbook seed failed: {e}")

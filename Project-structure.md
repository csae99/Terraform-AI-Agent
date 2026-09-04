# 📂 Autonomous Platform Engineering Ecosystem: Project Structure & Architecture Reference

This document provides a comprehensive, production-grade reference for the **Autonomous Infrastructure Platform & Platform Engineering Ecosystem (Phases 1 – 15)**.

---

## 🏗️ Repository Directory Tree

```text
c:\Users\User\Music\Terraform-AI-Agent\
├── agents/                       # Specialized CrewAI Agent definitions
│   ├── __init__.py
│   ├── architect.py              # System topology & visual Mermaid architect
│   ├── developer.py              # Core IaC synthesis & modular code developer
│   ├── security.py               # Security auditor (Checkov & tfsec integration)
│   ├── finops.py                 # Financial analyst & Infracost cost modeler
│   ├── deployment.py             # Live cloud deployment specialist (apply/destroy)
│   ├── testing_agent.py          # Continuous QA & behavior smoke testing agent
│   └── gitops_coordinator.py     # Git branch, PR generation & commit coordinator
│
├── crews/                        # Multi-agent crew assemblies & task bindings
│   ├── __init__.py
│   └── terraform_crew.py         # CrewAI sequential/hierarchical orchestrator
│
├── orchestrator/                 # Central execution pipeline & retry handling
│   ├── __init__.py
│   ├── pipeline.py               # Authoritative entrypoint (`run_full_pipeline`)
│   └── retry_handler.py          # Self-healing loop & structured decision tracer
│
├── workflows/                    # End-to-end task workflows
│   ├── __init__.py
│   └── terraform_generation.py   # High-level generation workflow
│
├── tools/                        # Deterministic execution tools & binary wrappers
│   ├── __init__.py
│   ├── base.py                   # Tool base classes
│   ├── engine/                   # Universal IaC Engine Abstraction Layer
│   │   ├── __init__.py
│   │   ├── base.py               # Abstract Base Engine (`IaCEngine`)
│   │   ├── terraform_engine.py   # HashiCorp Terraform CLI adapter
│   │   ├── opentofu_engine.py    # Linux Foundation OpenTofu CLI adapter
│   │   └── factory.py            # Dynamic engine factory with auto-fallback
│   ├── deployment/               # Cloud deployment & drift scanner
│   │   ├── __init__.py
│   │   ├── deployment_tools.py   # Terraform / OpenTofu apply & destroy tool
│   │   └── drift_detector.py     # Cloud state snooper & drift detection tool
│   ├── linters/                  # Static analysis & security scanners
│   │   ├── __init__.py
│   │   ├── checkov_tool.py       # Deep policy & vulnerability scanner
│   │   └── tfsec_tool.py         # High-speed binary security scanner
│   ├── finops/                   # Cost estimation tools
│   │   ├── __init__.py
│   │   └── infracost_tool.py     # Infracost monthly budget & breakdown tool
│   ├── testing/                  # Behavior testing tools
│   │   ├── __init__.py
│   │   └── qa_test_tool.py       # Post-apply HTTP & cloud status smoke tester
│   ├── gitops/                   # Version control & PR automation tools
│   │   ├── __init__.py
│   │   ├── git_tools.py          # Git branch, staging & commit manager
│   │   └── github_pr_tool.py     # GitHub & GitLab PR synthesizer
│   └── project/                  # Persistence & state tracking
│       ├── __init__.py
│       ├── tracker.py            # SQLite / PostgreSQL ORM database models
│       └── audit_tracker.py      # Immutable enterprise audit logging
│
├── memory/                       # Self-learning failure memory & pgvector RAG
│   ├── __init__.py
│   ├── pattern_manager.py        # Database-backed `PatternMemoryModel` manager
│   ├── vector_knowledge.py       # pgvector & cosine similarity RAG knowledge engine
│   └── failure_patterns.json     # Initial seed failure pattern bank
│
├── policy/                       # Policy-as-Code & Enterprise Guardrails (Phase 13)
│   ├── __init__.py
│   ├── opa_engine.py             # Open Policy Agent (OPA) / Rego AST evaluator
│   ├── guardrails.py             # Organization region & budget boundary validator
│   └── compliance/               # Pre-packaged enterprise compliance rulepacks
│       ├── soc2.rego             # SOC2 Type II compliance pack
│       ├── hipaa.rego            # HIPAA healthcare data compliance pack
│       ├── pci_dss.rego          # PCI-DSS v4.0 payment security pack
│       └── cis_benchmarks.rego   # CIS Cloud Architecture Benchmarks
│
├── sso/                          # Enterprise SSO & Identity Federation (Phase 13)
│   ├── __init__.py
│   ├── providers.py              # Entra ID, Okta, Google Workspace, Auth0 config
│   ├── oidc.py                   # OpenID Connect discovery, auth URL & JWT claims
│   └── saml.py                   # SAML 2.0 XML assertion token parser
│
├── consensus/                    # Multi-Agent Consensus & Debate Engine (Phase 13)
│   ├── __init__.py
│   ├── debate_engine.py          # Multi-Agent Debate coordinator (Dev A vs B vs Reviewer)
│   └── consensus_scorer.py       # 4-dimensional weighted consensus matrix
│
├── cloud_optimizer/              # Multi-Cloud Optimization Engine (Phase 13)
│   ├── __init__.py
│   ├── multi_cloud.py            # Automated AWS vs Azure vs GCP comparative analysis
│   └── provider_comparator.py    # Service equivalency & pricing comparator
│
├── aiops/                        # AI Operations Center & Model Routing (Phase 13)
│   ├── __init__.py
│   ├── monitoring.py             # Real-time agent health & error taxonomy telemetry
│   ├── alerts.py                 # Active governance & budget anomaly alert manager
│   └── model_router.py           # Task-complexity-based dynamic LLM router
│
├── marketplace/                  # Agent Marketplace & Plugin SDK (Phase 14)
│   ├── __init__.py
│   ├── plugin_sdk.py             # `BasePlugin`, `CustomToolPlugin`, `CustomAgentPlugin`
│   ├── catalog.py                # Pre-built agent registry (K8s, FinOps, DR, SecOps)
│   └── manager.py                # Tenant plugin installation & lifecycle manager
│
├── portal/                       # Internal Developer Portal & Workflows (Phase 14)
│   ├── __init__.py
│   ├── workflow_engine.py        # Visual DAG execution graph engine with branching
│   ├── templates.py              # Golden Path enterprise service blueprints
│   ├── approvals.py              # Dynamic risk-weighted approval gate evaluator
│   └── agent_governance.py       # 0-100 composite risk scoring & agent permissions
│
├── optimization/                 # Self-Optimizing Infrastructure (Phase 14)
│   ├── __init__.py
│   ├── finops_optimizer.py       # Compute right-sizing, spot workloads & S3 tiering
│   ├── autonomous_remediation.py # Drift/error detection & surgical patch auto-apply
│   └── recommendations.py        # Actionable quantified dollar savings cards
│
├── dr/                           # Disaster Recovery & Regional Failover (Phase 14)
│   ├── __init__.py
│   ├── dr_manager.py             # Cross-region state backups & RTO/RPO tracker
│   └── failover.py               # Automated regional failover orchestrator
│
├── observability/                # OpenTelemetry & Prometheus Observability (Phase 12)
│   ├── __init__.py
│   ├── tracing.py                # Distributed OpenTelemetry tracer & span collector
│   ├── metrics.py                # Prometheus metrics exporter & JSON summaries
│   └── analytics.py              # Executive KPI analytics & pattern leaderboard
│
├── billing/                      # Usage Metering & Dual Payment Gateways (Phase 12)
│   ├── __init__.py
│   ├── metering.py               # 3-Way cost attribution (AI Tokens, Compute, Cloud)
│   ├── usage_tracking.py         # Subscription models, quotas & billing tracker
│   ├── razorpay_service.py       # Razorpay gateway (INR, UPI, Cards, NetBanking)
│   ├── stripe_service.py         # Stripe gateway (Global cards, USD subscriptions)
│   └── invoicing.py              # Monthly statements & invoice generator
│
├── app/                          # Application Gateways & Web Server
│   ├── __init__.py
│   ├── main.py                   # CLI entrypoint with argparse
│   └── dashboard.py              # FastAPI Web Gateway with REST & SSE streaming
│
├── k8s/                          # Kubernetes Control Plane & GitOps Operator (Phase 15)
│   ├── crds/                     # Custom Resource Definitions (OpenAPI v3 schemas)
│   │   ├── platform.terraform-ai.io_terraformagents.yaml
│   │   ├── platform.terraform-ai.io_platformprojects.yaml
│   │   ├── platform.terraform-ai.io_workflows.yaml
│   │   └── platform.terraform-ai.io_policies.yaml
│   ├── operator/                 # Operator Controller & Reconciliation Engine
│   │   ├── __init__.py
│   │   ├── crd_schema.py         # Pydantic models for CRD schemas
│   │   ├── reconciler.py         # Declarative reconciliation loop & K8s events
│   │   ├── status_manager.py     # Condition transitions & timestamp management
│   │   └── drift_watcher.py      # Background cloud drift watcher & auto-healing
│   ├── gitops/                   # GitOps Controller Integrations
│   │   ├── __init__.py
│   │   ├── argocd_plugin.py      # ArgoCD custom Lua health checks & CM patch
│   │   └── flux_controller.py    # Flux CD webhook receiver & commit synchronizer
│   └── helm/                     # Production Helm 3 Chart
│       ├── Chart.yaml            # Package metadata (v1.0.0)
│       ├── values.yaml           # Deployment configurations & replicas
│       └── templates/            # Kubernetes deployment & RBAC manifests
│           ├── deployment.yaml   # Operator Deployment with health probes
│           └── rbac.yaml         # ClusterRole, Binding & ServiceAccount
│
├── static/                       # Web Dashboard Frontend
│   ├── index.html                # Modern glassmorphism single-page application UI
│   ├── login.html                # Enterprise login & SSO portal UI
│   ├── app.js                    # Dynamic reactive state manager & SSE stream reader
│   └── style.css                 # Custom curated dark-mode CSS design system
│
├── test-cases/                   # Test suites & manual verification plans
│   ├── MANUAL_TEST_PLAN.md       # Complete 19-scenario manual test roadmap
│   ├── test_backend_integration.py
│   ├── test_api_endpoints.py
│   └── test_observability.py
│
├── scratch/                      # Automated verification test suites
│   ├── test_phase15_k8s_control_plane.py # Phase 15 comprehensive K8s control plane test suite
│   ├── test_phase14.py           # Phase 14 comprehensive test suite
│   ├── test_phase13.py           # Phase 13 comprehensive test suite
│   ├── test_live_e2e.py          # Live REST API end-to-end test suite
│   ├── test_vector_knowledge.py  # pgvector & knowledge RAG test suite
│   ├── test_observability.py     # OpenTelemetry & Prometheus test suite
│   └── test_billing.py           # Billing & dual payment gateway test suite
│
├── .env.example                  # Environment configuration template
├── docker-compose.yml            # Docker stack (App, Redis, PostgreSQL with pgvector)
├── Dockerfile                    # Container definition
├── requirements.txt              # Production Python dependencies
├── setup.md                      # Comprehensive setup & troubleshooting guide
├── MULTI_AGENT_ARCHITECTURE.md   # Architectural reference guide
├── phase-13.md                   # Phase 13 requirements specification
├── phase-14.md                   # Phase 14 requirements specification
├── phase-15.md                   # Phase 15 requirements specification
├── co-pilot-review.md            # Co-pilot architecture reviews & audit logs
└── README.md                     # Main project hub & executive documentation
```

---

## 🏛️ Architectural Bounded Contexts

| Bounded Context | Directory | Primary Responsibilities |
|:---|:---|:---|
| **Core Multi-Agent Pipeline** | `agents/`, `crews/`, `orchestrator/` | Multi-agent collaboration, HCL synthesis, security auditing, self-healing retry logic, decision tracing. |
| **Kubernetes Control Plane & GitOps** | `k8s/` | Declarative Custom Resource Definitions (CRDs), Operator controller reconciler loop, ArgoCD/Flux GitOps integration, Helm 3 deployment. |
| **IaC Engine Abstraction** | `tools/engine/` | Universal runtime interface supporting Terraform and OpenTofu transparently. |
| **Marketplace & Extensions** | `marketplace/` | Agent catalog, Plugin SDK (`BasePlugin`), tenant installation and hook execution. |
| **Internal Developer Portal** | `portal/` | DAG visual workflow engine, Golden Path blueprints, risk-weighted approval evaluation. |
| **Autonomous Optimization** | `optimization/` | FinOps compute right-sizing, spot workloads, S3 lifecycle tiering, autonomous remediation. |
| **Disaster Recovery (DR)** | `dr/` | Cross-region state backups, RTO/RPO metrics, automated regional failover orchestration. |
| **Policy & Governance** | `policy/` | Open Policy Agent (OPA/Rego) evaluator, compliance packs (SOC2, HIPAA, PCI, CIS), organization guardrails. |
| **Identity Federation** | `sso/` | OIDC and SAML 2.0 single sign-on (Entra ID, Okta, Google Workspace, Auth0). |
| **Consensus & Multi-Cloud** | `consensus/`, `cloud_optimizer/` | Multi-agent debate scoring matrix, AWS vs. Azure vs. GCP comparative synthesis. |
| **AIOps Center** | `aiops/` | Telemetry aggregator, active incident alerting, task-complexity intelligent model router. |
| **Observability & Metering** | `observability/`, `billing/` | OpenTelemetry distributed tracing, Prometheus metrics, 3-way cost attribution, Razorpay/Stripe billing. |
| **Storage & Memory** | `memory/`, `tools/project/` | PostgreSQL with `pgvector`, persistent `PatternMemoryModel`, SQLite fallback, immutable audit logs. |
| **Web Gateway & UI** | `app/`, `static/` | FastAPI REST API, SSE log streaming, responsive dark-mode glassmorphic web dashboard. |

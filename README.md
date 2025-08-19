
# Aistratus

Aistratus is a personal cloud-native project that deploys a custom TinyLlama workflow on AWS and serves as a rigorous testbed for modern engineering practice. Everything is Infrastructure-as-Code: Terraform plus an environment-aware SSM registry enables reproducible, destroy/apply deployments without manual steps. Beyond running an LLM flow, the project demonstrates disciplined cloud architecture, DevOps, and CI/CD in a real AWS context.

---

## Architecture

Aistratus is AWS-native and IaC-driven. API Gateway fronts a Lambda Router protected by Cognito-compatible JWTs. Cross-environment IDs are stored in SSM Parameter Store. Networking runs in a dedicated VPC. A lightweight Desktop GUI (MVC) drives local orchestration and testing. The Router enqueues work to an SQS FIFO queue; an EC2 inference node is planned to consume jobs.

```mermaid
flowchart TD
  subgraph Client
    GUI[Desktop GUI (MVC)]
  end

  subgraph Edge
    APIGW[API Gateway]
    COG[Cognito-compatible JWT]
  end

  subgraph Compute
    LMB[Lambda Router]
    EC2[(EC2 Inference Node)]:::pending
  end

  subgraph Platform
    SSM[SSM Parameter Store]
    S3[S3 (Terraform State / Lambda Layers)]
    SQS[[SQS FIFO Job Queue]]:::done
    CW[CloudWatch (logs/alarms)]:::partial
  end

  GUI --> APIGW
  COG --> APIGW
  APIGW --> LMB
  LMB --> SSM
  LMB -. enqueue jobs .-> SQS
  EC2 -. consume jobs .-> SQS
  LMB --> CW
  EC2 --> CW

  classDef done fill:#E7F8EF,stroke:#19A974,color:#114;
  classDef partial fill:#FFF6E5,stroke:#FFB000,color:#331;
  classDef pending fill:#FDEDEE,stroke:#E74C3C,color:#611;

  class APIGW,LMB,SSM,S3,GUI,SQS done;
  class CW partial;
  class EC2 pending;
````

Notes:

* Authentication: JWT enforcement at the API layer. The Lambda Router performs lightweight request checks; a Pydantic schema is available in the API package and tests and can be wired into the production path if needed.
* S3 usage: Terraform remote state and Lambda layer artifacts. No runtime Router writes to S3 at present.

---

## Architecture Development & MVP Timeline (pre-GUI)

Key milestones before GUI-001 (2025-06-13), derived from your commit history:

* 2025-05-26 — Initial repo foundation committed: README, architecture docs/diagrams.
* 2025-05-28 — Security/IaC scaffold added: IAM, S3, Secrets scripts and policy files; README updated.
* 2025-06-03 to 2025-06-05 — Orchestration & CI/CD baseline: package refactor to `tinyllama`, Lambda router moved under orchestration, Terraform placeholder added; deployment artifacts plus buildspec/trust policies added and hardened.
* 2025-06-06 to 2025-06-12 — Architecture documentation matured: “final” and intermediate diagrams, requirements, product-owner wish; Prompt-Maker docs; CLI automation for epics.

(If you want the ultra-precise hash/date lines, keep your `commit_history.txt` alongside the repo for auditors.)

---

## Component Status

| Area                         | Function                                                    | Status  | References                |
| ---------------------------- | ----------------------------------------------------------- | ------- | ------------------------- |
| Terraform IaC + SSM registry | Reproducible infra; env-aware IDs in SSM                    | Done    | INFRA-001, INFRA-002      |
| API Gateway + JWT            | Secure edge; JWT authorizer for `/infer`; `/health` exposed | Done    | API-001, API-002          |
| Lambda Router                | Routes (`/health`, `/infer`); CI/CD hardened                | Done    | LAM-001                   |
| Desktop GUI (MVC)            | Local controller; auth, idle, cost display                  | Done    | GUI-001 … GUI-007, Epic 1 |
| CloudWatch                   | Log groups + p95 latency alarm                              | Partial | Observability module      |
| SQS FIFO Job Queue           | Async job dispatch (Router → SQS)                           | Done    | SQS-001                   |
| EC2 Inference Node           | GPU/CPU backend; build and cost controls                    | Pending | (future tickets)          |

---

## Closed Issues (Milestones)

Reverse-chronological list of closed, non-obsolete tickets:

* 2025-08-19 — SQS-001 (#75): Provision SQS FIFO Job Queue and integrate with infra
* 2025-07-23 — INFRA-002 (#72): Global ID registry via SSM Parameter Store (Option 1)
* 2025-07-23 — LAM-001 (#69): Enable Router with real JWT and body parsing/validation path
* 2025-07-01 — INFRA-001 (#64): Bootstrap remote state & base VPC
* 2025-06-25 — API-002 (#51): JWT Authorizer via Cognito
* 2025-06-20 — API-001 (#50): API Skeleton & Test Harness
* 2025-06-18 — GUI-007 (#47): Refactor Desktop into modular MVC + services
* 2025-06-18 — Epic 1 (#1): Desktop GUI core delivered
* 2025-06-14 — GUI-006 (#7): Output pane shows full conversation
* 2025-06-14 — GUI-005 (#6): Cost label polls live spend
* 2025-06-13 — GUI-004 (#5): Idle-timeout spinbox controls auto-stop
* 2025-06-13 — GUI-003 (#4): Red Stop-GPU button triggers `/stop`
* 2025-06-13 — GUI-002 (#3): Send button disables & shows spinner
* 2025-06-13 — GUI-001 (#2): Prompt box accepts multi-line input

(For narrative detail and lessons learned, see `Merged_Tickets.md`.)

---

## Quick Start

Deploy infra and Router:

```bash
python tools.py tf-apply
```

Run the Desktop GUI (from the project root):

```bash
python -m tinyllama.gui.main
```

Notes:

* The deploy step rebuilds `router.zip`, applies Terraform, and writes the live API URL into `.env_public`.
* CI uses the GitHub OIDC role to read SSM IDs; workflows are under `.github/workflows/`.

---

## Future Vision

Next milestones include EC2 inference integration, cost management automation, and streamlined build workflows. Medium-term goals:

1. Continuous fine-tuning pipeline for personalized TinyLlama weights.
2. RAG integration to unify orchestration with context-aware inference.

---

## Repository Hygiene

* Legacy JSON policy examples that reference deprecated API IDs are retained as examples. Active infrastructure is fully Terraform-managed; prefer the Terraform modules over standalone JSON snippets.

---

**Author**: Rusbeh Abtahi
**Contact**: [roosbab@gmail.com](mailto:roosbab@gmail.com)
**Created**: May 2025



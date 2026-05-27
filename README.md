# DevOps Engineer — 90 Minute Infrastructure Challenge

A minimal but production-style Kubernetes deployment with CI/CD,
observability via probes, and a live debugging demonstration.

## Stack

- **App:** FastAPI (Python 3.12), 1 service, 2 replicas
- **DB:** PostgreSQL 16 (single replica, emptyDir — see Tradeoffs)
- **Cluster:** Kind (Kubernetes in Docker)
- **CI/CD:** GitHub Actions → GHCR → `kubectl apply`
- **Reliability:** Tuned readiness + liveness probes

## Quick Start (local)

```bash
# 1. Create cluster
kind create cluster --config kind-config.yaml

# 2. Build image
docker build -t devops-challenge-app:local ./app

# 3. Load image into Kind (no registry needed for local)
kind load docker-image devops-challenge-app:local --name my-cluster

# 4. Update image ref in app-deployment.yaml to devops-challenge-app:local
#    (or use kustomize / Helm in a real setup)
sed -i 's|ghcr.io/YOUR_GH_USER/devops-challenge-app:latest|devops-challenge-app:local|' \
  k8s/app-deployment.yaml

# 5. Deploy
kubectl apply -f k8s/

# 6. Watch
kubectl get pods -n devops-challenge -w

# 7. Test
curl http://localhost:8080/health
curl -X POST http://localhost:8080/items \
  -H 'Content-Type: application/json' -d '{"name":"hello"}'
curl http://localhost:8080/items
```

## Reliability Choice — Probes (with reasoning)

**Why probes?** Without them, Kubernetes only knows if a process has exited.
A pod can be "Running" while completely broken (deadlocked, DB lost, OOM-recovering).
Probes give Kubernetes real signal.

**Two probes, two jobs — this is the key insight:**

| Probe | Endpoint | What it checks | What happens on failure |
|-------|----------|----------------|--------------------------|
| Liveness | `/health` | Process alive | **Restart container** |
| Readiness | `/ready` | DB reachable | **Remove from Service endpoints** |

**Why separate them?** If liveness also checked the DB, a transient DB outage
would cause every app pod to restart in a tight loop — turning a brief blip into
a full outage. With them separated, pods are pulled from load balancing during
the blip but quietly rejoin when the DB recovers. No restarts, no thundering herd.

**Tradeoffs:**
- Probes too aggressive (`failureThreshold: 1`, short timeouts) → false positives, flapping
- Probes too lenient → users see 5xx for longer
- `/ready` hitting the DB adds load — fine here, but in high-QPS services you'd
  cache the result for ~1s or use a lightweight liveness file

## Intentional Failure Scenario

**What I'll break:** Change the readiness probe to hit `/healthz` (a path that
doesn't exist). The container runs fine, the app serves traffic on `/health`
and `/ready`, but Kubernetes thinks the pod is never ready.

**Symptoms:**
- `kubectl get pods` → pods stuck `0/1 Running`
- `kubectl get svc app -o yaml` → endpoints list is empty
- `curl http://localhost:8080/health` → connection refused (no ready endpoints)

**Debug sequence I'll demo:**

```bash
# 1. Confirm the symptom
kubectl get pods -n devops-challenge

# 2. Look at the pod — events tell the story
kubectl describe pod -n devops-challenge -l app=api | tail -30
# → "Readiness probe failed: HTTP probe failed with statuscode: 404"

# 3. Verify the app itself is fine
kubectl exec -n devops-challenge deploy/app -- \
  python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read())"
# → b'{"status":"ok"}'   <-- app works!

# 4. So the app is healthy but probe path is wrong. Fix:
kubectl edit deployment/app -n devops-challenge
# change /healthz back to /ready

# 5. Watch recovery
kubectl rollout status deployment/app -n devops-challenge
kubectl get endpoints app -n devops-challenge   # endpoints repopulate
```

**Root cause:** Probe path typo. **Lesson:** Probes are config, and config bugs
look identical to app bugs from the outside. Always verify with `kubectl exec`
that the app endpoint actually responds before assuming the app is broken.

## Tradeoffs I Made Knowingly

| Simplification | What breaks at scale | Production fix |
|----------------|----------------------|----------------|
| Postgres with `emptyDir` | Data lost on pod restart | StatefulSet + PVC + storage class with backups |
| Single Postgres replica | No HA, RPO = last backup | Managed RDS / Cloud SQL, or operator (CloudNativePG) |
| Secret in plain YAML | Credentials in git | Sealed Secrets / External Secrets Operator / Vault |
| `latest` tag in default manifest | Non-reproducible deploys | Pin to SHA, GitOps with image updater |
| NodePort | Not a real ingress | Ingress controller (nginx/Traefik) + cert-manager + TLS |
| No HPA | Can't handle traffic spikes | HorizontalPodAutoscaler on CPU + custom metrics |
| No PodDisruptionBudget | Node drains can take service down | PDB with `minAvailable: 1` |
| No observability stack | Can't debug at scale | Prometheus + Grafana + Loki, OpenTelemetry traces |
| No NetworkPolicy | Pods can talk to anything | Default-deny + explicit allows |

## Video Script (8–12 min)

### 1. Live Demo (3–4 min)
```
- Show: kubectl get nodes, kubectl get pods -n devops-challenge
- Show: curl /health, POST /items, GET /items
- Show: kubectl get deploy,svc,secret -n devops-challenge
- Open GitHub → Actions tab → green run with build + deploy jobs
- Open the latest commit → show image pushed to GHCR
```

### 2. Architecture Walkthrough (2–3 min)
```
- Diagram (or just talk over the YAML):
  GitHub push → Actions runner → docker build → GHCR push
                                              → kubectl apply
                                              → rolling update
                                              → probes gate traffic
- Why Kind: fast, scriptable, CI-friendly
- Why GHCR: free, no extra auth, integrates with GH_TOKEN
- Why two probes: explained above
- Why namespace: isolation + easy teardown
```

### 3. Failure Debugging (2–3 min) — MOST IMPORTANT SECTION
```
- Before recording: apply the broken manifest (probe path = /healthz)
- On camera:
  "I'm getting reports the API is down. Let me look."
  kubectl get pods       → 0/1 Ready (huh, but it's Running?)
  kubectl logs           → app looks fine, serving requests
  Hypothesis 1: maybe DB? kubectl exec → /ready works
  → so app is fine, but k8s thinks it isn't. What does k8s see?
  kubectl describe pod   → "Readiness probe failed: 404 on /healthz"
  → Probe path is wrong. Fix and apply.
  kubectl rollout status → recovers in ~15s
  curl /items            → working
  "Lesson: 'Running but not Ready' almost always = probe config issue"
```

### 4. Tradeoffs (1–2 min)
- Walk through the table above
- Emphasize: I knew these were shortcuts, here's how I'd fix each

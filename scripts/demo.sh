#!/bin/bash
# Usage: ./demo.sh break   |   ./demo.sh fix   |   ./demo.sh status

set -e
NS=devops-challenge

case "$1" in
  break)
    echo "🔥 Breaking readiness probe (changing /ready to /healthz)..."
    kubectl patch deployment app -n $NS --type=json -p='[
      {"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/path","value":"/healthz"}
    ]'
    echo "Watch the pods become NotReady:"
    echo "  kubectl get pods -n $NS -w"
    ;;
  fix)
    echo "✅ Fixing readiness probe (restoring /ready)..."
    kubectl patch deployment app -n $NS --type=json -p='[
      {"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/path","value":"/ready"}
    ]'
    echo "Watch the pods recover:"
    echo "  kubectl rollout status deployment/app -n $NS"
    ;;
  status)
    echo "=== Pods ==="
    kubectl get pods -n $NS
    echo ""
    echo "=== Service endpoints (empty = no pods receiving traffic) ==="
    kubectl get endpoints app -n $NS
    echo ""
    echo "=== Current readiness probe path ==="
    kubectl get deployment app -n $NS -o jsonpath='{.spec.template.spec.containers[0].readinessProbe.httpGet.path}'
    echo ""
    ;;
  *)
    echo "Usage: $0 {break|fix|status}"
    exit 1
    ;;
esac

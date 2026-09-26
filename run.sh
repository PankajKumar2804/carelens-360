#!/usr/bin/env bash
# CareLens 360 — pipeline runner.
# Usage: ./run.sh all | setup | data | docs | gold | semantic | agent | gov | eval | demo | app
set -euo pipefail
CONN="${SNOW_CONNECTION:-default}"
run() { echo "▶ $1"; snow sql -c "$CONN" -f "$1"; }

stage_files() {
  echo "▶ staging synthetic files"
  snow sql -c "$CONN" -q "
    PUT file://$(pwd)/data/structured/*.csv @CARELENS.RAW.STRUCTURED_STAGE OVERWRITE=TRUE AUTO_COMPRESS=FALSE;
    PUT file://$(pwd)/data/docs/*.md       @CARELENS.RAW.DOC_STAGE        OVERWRITE=TRUE AUTO_COMPRESS=FALSE;
    ALTER STAGE CARELENS.RAW.DOC_STAGE REFRESH;"
}

case "${1:-all}" in
  setup)    run sql/00_setup.sql ;;
  data)     python3 scripts/gen_synthetic.py; stage_files; run sql/01_load_structured.sql ;;
  docs)     run sql/02_documents.sql ;;
  gold)     run sql/03_gold_360.sql ;;
  semantic) run sql/04_semantic_view.sql ;;
  agent)    run sql/05_search_and_agent.sql ;;
  gov)      run sql/06_governance.sql ;;
  eval)     run sql/07_eval.sql ;;
  demo)     snow sql -c "$CONN" -f demo/demo_queries.sql ;;
  app)      snow streamlit deploy --replace ;;
  all)
    run sql/00_setup.sql
    python3 scripts/gen_synthetic.py
    stage_files
    run sql/01_load_structured.sql
    run sql/02_documents.sql
    run sql/03_gold_360.sql
    run sql/04_semantic_view.sql
    run sql/05_search_and_agent.sql
    run sql/06_governance.sql
    run sql/07_eval.sql
    echo "✅ deployed. next: ./run.sh app"
    ;;
  *) echo "unknown target: $1"; exit 1 ;;
esac

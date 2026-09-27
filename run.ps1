$ErrorActionPreference = "Stop"
$env:PATH += ";C:\Users\panka\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\Scripts"

function Run-Sql($file) {
    Write-Host "▶ $file"
    snow sql -c NL29901 -f $file
}

Run-Sql "sql/00_setup.sql"

Write-Host "▶ generating synthetic data"
python scripts/gen_synthetic.py

Write-Host "▶ staging synthetic files"
$cwd = (Get-Location).Path.Replace('\', '/')
snow sql -c NL29901 -q "
PUT file://$cwd/data/structured/*.csv @CARELENS.RAW.STRUCTURED_STAGE OVERWRITE=TRUE AUTO_COMPRESS=FALSE;
PUT file://$cwd/data/docs/*.md       @CARELENS.RAW.DOC_STAGE        OVERWRITE=TRUE AUTO_COMPRESS=FALSE;
ALTER STAGE CARELENS.RAW.DOC_STAGE REFRESH;
"

Run-Sql "sql/01_load_structured.sql"
Run-Sql "sql/02_documents.sql"
Run-Sql "sql/03_gold_360.sql"
Run-Sql "sql/04_semantic_view.sql"
Run-Sql "sql/05_search_and_agent.sql"
Run-Sql "sql/06_governance.sql"
Run-Sql "sql/07_eval.sql"

Write-Host "▶ deploying streamlit app"
snow streamlit deploy --replace -c NL29901
Write-Host "✅ CareLens 360 deployed successfully!"
$ErrorActionPreference = "Stop"
$env:PATH += ";C:\Users\panka\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\Scripts"

Write-Host "▶ deploying streamlit app directly"
$cwd2 = (Get-Location).Path.Replace('\', '/')
snow sql -c NL29901 -q "
USE ROLE CARELENS_ADMIN; USE WAREHOUSE CARELENS_WH;
PUT file://$cwd2/app/carelens_app.py @CARELENS.AI.STREAMLIT_STAGE/ OVERWRITE=TRUE AUTO_COMPRESS=FALSE;
CREATE OR REPLACE STREAMLIT CARELENS.AI.CARELENS_360_COPILOT
  ROOT_LOCATION = '@CARELENS.AI.STREAMLIT_STAGE'
  MAIN_FILE = 'carelens_app.py'
  QUERY_WAREHOUSE = CARELENS_WH
  TITLE = 'CareLens 360 Copilot'
  COMMENT = 'Patient/member 360 and clinical-regulatory document copilot. Synthetic data.';
GRANT USAGE ON STREAMLIT CARELENS.AI.CARELENS_360_COPILOT TO ROLE CARELENS_CLINICIAN;
GRANT USAGE ON STREAMLIT CARELENS.AI.CARELENS_360_COPILOT TO ROLE CARELENS_CARE_MGR;
GRANT USAGE ON STREAMLIT CARELENS.AI.CARELENS_360_COPILOT TO ROLE CARELENS_ANALYST;
"
Write-Host "✅ Streamlit app deployed successfully!"

"""Execute the CareLens 360 SQL pipeline against Snowflake.
Works around the Microsoft Store Python stub issue where platform.libc_ver()
fails because sys.executable is a reparse point that can't be opened as a file.
"""
import platform
import subprocess
import sys
from pathlib import Path

# ---- monkey-patch before importing snowflake.connector ----
_orig_libc_ver = platform.libc_ver
def _safe_libc_ver(*args, **kwargs):
    try:
        return _orig_libc_ver(*args, **kwargs)
    except OSError:
        return ("", "")
platform.libc_ver = _safe_libc_ver

import snowflake.connector  # noqa: E402


def split_statements(sql: str) -> list[str]:
    stmts, buf, in_dollar = [], [], False
    for line in sql.splitlines():
        if "$$" in line:
            in_dollar = not in_dollar if line.count("$$") % 2 == 1 else in_dollar
        buf.append(line)
        if not in_dollar and line.rstrip().endswith(";"):
            stmts.append("\n".join(buf))
            buf = []
    if buf:
        remainder = "\n".join(buf).strip()
        if remainder:
            stmts.append(remainder)
    return [s.strip().rstrip(";").strip() for s in stmts if s.strip().rstrip(";").strip()]


def run_file(cur, filepath: str):
    print(f"▶ {filepath}")
    sql = Path(filepath).read_text(encoding="utf-8")
    for stmt in split_statements(sql):
        if not stmt or stmt.startswith("/*"):
            continue
        tag = stmt.split("\n")[0][:80]
        try:
            cur.execute(stmt)
            try:
                row = cur.fetchone()
            except Exception:
                row = None
            print(f"  ✓ {tag}")
        except snowflake.connector.errors.ProgrammingError as e:
            if "Unsupported feature" in str(e):
                print(f"  ⚠ SKIPPED (unsupported): {tag}")
            else:
                print(f"  ✗ FAILED: {tag}")
                print(f"    {e}")
                raise


def main():
    print("Connecting to Snowflake…")
    conn = snowflake.connector.connect(
        account="rq98990.ap-southeast-1",
        user="PANKAJKR",
        authenticator="externalbrowser",
    )
    cur = conn.cursor()

    try:
        run_file(cur, "sql/00_setup.sql")

        print("▶ generating synthetic data")
        subprocess.run([sys.executable, "scripts/gen_synthetic.py"], check=True)

        print("▶ staging synthetic files")
        cwd = Path.cwd().as_posix()
        cur.execute(f"PUT file://{cwd}/data/structured/*.csv @CARELENS.RAW.STRUCTURED_STAGE OVERWRITE=TRUE AUTO_COMPRESS=FALSE")
        print(f"  ✓ CSV files staged")
        cur.execute(f"PUT file://{cwd}/data/docs/*.md @CARELENS.RAW.DOC_STAGE OVERWRITE=TRUE AUTO_COMPRESS=FALSE")
        print(f"  ✓ doc files staged")
        cur.execute("ALTER STAGE CARELENS.RAW.DOC_STAGE REFRESH")

        sql_files = [
            "sql/01_load_structured.sql",
            "sql/02_documents.sql",
            "sql/03_gold_360.sql",
            "sql/04_semantic_view.sql",
            "sql/05_search_and_agent.sql",
            "sql/06_governance.sql",
            "sql/07_eval.sql",
        ]
        for f in sql_files:
            run_file(cur, f)

        print("▶ deploying streamlit app")
        cur.execute(f"PUT file://{cwd}/app/carelens_app.py @CARELENS.AI.STREAMLIT_STAGE/app/ OVERWRITE=TRUE AUTO_COMPRESS=FALSE")
        cur.execute("""CREATE OR REPLACE STREAMLIT CARELENS.AI.CARELENS_360_COPILOT
            ROOT_LOCATION = '@CARELENS.AI.STREAMLIT_STAGE'
            MAIN_FILE = '/app/carelens_app.py'
            QUERY_WAREHOUSE = CARELENS_WH
            TITLE = 'CareLens 360 Copilot'
            COMMENT = 'Patient/member 360 and clinical-regulatory document copilot. Synthetic data.'""")

        print("✅ CareLens 360 deployed successfully!")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()

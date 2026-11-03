"""Generate the TPC-H sample data (scale factor 1) as Parquet for the local DuckDB target.

    python scripts/setup_data.py

Writes data/tpch_sf1/<table>.parquet (about 350 MB, takes ~10 seconds).
Not needed for the Snowflake target, which reads SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "tpch_sf1"
TABLES = ["lineitem", "orders", "customer", "supplier", "nation", "region"]


def already_there() -> bool:
    return all((OUT / f"{t}.parquet").exists() for t in TABLES)


def with_tpchgen() -> bool:
    exe = shutil.which("tpchgen-cli")
    if not exe:
        return False
    subprocess.run(
        [exe, "parquet", "-s", "1", f"--output-dir={OUT}", f"--tables={','.join(TABLES)}"],
        check=True,
    )
    return True


def with_duckdb() -> None:
    # Fallback: DuckDB's own TPC-H extension (downloads the extension on first use).
    import duckdb

    con = duckdb.connect()
    con.execute("install tpch")
    con.execute("load tpch")
    con.execute("call dbgen(sf = 1)")
    for t in TABLES:
        con.execute(f"copy {t} to '{(OUT / f'{t}.parquet').as_posix()}' (format parquet)")


def main() -> None:
    if already_there():
        print(f"Data already present in {OUT}")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    print("Generating TPC-H scale factor 1 ...")
    if not with_tpchgen():
        print("tpchgen-cli not found, falling back to DuckDB's tpch extension")
        with_duckdb()
    missing = [t for t in TABLES if not (OUT / f"{t}.parquet").exists()]
    if missing:
        sys.exit(f"Missing tables after generation: {missing}")
    print(f"Done: {OUT}")


if __name__ == "__main__":
    main()

"""Run the packaged editor acceptance against a private PostgreSQL or MySQL server.

Run with the Python interpreter containing the installed Ciaren wheel, Playwright,
asyncpg and aiomysql. See qa/assistant/README.md. No existing database URL is accepted.
"""

import argparse
import asyncio
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from editor_smoke import assert_private_audit, fixture_env, run, serve
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.models.dataset import Dataset
from app.db.models.dataset_version import DatasetVersion
from app.db.models.flow import AssistantActivity, Flow
from app.db.models.project import Project

PREVIOUS = "c9d0e1f2a3b4"
HEAD = "ea641bc97f21"


@contextmanager
def database(args, work):
    """Own the cluster, generate its credentials, and listen exclusively on loopback."""
    data = work / "cluster"
    with socket.socket() as available:
        available.bind(("127.0.0.1", 0))
        port = available.getsockname()[1]
    password = secrets.token_hex(24)
    bootstrap = work / "bootstrap"
    bootstrap.touch(mode=0o600)
    env = fixture_env(work)
    # Extracted distribution packages can require non-system shared libraries.
    if "LD_LIBRARY_PATH" in os.environ:
        env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
    if args.engine == "postgresql":
        bindir = args.pg_bindir
        bootstrap.write_text(password + "\n")
        init = [
            str(bindir / "initdb"),
            "-D",
            str(data),
            "-U",
            "ciaren",
            "--no-locale",
            "--encoding=UTF8",
            "--auth-local=reject",
            "--auth-host=scram-sha-256",
            f"--pwfile={bootstrap}",
        ]
        if args.pg_share:
            init.extend(["-L", str(args.pg_share)])
        start = [
            str(bindir / "postgres"),
            "-D",
            str(data),
            "-c",
            "unix_socket_directories=",
            "-c",
            "listen_addresses=127.0.0.1",
            "-p",
            str(port),
        ]
        url = f"postgresql+asyncpg://ciaren:{password}@127.0.0.1:{port}/postgres"
    else:
        bootstrap.write_text(
            f"ALTER USER 'root'@'localhost' IDENTIFIED BY '{secrets.token_hex(32)}';\n"
            "CREATE DATABASE ciaren_audit CHARACTER SET utf8mb4;\n"
            f"CREATE USER 'ciaren'@'127.0.0.1' IDENTIFIED BY '{password}';\n"
            "GRANT ALL ON ciaren_audit.* TO 'ciaren'@'127.0.0.1';\n"
        )
        common = [
            str(args.mysqld),
            "--no-defaults",
            f"--datadir={data}",
            "--socket=",
            f"--pid-file={work}/mysql.pid",
            "--secure-file-priv=NULL",
            "--mysqlx=OFF",
            "--bind-address=127.0.0.1",
            f"--port={port}",
            "--skip-name-resolve",
            "--innodb-buffer-pool-size=64M",
        ]
        if args.mysql_basedir:
            common.append(f"--basedir={args.mysql_basedir}")
        if args.mysql_messages:
            common.append(f"--lc-messages-dir={args.mysql_messages}")
        init = [*common, "--initialize-insecure"]
        start = [*common, f"--init-file={bootstrap}"]
        url = f"mysql+aiomysql://ciaren:{password}@127.0.0.1:{port}/ciaren_audit"

    log = work / "database.log"
    with log.open("wb") as output:
        launched = subprocess.run(init, cwd=work, env=env, stdout=output, stderr=subprocess.STDOUT, timeout=120)
        if launched.returncode:
            raise RuntimeError(f"Private database initialization failed with status {launched.returncode}")
        proc = subprocess.Popen(start, cwd=work, env=env, stdout=output, stderr=subprocess.STDOUT)
        try:
            asyncio.run(wait_for_server(proc, url, data, args.engine, log))
            bootstrap.unlink()
            yield url
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)


async def wait_for_server(proc, url, data, dialect, log):
    engine = create_async_engine(url)
    try:
        end = time.monotonic() + 45
        while True:
            if proc.poll() is not None:
                raise RuntimeError(f"Private database exited before startup with status {proc.returncode}")
            if time.monotonic() >= end:
                raise TimeoutError("Private database did not become ready")
            message = "ready to accept connections" if dialect == "postgresql" else "ready for connections"
            if message in log.read_text(errors="replace"):
                break
            await asyncio.sleep(0.15)
        async with engine.begin() as conn:
            if dialect == "mysql":
                assert Path(await conn.scalar(text("SELECT @@datadir"))).resolve() == data.resolve()
                assert await conn.scalar(text("SELECT @@bind_address")) == "127.0.0.1"
                assert not await conn.scalar(text("SELECT @@socket"))
                assert "MySQL" in await conn.scalar(text("SELECT @@version_comment"))
            else:
                assert Path(await conn.scalar(text("SHOW data_directory"))).resolve() == data.resolve()
                assert await conn.scalar(text("SHOW listen_addresses")) == "127.0.0.1"
                assert not await conn.scalar(text("SHOW unix_socket_directories"))
            print("Live server:", await conn.scalar(text("SELECT version()")), engine.url.drivername, flush=True)
    finally:
        await engine.dispose()


def legacy_graph(dataset):
    def node(id, kind, label, x, config):
        return dict(id=id, type=kind, position={"x": x, "y": 80}, data={"label": label, "config": config})

    return {
        "engine": "pandas",
        "nodes": [
            node(
                "legacy-input",
                "fileInput",
                "Legacy input",
                50,
                {"format": "csv", "dataset_id": dataset, "dataset_version": 1},
            ),
            node(
                "legacy-output", "fileOutput", "Legacy output", 350, {"format": "csv", "dataset_name": "legacy-result"}
            ),
        ],
        "edges": [
            {
                "id": "legacy-link",
                "source": "legacy-input",
                "target": "legacy-output",
                "sourceHandle": "out",
                "targetHandle": "in",
            }
        ],
    }


async def inspect_database(url, dialect, work, phase, legacy=None, race=None):
    engine = create_async_engine(url)
    flows = Flow.__table__.c
    activity = AssistantActivity.__table__.c
    try:
        async with engine.begin() as conn:
            assert (
                conn.dialect.name == dialect
                and conn.dialect.driver == {"postgresql": "asyncpg", "mysql": "aiomysql"}[dialect]
            )
            assert await conn.scalar(text("SELECT version_num FROM alembic_version")) == (
                PREVIOUS if phase == "seed" else HEAD
            )
            present = await conn.run_sync(lambda c: inspect(c).has_table("assistant_activity"))
            assert present == (phase != "seed")
            if phase == "seed":
                project, dataset, flow = (str(uuid4()) for _ in range(3))
                file = work / "legacy.csv"
                file.write_text("amount\n17\n")
                graph = legacy_graph(dataset)
                await conn.execute(Project.__table__.insert().values(id=project, name="Before upgrade"))
                await conn.execute(
                    Dataset.__table__.insert().values(id=dataset, project_id=project, name=file.name, source_type="csv")
                )
                await conn.execute(
                    DatasetVersion.__table__.insert().values(
                        dataset_id=dataset,
                        version_number=1,
                        location=str(file),
                        schema_json=[{"name": "amount", "dtype": "int64"}],
                        row_count=1,
                    )
                )
                await conn.execute(
                    Flow.__table__.insert().values(
                        id=flow, project_id=project, name="Pre-migration CSV", graph_json=graph
                    )
                )
                return {"flow": flow, "graph": graph}
            assert await conn.scalar(select(flows.graph_json).where(flows.id == legacy["flow"])) == legacy["graph"]
            if dialect == "mysql":
                assert (
                    await conn.scalar(
                        text(
                            "SELECT datetime_precision FROM information_schema.columns "
                            "WHERE table_schema=database() AND table_name='flows' AND column_name='updated_at'"
                        )
                    )
                    == 6
                )
            if phase == "finish":
                facts = (await conn.execute(select(activity.details, activity.inverse))).all()
                assert facts
                assert_private_audit(json.dumps([tuple(row) for row in facts], ensure_ascii=False))
                records = (
                    await conn.execute(
                        select(activity.id, activity.source, activity.reverses)
                        .where(activity.flow_id == race[0])
                        .order_by(activity.created_at)
                    )
                ).all()
                assert await conn.scalar(select(flows.graph_json).where(flows.id == race[0])) == race[3]
                assert (
                    len(records) == 2
                    and records[0] == (race[1], "build", None)
                    and records[1] == (race[2], "revert", race[1])
                )
                print("Direct database audit confirmed the single winning apply and its linked reversal.", flush=True)
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", choices=["postgresql", "mysql"])
    parser.add_argument("--pg-bindir", type=Path)
    parser.add_argument("--pg-share", type=Path)
    parser.add_argument("--mysqld", type=Path)
    parser.add_argument("--mysql-basedir", type=Path)
    parser.add_argument("--mysql-messages", type=Path)
    parser.add_argument("--screenshots", type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error("Use an unprivileged account.")
    if not (args.pg_bindir if args.engine == "postgresql" else args.mysqld):
        parser.error("Provide the database binary location.")
    import app

    assert Path(app.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()), (
        "Install the wheel in a dedicated venv."
    )
    cli = Path(sys.executable).with_name("ciaren")
    shots = args.screenshots.resolve()
    shots.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ciaren-db-") as temp:
        work = Path(temp)
        with database(args, work) as url:
            env = fixture_env(work)
            env.update(CIAREN_DATABASE_URL=url, CIAREN_DATA_DIR=str(work / "app-data"))

            def migrate(rev):
                subprocess.run(
                    [str(cli), "db", "upgrade", "--revision", rev], cwd=work, env=env, check=True, timeout=60
                )

            migrate(PREVIOUS)
            legacy = asyncio.run(inspect_database(url, args.engine, work, "seed"))
            migrate("head")
            asyncio.run(inspect_database(url, args.engine, work, "migrated", legacy))
            print(f"Packaged CLI migrated {PREVIOUS} -> {HEAD}. Existing graph verified.", flush=True)
            with serve(work, env, sys.executable) as base:
                race = run(base, shots, work, python=sys.executable, legacy=legacy)
            asyncio.run(inspect_database(url, args.engine, work, "finish", legacy, race))
            assert not (work / "ciaren.db").exists()
    print(f"{args.engine}: packaged migration, editor, data and concurrency acceptance passed; private server stopped.")


if __name__ == "__main__":
    main()

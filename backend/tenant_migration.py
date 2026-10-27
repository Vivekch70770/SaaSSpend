"""Explicit, backup-first migration for the Stage 2.1 tenant schema."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import os
import sqlite3
import unicodedata
import uuid
from pathlib import Path
from typing import Any

LEGACY_ORGANIZATION_ID = "b9c9b8cb-88a2-4c45-a4cf-95cc1263eb51"
LEGACY_ORGANIZATION_NAME = "Legacy organization"
MIGRATION_VERSION = "stage2.1-tenant-schema"
APPLICATION_FIELDS = (
    "name",
    "category",
    "cost",
    "licenses",
    "active",
    "risk",
    "renewal",
    "annual",
    "renewal_reviewed",
)
SUPPORTED_LEGACY_APPLICATION_COLUMNS = frozenset(APPLICATION_FIELDS)


class MigrationError(RuntimeError):
    """Raised when a migration precondition or validation fails."""


def normalize_application_name(name: str) -> str:
    return unicodedata.normalize("NFKC", name.strip()).casefold()


def _read_only_connection(path: Path) -> sqlite3.Connection:
    uri = f"{path.resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.execute("PRAGMA query_only = ON")
    return connection


def _application_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(applications)")
    }
    if columns != SUPPORTED_LEGACY_APPLICATION_COLUMNS:
        unexpected = sorted(columns - SUPPORTED_LEGACY_APPLICATION_COLUMNS)
        missing = sorted(SUPPORTED_LEGACY_APPLICATION_COLUMNS - columns)
        details = []
        if unexpected:
            details.append(f"unexpected columns: {', '.join(unexpected)}")
        if missing:
            details.append(f"missing columns: {', '.join(missing)}")
        raise MigrationError(
            "The source applications schema is not supported ("
            + "; ".join(details)
            + ")"
        )
    query = "SELECT " + ", ".join(APPLICATION_FIELDS) + " FROM applications ORDER BY rowid"
    rows = []
    for raw in connection.execute(query):
        rows.append(dict(zip(APPLICATION_FIELDS, raw)))
    return rows


def _validate_source(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 8:
        raise MigrationError(f"Expected exactly 8 legacy applications; found {len(rows)}")
    normalized_names = [normalize_application_name(row["name"]) for row in rows]
    if any(not name for name in normalized_names):
        raise MigrationError("Application names must not be blank")
    if len(set(normalized_names)) != len(normalized_names):
        raise MigrationError("Application names collide after normalization")
    if any(row["renewal_reviewed"] not in (0, 1) for row in rows):
        raise MigrationError("Invalid renewal review flag in source applications")


def _verify_backup(
    backup_path: Path,
    expected_rows: list[dict[str, Any]],
) -> None:
    with closing(_read_only_connection(backup_path)) as backup:
        integrity = backup.execute("PRAGMA integrity_check").fetchone()[0]
        rows = _application_rows(backup)
        if integrity != "ok" or rows != expected_rows:
            raise MigrationError("The database backup failed integrity or field verification")


def create_verified_backup(database_path: Path, backup_path: Path) -> None:
    if not database_path.is_file():
        raise MigrationError("The target database does not exist")
    if backup_path.exists():
        raise MigrationError("Refusing to overwrite an existing backup")
    with closing(_read_only_connection(database_path)) as source:
        rows = _application_rows(source)
        _validate_source(rows)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_reserved = False
        try:
            descriptor = os.open(backup_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            backup_reserved = True
            os.close(descriptor)
            with closing(sqlite3.connect(backup_path)) as backup:
                with backup:
                    source.backup(backup)
            _verify_backup(backup_path, rows)
        except Exception:
            if backup_reserved and backup_path.exists():
                backup_path.unlink()
            raise


def _create_tenant_tables(connection: sqlite3.Connection) -> None:
    statements = (
        """CREATE TABLE organizations (
            id TEXT NOT NULL PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""",

        """CREATE TABLE organization_memberships (
            organization_id TEXT NOT NULL,
            supabase_user_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('owner', 'admin', 'editor', 'viewer')),
            created_at TEXT NOT NULL,
            PRIMARY KEY (organization_id, supabase_user_id),
            FOREIGN KEY (organization_id)
                REFERENCES organizations(id) ON DELETE RESTRICT
        )""",

        """CREATE INDEX organization_memberships_by_user
            ON organization_memberships(supabase_user_id)""",

        """CREATE TABLE applications_new (
            id TEXT NOT NULL PRIMARY KEY,
            organization_id TEXT NOT NULL,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            category TEXT NOT NULL,
            cost INTEGER NOT NULL,
            licenses INTEGER NOT NULL,
            active INTEGER NOT NULL,
            risk TEXT NOT NULL,
            renewal TEXT NOT NULL,
            annual INTEGER NOT NULL,
            renewal_reviewed INTEGER NOT NULL DEFAULT 0
                CHECK (renewal_reviewed IN (0, 1)),
            FOREIGN KEY (organization_id)
                REFERENCES organizations(id) ON DELETE RESTRICT,
            UNIQUE (organization_id, normalized_name)
        )""",

        """CREATE INDEX applications_new_by_organization
            ON applications_new(organization_id)""",

        """CREATE TABLE application_metadata (
            key TEXT NOT NULL PRIMARY KEY,
            value TEXT NOT NULL
        )""",

        """CREATE TABLE schema_migrations (
            version TEXT NOT NULL PRIMARY KEY,
            applied_at TEXT NOT NULL
        )""",
    )
    for statement in statements:
        connection.execute(statement)


def _validate_candidate(
    connection: sqlite3.Connection,
    source_rows: list[dict[str, Any]],
    owner_id: str,
) -> None:
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    if tables != {
        "organizations",
        "organization_memberships",
        "applications",
        "application_metadata",
        "schema_migrations",
    }:
        raise MigrationError("Candidate database schema is incomplete or unexpected")

    required_columns = {
        "organizations": {"id", "name", "created_at"},
        "organization_memberships": {
            "organization_id",
            "supabase_user_id",
            "role",
            "created_at",
        },
        "application_metadata": {"key", "value"},
        "schema_migrations": {"version", "applied_at"},
    }
    for table, expected_columns in required_columns.items():
        actual_columns = {
            row[1] for row in connection.execute(f"PRAGMA table_info({table})")
        }
        if not expected_columns <= actual_columns:
            raise MigrationError(f"Candidate {table} schema is incomplete")

    organizations = connection.execute(
        "SELECT id, name FROM organizations"
    ).fetchall()
    if organizations != [(LEGACY_ORGANIZATION_ID, LEGACY_ORGANIZATION_NAME)]:
        raise MigrationError("Candidate organization state is invalid")
    memberships = connection.execute(
        """
        SELECT organization_id, supabase_user_id, role
        FROM organization_memberships
        """
    ).fetchall()
    if memberships != [(LEGACY_ORGANIZATION_ID, owner_id, "owner")]:
        raise MigrationError("Candidate owner membership state is invalid")

    membership_foreign_keys = {
        (row[2], row[3], row[4])
        for row in connection.execute(
            "PRAGMA foreign_key_list(organization_memberships)"
        )
    }
    application_foreign_keys = {
        (row[2], row[3], row[4])
        for row in connection.execute("PRAGMA foreign_key_list(applications)")
    }
    if ("organizations", "organization_id", "id") not in membership_foreign_keys:
        raise MigrationError("Candidate membership foreign key is missing")
    if ("organizations", "organization_id", "id") not in application_foreign_keys:
        raise MigrationError("Candidate application foreign key is missing")

    application_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(applications)")
    }
    if not {
        "id",
        "organization_id",
        "normalized_name",
        *APPLICATION_FIELDS,
    } <= application_columns:
        raise MigrationError("Candidate application schema is incomplete")

    target_rows = connection.execute(
        """
        SELECT id, organization_id, normalized_name, name, category, cost, licenses,
               active, risk, renewal, annual, renewal_reviewed
        FROM applications
        ORDER BY rowid
        """,
    ).fetchall()
    if connection.execute("SELECT COUNT(*) FROM applications").fetchone()[0] != 8:
        raise MigrationError("Migrated application count is not exactly 8")
    if connection.execute(
        "SELECT COUNT(*) FROM applications WHERE organization_id != ?",
        (LEGACY_ORGANIZATION_ID,),
    ).fetchone()[0]:
        raise MigrationError("A legacy application was assigned to another organization")

    persisted_rows = connection.execute(
        """
        SELECT name, category, cost, licenses, active, risk, renewal, annual,
               renewal_reviewed
        FROM applications
        ORDER BY rowid
        """
    ).fetchall()
    expected_rows = [
        tuple(row[field] for field in APPLICATION_FIELDS) for row in source_rows
    ]
    if persisted_rows != expected_rows:
        raise MigrationError("Candidate application values do not match the source")

    identifiers = set()
    for row, expected in zip(target_rows, source_rows):
        application_id, organization_id, normalized_name, *values = row
        try:
            uuid.UUID(application_id)
        except (ValueError, AttributeError) as error:
            raise MigrationError("Candidate application ID is invalid") from error
        if application_id in identifiers:
            raise MigrationError("Candidate application IDs are not unique")
        identifiers.add(application_id)
        if organization_id != LEGACY_ORGANIZATION_ID:
            raise MigrationError("Candidate application organization is invalid")
        if normalized_name != normalize_application_name(expected["name"]):
            raise MigrationError("Candidate normalized application name is invalid")
        if tuple(values) != tuple(expected[field] for field in APPLICATION_FIELDS):
            raise MigrationError("Candidate application values do not match the source")

    migration_rows = connection.execute(
        "SELECT version FROM schema_migrations"
    ).fetchall()
    if migration_rows != [(MIGRATION_VERSION,)]:
        raise MigrationError("Candidate migration metadata is invalid")
    metadata_rows = connection.execute(
        "SELECT key, value FROM application_metadata"
    ).fetchall()
    if metadata_rows != [("legacy_organization_id", LEGACY_ORGANIZATION_ID)]:
        raise MigrationError("Candidate application metadata is invalid")
    unique_indexes = connection.execute("PRAGMA index_list(applications)").fetchall()
    if not any(
        row[2]
        and tuple(
            column[2]
            for column in connection.execute(
                f"PRAGMA index_info('{row[1]}')"
            ).fetchall()
        )
        == ("organization_id", "normalized_name")
        for row in unique_indexes
    ):
        raise MigrationError("Candidate organization/name uniqueness is missing")
    if connection.execute("PRAGMA foreign_key_check").fetchall():
        raise MigrationError("Foreign-key validation failed")
    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise MigrationError("SQLite integrity validation failed")


def _copy_backup_to_candidate(
    backup_path: Path,
    candidate_path: Path,
    source_rows: list[dict[str, Any]],
    owner_id: str,
) -> None:
    with closing(_read_only_connection(backup_path)) as backup:
        with closing(sqlite3.connect(candidate_path)) as candidate:
            backup.backup(candidate)

    connection = sqlite3.connect(candidate_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("BEGIN IMMEDIATE")
        _create_tenant_tables(connection)
        now = datetime.now(timezone.utc).isoformat()
        connection.execute(
            "INSERT INTO organizations (id, name, created_at) VALUES (?, ?, ?)",
            (LEGACY_ORGANIZATION_ID, LEGACY_ORGANIZATION_NAME, now),
        )
        connection.execute(
            """
            INSERT INTO organization_memberships
                (organization_id, supabase_user_id, role, created_at)
            VALUES (?, ?, 'owner', ?)
            """,
            (LEGACY_ORGANIZATION_ID, owner_id, now),
        )
        for row in source_rows:
            connection.execute(
                """
                INSERT INTO applications_new
                    (id, organization_id, name, normalized_name, category, cost,
                     licenses, active, risk, renewal, annual, renewal_reviewed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    LEGACY_ORGANIZATION_ID,
                    row["name"],
                    normalize_application_name(row["name"]),
                    row["category"],
                    row["cost"],
                    row["licenses"],
                    row["active"],
                    row["risk"],
                    row["renewal"],
                    row["annual"],
                    row["renewal_reviewed"],
                ),
            )
        if connection.execute(
            "SELECT COUNT(*) FROM applications_new"
        ).fetchone()[0] != 8:
            raise MigrationError("Candidate application count is not exactly 8")
        connection.execute("DROP TABLE applications")
        connection.execute("ALTER TABLE applications_new RENAME TO applications")
        connection.execute(
            "CREATE INDEX applications_by_organization ON applications(organization_id)"
        )
        connection.execute(
            "INSERT INTO application_metadata (key, value) VALUES ('legacy_organization_id', ?)",
            (LEGACY_ORGANIZATION_ID,),
        )
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (MIGRATION_VERSION, now),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    with closing(_read_only_connection(candidate_path)) as candidate:
        _validate_candidate(candidate, source_rows, owner_id)


def _remove_database_files(database_path: Path) -> None:
    for suffix in ("", "-journal", "-wal", "-shm"):
        path = Path(f"{database_path}{suffix}")
        if path.exists():
            path.unlink()


def prepare_migration_candidate(
    database_path: str | Path,
    candidate_path: str | Path | None = None,
    backup_path: str | Path | None = None,
) -> Path:
    """Build and validate a separate candidate without changing the source database."""
    database = Path(database_path).resolve()
    owner_id = os.getenv("SAASSPEND_LEGACY_OWNER_USER_ID", "")
    try:
        owner_id = str(uuid.UUID(owner_id))
    except (ValueError, AttributeError) as error:
        raise MigrationError(
            "SAASSPEND_LEGACY_OWNER_USER_ID must contain the explicitly approved Supabase user UUID"
        ) from error
    if not database.is_file():
        raise MigrationError("The target database does not exist")
    backup = (
        Path(backup_path).resolve()
        if backup_path is not None
        else Path(f"{database}.stage2.1.bak")
    )
    candidate = (
        Path(candidate_path).resolve()
        if candidate_path is not None
        else Path(f"{database}.stage2.1.candidate")
    )
    if len({database, backup, candidate}) != 3:
        raise MigrationError("Database, backup, and candidate paths must be different")
    if candidate.exists():
        raise MigrationError("Refusing to overwrite an existing migration candidate")

    with closing(_read_only_connection(database)) as source:
        source_rows = _application_rows(source)
        _validate_source(source_rows)
        tables = {
            row[0]
            for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        if tables != {"applications"}:
            raise MigrationError("The source database has unexpected tables or is already migrated")
        additional_objects = source.execute(
            """
            SELECT COUNT(*) FROM sqlite_master
            WHERE (type IN ('view', 'trigger'))
               OR (type = 'index' AND name NOT LIKE 'sqlite_%')
            """
        ).fetchone()[0]
        if additional_objects:
            raise MigrationError("The source database has unexpected views, triggers, or indexes")

    create_verified_backup(database, backup)
    _verify_backup(backup, source_rows)
    candidate.parent.mkdir(parents=True, exist_ok=True)
    staging = candidate.with_name(f".{candidate.name}.{uuid.uuid4().hex}.tmp")
    reserved_candidate = False
    published = False
    try:
        _copy_backup_to_candidate(backup, staging, source_rows, owner_id)
        _verify_backup(backup, source_rows)
        for suffix in ("-journal", "-wal", "-shm"):
            if Path(f"{staging}{suffix}").exists():
                raise MigrationError("Candidate has unexpected SQLite sidecar files")

        descriptor = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        reserved_candidate = True
        os.close(descriptor)
        os.replace(staging, candidate)
        published = True
    except Exception:
        if reserved_candidate and candidate.exists():
            candidate.unlink()
        raise
    finally:
        if not published:
            _remove_database_files(staging)

    return candidate


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build and validate a tenant-schema candidate without replacing the source database."
    )
    parser.add_argument("--database", required=True, help="Explicit path to the source database")
    parser.add_argument("--backup", help="Backup path; defaults to <database>.stage2.1.bak")
    parser.add_argument(
        "--candidate",
        help="Candidate path; defaults to <database>.stage2.1.candidate",
    )
    args = parser.parse_args()
    candidate = prepare_migration_candidate(
        args.database,
        candidate_path=args.candidate,
        backup_path=args.backup,
    )
    print(f"Validated migration candidate created at: {candidate}")
    print("The source database was not replaced; production cutover was not performed.")


if __name__ == "__main__":
    main()

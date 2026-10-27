import sqlite3
import tempfile
import unittest
import uuid
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from data import _APPS
from tenant_migration import (
    LEGACY_ORGANIZATION_ID,
    LEGACY_ORGANIZATION_NAME,
    MigrationError,
    _validate_candidate,
    prepare_migration_candidate,
    normalize_application_name,
)

APPROVED_OWNER_ID = "72f62a26-0d1c-4e6c-a91b-8349bf1b6a40"


def create_source_database(path: Path, count: int = 8) -> list[tuple]:
    records = [
        (*app, index % 2)
        for index, app in enumerate(_APPS[:count])
    ]
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            """
            CREATE TABLE applications (
                name TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                cost INTEGER NOT NULL,
                licenses INTEGER NOT NULL,
                active INTEGER NOT NULL,
                risk TEXT NOT NULL,
                renewal TEXT NOT NULL,
                annual INTEGER NOT NULL,
                renewal_reviewed INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO applications
                (name, category, cost, licenses, active, risk, renewal, annual, renewal_reviewed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )
        connection.commit()
    return records


class TenantMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "legacy.sqlite3"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_candidate_preserves_all_fields_and_leaves_source_untouched(self):
        source_records = create_source_database(self.database_path)
        source_bytes = self.database_path.read_bytes()
        with patch.dict(
            "os.environ",
            {"SAASSPEND_LEGACY_OWNER_USER_ID": APPROVED_OWNER_ID},
        ):
            candidate_path = prepare_migration_candidate(self.database_path)

        backup_path = Path(f"{self.database_path}.stage2.1.bak")
        self.assertTrue(backup_path.is_file())
        self.assertTrue(candidate_path.is_file())
        self.assertEqual(self.database_path.read_bytes(), source_bytes)
        with closing(sqlite3.connect(candidate_path)) as migrated:
            applications = migrated.execute(
                """
                SELECT name, category, cost, licenses, active, risk, renewal, annual,
                       renewal_reviewed
                FROM applications WHERE organization_id = ?
                ORDER BY rowid
                """,
                (LEGACY_ORGANIZATION_ID,),
            ).fetchall()
            organizations = migrated.execute(
                "SELECT id, name FROM organizations"
            ).fetchall()
            memberships = migrated.execute(
                """
                SELECT organization_id, supabase_user_id, role
                FROM organization_memberships
                """
            ).fetchall()
            identity = migrated.execute(
                "SELECT COUNT(DISTINCT id) FROM applications"
            ).fetchone()[0]
            integrity = migrated.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_key_issues = migrated.execute("PRAGMA foreign_key_check").fetchall()

        self.assertEqual(applications, source_records)
        self.assertEqual(organizations, [(LEGACY_ORGANIZATION_ID, LEGACY_ORGANIZATION_NAME)])
        self.assertEqual(
            memberships,
            [(LEGACY_ORGANIZATION_ID, APPROVED_OWNER_ID, "owner")],
        )
        self.assertEqual(identity, 8)
        self.assertEqual(integrity, "ok")
        self.assertEqual(foreign_key_issues, [])

        with closing(sqlite3.connect(backup_path)) as backup:
            self.assertEqual(
                backup.execute("SELECT COUNT(*) FROM applications").fetchone()[0],
                8,
            )
        with closing(sqlite3.connect(self.database_path)) as original:
            self.assertEqual(
                {
                    row[0]
                    for row in original.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table' "
                        "AND name NOT LIKE 'sqlite_%'"
                    )
                },
                {"applications"},
            )

    def test_missing_or_invalid_explicit_owner_fails_before_backup_or_mutation(self):
        create_source_database(self.database_path)
        before = self.database_path.read_bytes()
        backup_path = Path(f"{self.database_path}.stage2.1.bak")

        for owner in (None, "not-a-uuid"):
            with self.subTest(owner_is_configured=owner is not None):
                with patch.dict("os.environ", {"SAASSPEND_LEGACY_OWNER_USER_ID": ""}):
                    with self.assertRaises(MigrationError):
                        if owner is not None:
                            with patch.dict(
                                "os.environ",
                                {"SAASSPEND_LEGACY_OWNER_USER_ID": owner},
                            ):
                                prepare_migration_candidate(self.database_path)
                        else:
                            prepare_migration_candidate(self.database_path)
                self.assertEqual(self.database_path.read_bytes(), before)
                self.assertFalse(backup_path.exists())

    def test_unexpected_record_count_aborts_without_changing_source(self):
        create_source_database(self.database_path, count=7)
        before = self.database_path.read_bytes()

        with self.assertRaisesRegex(MigrationError, "exactly 8"):
            with patch.dict(
                "os.environ",
                {"SAASSPEND_LEGACY_OWNER_USER_ID": APPROVED_OWNER_ID},
            ):
                prepare_migration_candidate(self.database_path)

        self.assertEqual(self.database_path.read_bytes(), before)
        self.assertFalse(Path(f"{self.database_path}.stage2.1.bak").exists())

    def test_unexpected_application_column_rejects_candidate_without_changing_source(self):
        create_source_database(self.database_path)
        with closing(sqlite3.connect(self.database_path)) as source:
            source.execute("ALTER TABLE applications ADD COLUMN legacy_notes TEXT")
            source.execute(
                "UPDATE applications SET legacy_notes = 'preserve me' WHERE name = 'Slack'"
            )
            source.commit()
        before = self.database_path.read_bytes()
        backup_path = Path(f"{self.database_path}.stage2.1.bak")
        candidate_path = Path(f"{self.database_path}.stage2.1.candidate")

        with patch.dict(
            "os.environ",
            {"SAASSPEND_LEGACY_OWNER_USER_ID": APPROVED_OWNER_ID},
        ):
            with self.assertRaisesRegex(MigrationError, "unexpected columns: legacy_notes"):
                prepare_migration_candidate(self.database_path)

        self.assertEqual(self.database_path.read_bytes(), before)
        self.assertFalse(backup_path.exists())
        self.assertFalse(candidate_path.exists())
        with closing(sqlite3.connect(self.database_path)) as source:
            self.assertEqual(
                source.execute(
                    "SELECT legacy_notes FROM applications WHERE name = 'Slack'"
                ).fetchone(),
                ("preserve me",),
            )

    def test_application_name_normalization_handles_unicode_and_whitespace(self):
        self.assertEqual(normalize_application_name("  Straße  "), "strasse")
        self.assertEqual(normalize_application_name("ＳＡＡＳ"), "saas")

    def test_candidate_transaction_failure_leaves_source_and_retains_backup(self):
        create_source_database(self.database_path)
        source_bytes = self.database_path.read_bytes()
        repeated_id = uuid.UUID("11111111-1111-4111-8111-111111111111")

        with patch("tenant_migration.uuid.uuid4", return_value=repeated_id):
            with self.assertRaises(sqlite3.IntegrityError):
                with patch.dict(
                    "os.environ",
                    {"SAASSPEND_LEGACY_OWNER_USER_ID": APPROVED_OWNER_ID},
                ):
                    prepare_migration_candidate(self.database_path)

        with closing(sqlite3.connect(self.database_path)) as original:
            table_names = {
                row[0]
                for row in original.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' "
                    "AND name NOT LIKE 'sqlite_%'"
                )
            }
            rows = original.execute(
                """
                SELECT name, category, cost, licenses, active, risk, renewal, annual,
                       renewal_reviewed
                FROM applications ORDER BY rowid
                """
            ).fetchall()
            integrity = original.execute("PRAGMA integrity_check").fetchone()[0]

        backup_path = Path(f"{self.database_path}.stage2.1.bak")
        self.assertTrue(backup_path.is_file())
        self.assertEqual(self.database_path.read_bytes(), source_bytes)
        self.assertEqual(table_names, {"applications"})
        self.assertEqual(rows, [(*app, index % 2) for index, app in enumerate(_APPS)])
        self.assertEqual(integrity, "ok")
        self.assertFalse(Path(f"{self.database_path}.stage2.1.candidate").exists())
        with closing(sqlite3.connect(backup_path)) as backup:
            self.assertEqual(
                backup.execute("PRAGMA integrity_check").fetchone()[0],
                "ok",
            )

    def test_candidate_creation_failure_leaves_source_untouched(self):
        create_source_database(self.database_path)
        source_bytes = self.database_path.read_bytes()
        with patch(
            "tenant_migration._copy_backup_to_candidate",
            side_effect=OSError("simulated candidate creation failure"),
        ):
            with patch.dict(
                "os.environ",
                {"SAASSPEND_LEGACY_OWNER_USER_ID": APPROVED_OWNER_ID},
            ):
                with self.assertRaisesRegex(OSError, "candidate creation"):
                    prepare_migration_candidate(self.database_path)

        self.assertEqual(self.database_path.read_bytes(), source_bytes)
        self.assertFalse(Path(f"{self.database_path}.stage2.1.candidate").exists())
        self.assertTrue(Path(f"{self.database_path}.stage2.1.bak").exists())

    def test_candidate_preparation_preserves_source_with_open_wal_connection(self):
        create_source_database(self.database_path)
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA wal_autocheckpoint = 0")
            connection.execute(
                "UPDATE applications SET renewal_reviewed = 1 WHERE name = 'Slack'"
            )
            connection.commit()
            source_records = connection.execute(
                """
                SELECT name, category, cost, licenses, active, risk, renewal, annual,
                       renewal_reviewed
                FROM applications ORDER BY rowid
                """
            ).fetchall()
            wal_path = Path(f"{self.database_path}-wal")
            self.assertTrue(wal_path.exists())

            with patch.dict(
                "os.environ",
                {"SAASSPEND_LEGACY_OWNER_USER_ID": APPROVED_OWNER_ID},
            ):
                candidate_path = prepare_migration_candidate(self.database_path)

            self.assertTrue(wal_path.exists())
            self.assertEqual(
                connection.execute(
                    """
                    SELECT name, category, cost, licenses, active, risk, renewal, annual,
                           renewal_reviewed
                    FROM applications ORDER BY rowid
                    """
                ).fetchall(),
                source_records,
            )
            with closing(sqlite3.connect(candidate_path)) as candidate:
                self.assertEqual(
                    candidate.execute(
                        """
                        SELECT name, category, cost, licenses, active, risk, renewal,
                               annual, renewal_reviewed
                        FROM applications WHERE organization_id = ?
                        ORDER BY rowid
                        """,
                        (LEGACY_ORGANIZATION_ID,),
                    ).fetchall(),
                    source_records,
                )
        finally:
            connection.close()

    def test_candidate_validation_failure_leaves_source_untouched(self):
        create_source_database(self.database_path)
        source_bytes = self.database_path.read_bytes()
        with patch(
            "tenant_migration._validate_candidate",
            side_effect=MigrationError("simulated candidate validation failure"),
        ):
            with patch.dict(
                "os.environ",
                {"SAASSPEND_LEGACY_OWNER_USER_ID": APPROVED_OWNER_ID},
            ):
                with self.assertRaisesRegex(MigrationError, "validation failure"):
                    prepare_migration_candidate(self.database_path)

        self.assertEqual(self.database_path.read_bytes(), source_bytes)
        self.assertFalse(Path(f"{self.database_path}.stage2.1.candidate").exists())

    def test_corrupted_candidate_record_is_rejected_without_changing_source(self):
        create_source_database(self.database_path)
        source_bytes = self.database_path.read_bytes()

        def corrupt_candidate_then_validate(connection, source_rows, owner_id):
            candidate_path = Path(
                connection.execute("PRAGMA database_list").fetchone()[2]
            )
            with closing(sqlite3.connect(candidate_path)) as candidate:
                candidate.execute(
                    """
                    UPDATE applications
                    SET normalized_name = 'tampered-name'
                    WHERE name = 'Slack'
                    """
                )
                candidate.commit()
            return _validate_candidate(connection, source_rows, owner_id)

        with patch(
            "tenant_migration._validate_candidate",
            side_effect=corrupt_candidate_then_validate,
        ):
            with patch.dict(
                "os.environ",
                {"SAASSPEND_LEGACY_OWNER_USER_ID": APPROVED_OWNER_ID},
            ):
                with self.assertRaisesRegex(MigrationError, "normalized application name"):
                    prepare_migration_candidate(self.database_path)

        self.assertEqual(self.database_path.read_bytes(), source_bytes)
        self.assertFalse(Path(f"{self.database_path}.stage2.1.candidate").exists())
        self.assertTrue(Path(f"{self.database_path}.stage2.1.bak").exists())

    def test_backup_verification_failure_leaves_source_untouched(self):
        create_source_database(self.database_path)
        source_bytes = self.database_path.read_bytes()
        with patch(
            "tenant_migration._verify_backup",
            side_effect=MigrationError("simulated backup verification failure"),
        ):
            with patch.dict(
                "os.environ",
                {"SAASSPEND_LEGACY_OWNER_USER_ID": APPROVED_OWNER_ID},
            ):
                with self.assertRaisesRegex(MigrationError, "backup verification"):
                    prepare_migration_candidate(self.database_path)

        self.assertEqual(self.database_path.read_bytes(), source_bytes)
        self.assertFalse(Path(f"{self.database_path}.stage2.1.candidate").exists())
        self.assertFalse(Path(f"{self.database_path}.stage2.1.bak").exists())

    def test_existing_backup_is_never_overwritten(self):
        create_source_database(self.database_path)
        source_bytes = self.database_path.read_bytes()
        backup_path = Path(f"{self.database_path}.stage2.1.bak")
        original_backup = b"pre-existing backup artifact"
        backup_path.write_bytes(original_backup)

        with patch.dict(
            "os.environ",
            {"SAASSPEND_LEGACY_OWNER_USER_ID": APPROVED_OWNER_ID},
        ):
            with self.assertRaisesRegex(MigrationError, "Refusing to overwrite"):
                prepare_migration_candidate(self.database_path)

        self.assertEqual(self.database_path.read_bytes(), source_bytes)
        self.assertEqual(backup_path.read_bytes(), original_backup)
        self.assertFalse(Path(f"{self.database_path}.stage2.1.candidate").exists())

    def test_candidate_publication_replacement_failure_leaves_source_untouched(self):
        create_source_database(self.database_path)
        source_bytes = self.database_path.read_bytes()
        with patch(
            "tenant_migration.os.replace",
            side_effect=OSError("simulated candidate publication failure"),
        ):
            with patch.dict(
                "os.environ",
                {"SAASSPEND_LEGACY_OWNER_USER_ID": APPROVED_OWNER_ID},
            ):
                with self.assertRaisesRegex(OSError, "publication failure"):
                    prepare_migration_candidate(self.database_path)

        self.assertEqual(self.database_path.read_bytes(), source_bytes)
        self.assertFalse(Path(f"{self.database_path}.stage2.1.candidate").exists())
        self.assertTrue(Path(f"{self.database_path}.stage2.1.bak").exists())
        self.assertEqual(
            list(self.database_path.parent.glob(".*.tmp")),
            [],
        )


if __name__ == "__main__":
    unittest.main()

"""Fresh process imports must work without migration/test import side effects."""

import subprocess
import sys


def test_domain_models_register_all_foreign_key_targets_in_fresh_process():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import counterparty.models; from counterparty.database import Base; "
            "assert 'organizations' in Base.metadata.tables; list(Base.metadata.sorted_tables)",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr

"""Narrow migration checks in a sanitized copy, never against installed data."""
import json
import os
from pathlib import Path
import module1_check as checks

PYTHON = '/private/tmp/fieldwork-module6/venv/bin/python'


def main():
    url = os.environ.get('FIELDWORK_DISPOSABLE_POSTGRES_URL')
    tools = os.environ.get('FIELDWORK_TEST_PG_TOOLS')
    if not url or not tools:
        raise SystemExit('Explicit disposable PG17 URL and tools required')
    checks.OUT = checks.ROOT / 'docs/package6a'
    checks.OUT.mkdir(exist_ok=True)
    root, env = checks.isolated()
    env.update(HOME=str(root / 'home'), TEST_POSTGRES_URL=url,
               FIELDWORK_TEST_PG_TOOLS=tools,
               FIELDWORK_RELEASE_MIGRATION_REPORT=str(checks.OUT / 'migration-rehearsal.json'))
    Path(env['HOME']).mkdir()
    results = {}
    suites = [
        ('migration-suite', ['-m', 'pytest', '-q', '-ra', 'tests/test_migration_v2.py',
                             'tests/test_migration_v6.py', 'tests/test_release_migration.py',
                             'tests/test_postgres_security.py',
                             'tests/test_runtime.py::test_sqlite005_additive_migration_and_backup_restore',
                             'tests/test_release.py::test_migration_failure_transaction_and_duplicate_invocation']),
        ('backend-regressions', ['-m', 'pytest', '-q', '-ra']),
        ('ruff', ['-m', 'ruff', 'check', 'app', 'scripts', 'tests']),
    ]
    for name, args in suites:
        results[name] = checks.run(name, [PYTHON, *args], root / 'backend', env)
        if results[name]['exit_code']:
            break
    (checks.OUT / 'checks.json').write_text(json.dumps(results, indent=2) + '\n')
    if any(r['exit_code'] for r in results.values()):
        raise SystemExit('A migration/regression check failed; inspect private-fixture logs')


if __name__ == '__main__':
    main()

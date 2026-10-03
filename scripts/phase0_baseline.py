"""Audit isolated copies. Never load live env files, databases, or sending workers."""
import concurrent.futures
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
LIVE = Path.home() / '.local/share/fieldwork'
OUT = ROOT / 'docs/baseline'
PYTHON = LIVE / '.venv/bin/python'
SKIP = {'.git', '.venv', 'node_modules', '.next', '__pycache__', '.pytest_cache', 'data', 'logs'}

def ignore(_, names):
    return [n for n in names if n in SKIP or n.startswith('.env') or n.endswith(('.db', '.sqlite', '.sqlite3', '.lock', '.tsbuildinfo', '.egg-info')) or '.db-' in n or '.sqlite-' in n]

def environment(folder):
    env = dict(os.environ)
    for key in list(env):
        if any(s in key for s in ('API_KEY', 'TOKEN', 'PASSWORD', 'OAUTH', 'DATABASE_URL', 'TEST_POSTGRES_URL', 'LIVE_BATCH')):
            env.pop(key, None)
    env.update(DATABASE_URL='sqlite:///' + str(folder / 'baseline.sqlite'), ENVIRONMENT='development',
               DRY_RUN='true', MANUAL_MODE='true', RESPONSE_POLL_ENABLED='false', AUTO_APPROVE='false',
               API_KEY='local-development-key-change-me', SSL_CERT_FILE='/etc/ssl/cert.pem',
               HOME=str(folder / 'home'), SENDER_EMAIL='', OAUTH_CLIENT_ID='', OAUTH_CLIENT_SECRET='',
               OAUTH_REFRESH_TOKEN='', OPENAI_API_KEY='', TAVILY_API_KEY='', FIRECRAWL_API_KEY='',
               GOOGLE_MAPS_API_KEY='', APOLLO_API_KEY='', HUNTER_API_KEY='', CI='true')
    return env

def command(label, args, cwd, env, timeout=180):
    start = time.monotonic()
    try:
        result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
        output = result.stdout + result.stderr
        code = result.returncode
    except subprocess.TimeoutExpired as exc:
        output = str(exc)
        code = 124
    (OUT / (label + '.log')).write_text(output)
    record = {'command': args, 'cwd': str(cwd), 'exit_code': code, 'seconds': round(time.monotonic()-start, 2), 'log': label + '.log'}
    print(json.dumps({'check': label, **record}), flush=True)
    return record

def backend(name, snapshot, env):
    checks = {}
    folder = snapshot / 'backend'
    checks['dependency_check'] = command(name+'-pip-check', [str(PYTHON), '-m', 'pip', 'check'], folder, env)
    checks['install_resolution'] = command(name+'-install-resolution', [str(PYTHON), '-m', 'pip', 'install', '--dry-run', '--no-index', '-r', 'requirements.lock.txt'], folder, env)
    checks['tests'] = command(name+'-pytest', [str(PYTHON), '-m', 'pytest', '-q', '-ra'], folder, env)
    checks['migration'] = command(name+'-migration', [str(PYTHON), '-m', 'alembic', 'upgrade', 'head'], folder, env)
    checks['python_compile'] = command(name+'-compile', [str(PYTHON), '-m', 'compileall', '-q', 'app', 'scripts'], folder, env)
    return checks

def frontend(name, snapshot, env):
    folder = snapshot / 'frontend'
    checks = {}
    checks['install'] = command(name+'-npm-ci', ['npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund'], folder, env, 240)
    checks['lint'] = command(name+'-lint', ['npm', 'run', 'lint'], folder, env)
    checks['typecheck'] = command(name+'-typecheck', ['npm', 'run', 'typecheck'], folder, env)
    checks['build'] = command(name+'-build', ['npm', 'run', 'build'], folder, env, 240)
    checks['dependency_audit'] = command(name+'-npm-audit', ['npm', 'audit', '--omit=dev', '--json'], folder, env, 60)
    return checks

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='fieldwork-phase0-'))
    results = {'date': '2026-10-03', 'temporary_root': str(temp), 'safety': 'No live env/database copied; response polling off; fake HOME; no sending worker started.'}
    futures = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for name, source in [('workspace', ROOT), ('runtime', LIVE)]:
            snapshot = temp / name
            snapshot.mkdir()
            for part in ('backend', 'frontend'):
                shutil.copytree(source / part, snapshot / part, ignore=ignore)
            env = environment(snapshot)
            for domain, fn in [('backend', backend), ('frontend', frontend)]:
                futures[pool.submit(fn, name, snapshot, env)] = (name, domain)
        for future in concurrent.futures.as_completed(futures):
            name, domain = futures[future]
            results.setdefault(name, {})[domain] = future.result()
            (OUT / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print('Baseline complete. Isolated snapshots retained at ' + str(temp), flush=True)

if __name__ == '__main__':
    main()

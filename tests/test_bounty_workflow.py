"""Behavioural tests of the state scripts (against LOCAL bare git remotes), the workflow structure and Windows import isolation.
These run bash and git; they are skipped where those are missing. They do not talk to GitHub - the GitHub Actions run itself is NOT covered here."""
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BASH = shutil.which("bash")
GIT = shutil.which("git")
pytestmark = pytest.mark.skipif(not (BASH and GIT), reason="needs bash and git")
ENV_BASE = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}


def sh(cmd, cwd, env=None, check=False):
    e = dict(ENV_BASE)
    e.update(env or {})
    r = subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True, shell=isinstance(cmd, str))
    if check and r.returncode:
        raise AssertionError(f"{cmd}\n{r.stdout}\n{r.stderr}")
    return r


def git(cwd, *a, check=True, env=None):
    return sh(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false", *a], cwd, env, check)


@pytest.fixture
def repo(tmp_path):
    bare = tmp_path / "remote.git"
    sh(["git", "init", "-q", "--bare", str(bare)], tmp_path, check=True)
    work = tmp_path / "work"
    work.mkdir()
    sh(["git", "init", "-q", "-b", "main"], work, check=True)
    (work / "README").write_text("x")
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "init")
    git(work, "remote", "add", "origin", str(bare))
    git(work, "push", "-q", "origin", "main")
    (work / "scripts").mkdir()
    for n in ("state_restore.sh", "state_save.sh"):
        shutil.copy(ROOT / "scripts" / n, work / "scripts" / n)
    return work, bare


def mkstate(d: Path, text="v1"):
    d.mkdir(parents=True, exist_ok=True)
    (d / "bounty.sqlite3").write_text(text)
    (d / "note.txt").write_text(text)


def remote_head(bare, branch="flyfoundry-state"):
    r = sh(["git", "--git-dir", str(bare), "rev-parse", "--verify", "-q", f"refs/heads/{branch}"], bare)
    return r.stdout.strip() if r.returncode == 0 else None


def restore(work, d="state", env=None):
    return sh(["bash", "scripts/state_restore.sh", "origin", d], work, env)


def save(work, d="state", env=None):
    return sh(["bash", "scripts/state_save.sh", "origin", d, "msg"], work, env)


def test_restore_when_branch_absent_is_empty_and_marks_none(repo):
    work, bare = repo
    r = restore(work)
    assert r.returncode == 0, r.stderr
    assert (work / "state").is_dir() and not any((work / "state").iterdir())
    assert (work / "state.base_sha").read_text().strip() == "none"


def test_roundtrip_save_then_restore(repo):
    work, bare = repo
    restore(work)
    mkstate(work / "state", "v1")
    r = save(work)
    assert r.returncode == 0, r.stderr
    head = remote_head(bare)
    assert head
    shutil.rmtree(work / "state")
    r = restore(work)
    assert r.returncode == 0, r.stderr
    assert (work / "state" / "note.txt").read_text() == "v1" and (work / "state.base_sha").read_text().strip() == head


def test_remote_unreachable_is_failure_not_empty_state(repo):
    work, bare = repo
    git(work, "remote", "set-url", "origin", str(bare) + "-missing")
    mkstate(work / "state", "precious")
    r = restore(work)
    assert r.returncode == 1
    assert (work / "state" / "note.txt").read_text() == "precious"                  # nothing overwritten, nothing guessed


def test_corrupt_archive_fails_and_does_not_publish(repo, tmp_path):
    work, bare = repo
    restore(work)
    mkstate(work / "state", "v1")
    assert save(work).returncode == 0
    head = remote_head(bare)
    fake = tmp_path / "fakebin"
    fake.mkdir()
    (fake / "tar").write_text("#!/bin/sh\nexit 2\n")
    (fake / "tar").chmod(0o755)
    shutil.rmtree(work / "state")
    r = restore(work, env={"PATH": f"{fake}{os.pathsep}{os.environ['PATH']}"})
    assert r.returncode == 1 and not (work / "state").exists()                        # no empty directory that could later be published
    assert remote_head(bare) == head


def test_verify_failure_on_restore_keeps_existing_dir_and_remote(repo):
    work, bare = repo
    restore(work)
    mkstate(work / "state", "v1")
    save(work)
    head = remote_head(bare)
    mkstate(work / "state", "local-newer")
    r = restore(work, env={"STATE_VERIFY": "exit 1"})
    assert r.returncode == 1 and (work / "state" / "note.txt").read_text() == "local-newer"
    assert remote_head(bare) == head


def test_save_refuses_when_verification_fails(repo):
    work, bare = repo
    restore(work)
    mkstate(work / "state", "bad")
    r = save(work, env={"STATE_VERIFY": "test -f \"$1/does-not-exist\""})
    assert r.returncode == 1 and remote_head(bare) is None


def test_save_requires_base_marker_when_asked(repo):
    work, bare = repo
    mkstate(work / "state", "x")
    r = save(work, env={"STATE_REQUIRE_BASE": "1"})
    assert r.returncode == 1 and remote_head(bare) is None


def test_lease_blocks_overwrite_of_concurrent_remote_change(repo, tmp_path):
    work, bare = repo
    restore(work)
    mkstate(work / "state", "mine")
    assert save(work).returncode == 0
    restore(work)                                                                      # base = head A
    mkstate(work / "state", "mine-2")
    # somebody else updates the remote state branch after our restore
    other = tmp_path / "other"
    sh(["git", "clone", "-q", str(bare), str(other)], tmp_path, check=True)
    git(other, "checkout", "-q", "-B", "flyfoundry-state", "origin/flyfoundry-state")
    (other / "note.txt").write_text("theirs")
    git(other, "commit", "-q", "-am", "theirs")
    git(other, "push", "-q", "origin", "flyfoundry-state")
    theirs = remote_head(bare)
    r = save(work, env={"STATE_REQUIRE_BASE": "1"})
    assert r.returncode == 1 and "nothing was overwritten" in r.stderr
    assert remote_head(bare) == theirs


def test_lease_for_absent_branch_blocks_when_someone_created_it(repo, tmp_path):
    work, bare = repo
    restore(work)                                                                      # base = none
    mkstate(work / "state", "mine")
    other = tmp_path / "other"
    sh(["git", "clone", "-q", str(bare), str(other)], tmp_path, check=True)
    git(other, "checkout", "-q", "--orphan", "flyfoundry-state")
    (other / "f").write_text("theirs")
    git(other, "add", "-A")
    git(other, "commit", "-q", "-m", "theirs")
    git(other, "push", "-q", "origin", "flyfoundry-state")
    theirs = remote_head(bare)
    r = save(work, env={"STATE_REQUIRE_BASE": "1"})
    assert r.returncode == 1 and remote_head(bare) == theirs


def test_separate_branch_names_do_not_collide(repo):
    work, bare = repo
    env = {"STATE_BRANCH": "flyfoundry-bounty-state"}
    restore(work, env=env)
    mkstate(work / "state", "b")
    assert save(work, env=env).returncode == 0
    assert remote_head(bare, "flyfoundry-bounty-state") and remote_head(bare) is None


# ---------- real state (sqlite) through the verify gate
def test_verify_state_command_is_usable_as_state_verify(repo, tmp_path):
    work, bare = repo
    from flyfoundry.bounty_factory.store import Store
    st = tmp_path / "gen"
    Store(st / "bounty.sqlite3").close()
    ok = sh([sys.executable, "-m", "flyfoundry", "bounty", "verify-state", "--state-dir", str(st)], ROOT)
    assert ok.returncode == 0, ok.stderr
    (st / "bounty.sqlite3").write_bytes(b"garbage" * 200)
    bad = sh([sys.executable, "-m", "flyfoundry", "bounty", "verify-state", "--state-dir", str(st)], ROOT)
    assert bad.returncode == 7


# ---------- workflow structure (static) + shell syntax of every run block
yaml = pytest.importorskip("yaml")
WF = yaml.safe_load((ROOT / ".github/workflows/bounty_discovery.yml").read_text(encoding="utf-8"))


def test_workflow_jobs_and_permissions():
    jobs = WF["jobs"]
    assert set(jobs) == {"discover", "persist"}
    assert WF["permissions"] == {"contents": "read"}
    assert jobs["discover"]["permissions"] == {"contents": "read"}
    assert jobs["persist"]["permissions"] == {"contents": "write"}
    assert jobs["persist"]["needs"] == "discover"
    steps_persist = json.dumps(jobs["persist"]["steps"])
    assert "state_save.sh" in steps_persist and "STATE_REQUIRE_BASE" in steps_persist
    assert "flyfoundry bounty run" not in steps_persist                              # persist never runs network/parsing code
    assert "state_save.sh" not in json.dumps(jobs["discover"]["steps"])              # the read-only job cannot publish


def test_workflow_does_not_claim_single_branch_permission():
    txt = (ROOT / ".github/workflows/bounty_discovery.yml").read_text(encoding="utf-8")
    assert "repository-wide" in txt
    assert not re.search(r"contents:\s*write[^\n]*(only|limited)[^\n]*branch", txt, re.I)


def test_workflow_tests_exist_and_state_branch_isolated():
    txt = (ROOT / ".github/workflows/bounty_discovery.yml").read_text(encoding="utf-8")
    for f in re.findall(r"tests/test_\w+\.py", txt):
        assert (ROOT / f).exists(), f
    assert WF["env"]["STATE_BRANCH"] == "flyfoundry-bounty-state"


def test_workflow_run_blocks_are_valid_bash():
    for jn, job in WF["jobs"].items():
        for st in job["steps"]:
            run = st.get("run")
            if not run:
                continue
            run = re.sub(r"\$\{\{.*?\}\}", "X", run)
            r = subprocess.run([BASH, "-n"], input=run, capture_output=True, text=True)
            assert r.returncode == 0, (jn, st.get("name"), r.stderr)


def test_workflow_failure_step_maps_exit_codes():
    discover = WF["jobs"]["discover"]["steps"]
    s = [x for x in discover if "Fail loudly" in x.get("name", "")][0]
    script = re.sub(r"\$\{\{\s*steps\.run\.outputs\.run_status\s*\}\}", "x", s["run"])
    for rc, exp in (("0", 0), ("3", 0), ("4", 4), ("5", 5), ("6", 6)):
        script_rc = script.replace('"${{ steps.run.outputs.rc }}"', f'"{rc}"')
        script_rc = re.sub(r'rc="\$\{\{.*?\}\}"', f'rc="{rc}"', script_rc)
        r = subprocess.run([BASH, "-c", script_rc], capture_output=True, text=True)
        assert r.returncode == exp, (rc, r.stdout, r.stderr)


# ---------- 4.4 Windows compatibility (simulated: no `resource`, no numpy)
SIM = textwrap.dedent("""
    import sys, importlib.abc
    sys.modules['resource'] = None            # import resource -> ImportError, as on Windows
    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path, target=None):
            if name.split('.')[0] in ('numpy', 'scipy', 'pandas'):
                raise ImportError('blocked: ' + name)
    sys.meta_path.insert(0, Block())
    sys.path.insert(0, %r)
    from flyfoundry.cli.entry import main
    sys.exit(main(%r))
""")


def run_sim(argv, cwd):
    return subprocess.run([sys.executable, "-c", SIM % (str(ROOT), argv)], cwd=cwd, capture_output=True, text=True)


def test_bounty_cli_works_without_resource_and_numpy(tmp_path):
    r = run_sim(["bounty", "--help"], ROOT)
    assert r.returncode == 0 and "Bounty Factory" in r.stdout, r.stderr
    from flyfoundry.bounty_factory.store import Store
    st = tmp_path / "st"
    Store(st / "bounty.sqlite3").close()
    r = run_sim(["bounty", "evaluate", "--state-dir", str(st), "--out", str(tmp_path / "out"), "--reviews", str(tmp_path / "r.json"),
                 "--manual", str(tmp_path / "m.json"), "--now", "2026-10-15T12:50:43Z"], ROOT)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "out" / "manifest.json").exists()


def test_research_cli_import_tolerates_missing_resource():
    code = "import sys; sys.modules['resource']=None; sys.path.insert(0, %r); import flyfoundry.research.experiment as e; print(e._rss_mb())" % str(ROOT)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parent


def test_branch_android_job_never_references_release_secrets():
    workflow = (REPOSITORY_ROOT / ".github/workflows/build-apk.yml").read_text(encoding="utf-8")
    debug_job = workflow.split("  build-apk-debug:", 1)[1].split(
        "  build-apk-release:", 1
    )[0]
    release_job = workflow.split("  build-apk-release:", 1)[1].split(
        "  build-windows:", 1
    )[0]
    assert "secrets." not in debug_job
    assert "environment:\n      name: android-release" in release_job
    assert "startsWith(github.ref, 'refs/tags/v')" in release_job
    assert "actions/cache" not in release_job


def test_github_actions_are_pinned_to_full_commits():
    workflow = (REPOSITORY_ROOT / ".github/workflows/build-apk.yml").read_text(encoding="utf-8")
    uses = re.findall(r"uses:\s+(actions/[^@\s]+)@([^\s]+)", workflow)
    assert uses
    assert all(re.fullmatch(r"[0-9a-f]{40}", revision) for _, revision in uses)


def test_windows_bundle_uses_optimized_bytecode_and_no_source_package():
    build = (ROOT / "scripts/build_windows.py").read_text(encoding="utf-8")
    packager = (ROOT / "scripts/create_package.py").read_text(encoding="utf-8")
    assert '"--optimize"' in build and '"2"' in build
    assert 'ROOT / "lankdea"' not in packager
    assert 'ROOT / "tests"' not in packager


def test_publisher_downloads_do_not_dirty_source_commit_check():
    import subprocess

    workflow = (REPOSITORY_ROOT / ".github/workflows/build-apk.yml").read_text(encoding="utf-8")
    publisher = workflow.split("  publish:", 1)[1]
    assert "path: 2-instaladores/ci-release-package" in publisher
    assert "../2-instaladores/ci-release-downloads" in publisher
    for path in ("2-instaladores/ci-release-package/paquete.zip",
                 "2-instaladores/ci-release-downloads/manifest.json"):
        result = subprocess.run(["git", "check-ignore", path], cwd=REPOSITORY_ROOT,
                                capture_output=True, text=True)
        assert result.returncode == 0, path

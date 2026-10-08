from pathlib import Path


PROGRAM_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PROGRAM_ROOT.parent


def test_numbered_repository_layout_is_present():
    for name in ("1-programa", "2-instaladores", "3-ejecutar"):
        assert (REPOSITORY_ROOT / name).is_dir()
        assert (REPOSITORY_ROOT / name / "README.md").is_file()
    assert (REPOSITORY_ROOT / "README.md").is_file()


def test_source_and_entry_points_are_in_the_expected_folders():
    assert (PROGRAM_ROOT / "main.py").is_file()
    assert (PROGRAM_ROOT / "lankdea").is_dir()
    assert (REPOSITORY_ROOT / "2-instaladores/configuracion-windows/Lankdea.iss").is_file()
    assert (REPOSITORY_ROOT / "3-ejecutar/Ejecutar Lankdea.cmd").is_file()
    assert not (REPOSITORY_ROOT / "main.py").exists()
    assert not (REPOSITORY_ROOT / "lankdea").exists()

from koyoapp import __version__, scaffold, templates


def test_scaffold_ships_deployment_files(tmp_path, monkeypatch):
    monkeypatch.setattr(scaffold, "create_venv", lambda project_dir: True)
    root = scaffold.scaffold(str(tmp_path / "demo"))

    procfile = (root / "Procfile").read_text(encoding="utf-8")
    assert procfile == (
        "web: python -m uvicorn koyoapp.serve:app --host 0.0.0.0 --port $PORT\n"
    )

    requirements = (root / "requirements.txt").read_text(encoding="utf-8")
    assert requirements == f"koyoapp=={__version__}\n"

    railwayignore = (root / ".railwayignore").read_text(encoding="utf-8")
    assert ".venv/" in railwayignore
    assert "__pycache__/" in railwayignore
    assert ".koyo/" in railwayignore


def test_scaffold_readme_documents_deploying(tmp_path, monkeypatch):
    monkeypatch.setattr(scaffold, "create_venv", lambda project_dir: True)
    root = scaffold.scaffold(str(tmp_path / "demo"))

    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "## Deploying" in readme
    assert "railway up" in readme


def test_deploy_files_are_in_template_set():
    assert "Procfile" in templates.FILES
    assert "requirements.txt" in templates.FILES
    assert ".railwayignore" in templates.FILES
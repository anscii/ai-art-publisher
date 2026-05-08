import os


def test_dockerfile_exists():
    assert os.path.exists("Dockerfile"), "Dockerfile missing"


def test_dockerfile_exposes_correct_port():
    content = open("Dockerfile").read()
    assert "EXPOSE 8080" in content
    assert "0.0.0.0" in content
    assert "8080" in content


def test_dockerfile_creates_data_dir():
    content = open("Dockerfile").read()
    assert "mkdir" in content and "data" in content


def test_flytoml_exists():
    assert os.path.exists("fly.toml"), "fly.toml missing"


def test_flytoml_auto_stop_off():
    content = open("fly.toml").read()
    assert "auto_stop_machines" in content
    assert '"off"' in content or "'off'" in content


def test_flytoml_has_volume_mount():
    content = open("fly.toml").read()
    assert "/app/data" in content


def test_gitignore_excludes_secrets():
    content = open(".gitignore").read()
    assert ".env" in content
    assert "data/" in content

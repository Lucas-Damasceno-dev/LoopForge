import os
from pathlib import Path
import pytest
from lf.config.loader import load_ade_config, save_ade_config
from lf.config.schema import AdeConfig, AdeMcpServer


def test_ade_config_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = load_ade_config()  # arquivo não existe -> defaults
    assert cfg.budget.max_usd == 10.0
    assert cfg.providers.primary == "native"
    assert cfg.hitl.timeout_seconds == 300
    assert cfg.mcp_servers == []


def test_ade_config_roundtrip_yaml(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = AdeConfig(mcp_servers=[AdeMcpServer(name="fs", command="npx", args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"])])
    path = save_ade_config(cfg, tmp_path / "ade.yaml")
    assert path.exists()
    loaded = load_ade_config(path)
    assert loaded.mcp_servers[0].name == "fs"
    assert loaded.mcp_servers[0].command == "npx"


def test_ade_config_invalid_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "ade.yaml").write_text("budget:\n  max_usd: 'nao-e-numero'\n")
    with pytest.raises(Exception):
        load_ade_config(tmp_path / "ade.yaml")

import tasks


def test_parser_lists_every_documented_subcommand():
    parser = tasks.build_parser()
    expected = {
        "init", "fmt", "lint", "test", "checkov",
        "dev", "plan", "deploy", "deploy-functions",
        "bootstrap-data", "backfill", "smoke-test", "evaluate", "destroy",
    }  # fmt: skip
    assert expected == set(tasks.HANDLERS)
    for name in expected:
        argv = [name, "--days", "3"] if name == "backfill" else [name]
        assert parser.parse_args(argv).command == name


def test_destroy_only_prints(capsys):
    assert tasks.main(["destroy"]) == 0
    assert "never deletes" in capsys.readouterr().out


def test_missing_script_returns_error(monkeypatch, capsys):
    monkeypatch.setattr(tasks, "ROOT", tasks.ROOT / "does-not-exist")
    assert tasks.run_script("nope.py") == 2
    assert "does not exist" in capsys.readouterr().err

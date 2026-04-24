"""Tests for the ``recon serve`` Click command.

Verifies the CLI accepts the right options, refuses unsafe binds,
and wires up the expected uvicorn invocation.
"""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from recon.cli import main


class TestServeHelp:
    def test_serve_command_is_registered(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--help"])
        assert result.exit_code == 0
        assert "Launch the recon web UI" in result.output

    def test_serve_advertises_default_port(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--help"])
        assert "8787" in result.output

    def test_serve_advertises_unsafe_bind_flag(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--help"])
        assert "--unsafe-bind-all" in result.output


class TestServeBindRefusal:
    def test_refuses_0000_without_unsafe_flag(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--host", "0.0.0.0"])
        assert result.exit_code != 0
        assert "unsafe-bind-all" in result.output.lower()

    def test_refuses_public_ip_without_unsafe_flag(self) -> None:
        # A non-loopback IP still requires explicit opt-in.
        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--host", "192.168.1.42"])
        assert result.exit_code != 0
        assert "unsafe-bind-all" in result.output.lower()

    def test_allows_localhost(self) -> None:
        runner = CliRunner()
        with patch("recon.web.server.run_server") as mock_run:
            result = runner.invoke(main, ["serve", "--host", "127.0.0.1", "--no-open"])
            assert result.exit_code == 0
            mock_run.assert_called_once()
            kwargs = mock_run.call_args.kwargs
            assert kwargs["host"] == "127.0.0.1"

    def test_allows_loopback_alias(self) -> None:
        runner = CliRunner()
        with patch("recon.web.server.run_server") as mock_run:
            result = runner.invoke(main, ["serve", "--host", "localhost", "--no-open"])
            assert result.exit_code == 0
            mock_run.assert_called_once()

    def test_allows_0000_with_unsafe_flag(self) -> None:
        runner = CliRunner()
        with patch("recon.web.server.run_server") as mock_run:
            result = runner.invoke(
                main,
                ["serve", "--host", "0.0.0.0", "--unsafe-bind-all", "--no-open"],
            )
            assert result.exit_code == 0
            mock_run.assert_called_once()
            assert mock_run.call_args.kwargs["host"] == "0.0.0.0"


class TestServeOptions:
    def test_passes_port_to_uvicorn(self) -> None:
        runner = CliRunner()
        with patch("recon.web.server.run_server") as mock_run:
            result = runner.invoke(main, ["serve", "--port", "9999", "--no-open"])
            assert result.exit_code == 0
            assert mock_run.call_args.kwargs["port"] == 9999

    def test_no_open_flag_disables_browser(self) -> None:
        runner = CliRunner()
        with patch("recon.web.server.run_server") as mock_run:
            result = runner.invoke(main, ["serve", "--no-open"])
            assert result.exit_code == 0
            assert mock_run.call_args.kwargs["open_browser"] is False

    def test_default_opens_browser(self) -> None:
        runner = CliRunner()
        with patch("recon.web.server.run_server") as mock_run:
            result = runner.invoke(main, ["serve"])
            assert result.exit_code == 0
            assert mock_run.call_args.kwargs["open_browser"] is True

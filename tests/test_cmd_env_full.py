import pytest
import argparse
from unittest.mock import patch
from nexus.environment import EnvironmentEntry, save_environments, load_environments


class TestCmdEnvList:
    def test_lists_envs(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_env_list
        save_environments([
            EnvironmentEntry(hostname="pc1", name="Home", location="casa", last_seen="2026-01-01")
        ])
        with patch("nexus._legacy_main.get_current_hostname", return_value="other-host"), \
             patch("nexus.environment.get_current_hostname", return_value="other-host"):
            cmd_env_list()
        out = capsys.readouterr().out
        assert "Home" in out
        assert "pc1" in out

    def test_lists_shows_current_marker(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_env_list
        save_environments([
            EnvironmentEntry(hostname="current-pc", name="Current", location="home")
        ])
        # cmd_env_list does: from .environment import get_current_hostname
        # so we patch the local import
        with patch("nexus.environment.get_current_hostname", return_value="current-pc"):
            cmd_env_list()
        out = capsys.readouterr().out
        assert "current-pc" in out
        assert "atual" in out

    def test_lists_shows_paths_count(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_env_list
        save_environments([
            EnvironmentEntry(
                hostname="pc1",
                name="Home",
                location="casa",
                paths={"nexus": "/home/user/nexus", "myapp": "/home/user/myapp"},
            )
        ])
        with patch("nexus.environment.get_current_hostname", return_value="other"):
            cmd_env_list()
        out = capsys.readouterr().out
        assert "Projetos: 2" in out

    def test_lists_shows_absent(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_env_list
        save_environments([
            EnvironmentEntry(
                hostname="pc1",
                name="Home",
                location="casa",
                absent=["old-proj"],
            )
        ])
        with patch("nexus.environment.get_current_hostname", return_value="other"):
            cmd_env_list()
        out = capsys.readouterr().out
        assert "old-proj" in out

    def test_empty_list(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_env_list
        cmd_env_list()
        assert "Nenhum" in capsys.readouterr().out

    def test_multiple_envs(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_env_list
        save_environments([
            EnvironmentEntry(hostname="pc1", name="Home", location="casa"),
            EnvironmentEntry(hostname="pc2", name="Work", location="trabalho"),
        ])
        with patch("nexus.environment.get_current_hostname", return_value="other"):
            cmd_env_list()
        out = capsys.readouterr().out
        assert "Home" in out
        assert "Work" in out


class TestCmdEnvInfo:
    def test_info_shows_current_env(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_env_info
        save_environments([
            EnvironmentEntry(hostname="mypc", name="My PC", location="office")
        ])
        with patch("nexus.environment.get_current_hostname", return_value="mypc"), \
             patch("nexus._legacy_main.get_current_hostname", return_value="mypc"):
            cmd_env_info(argparse.Namespace(name=None))
        out = capsys.readouterr().out
        assert "My PC" in out

    def test_info_by_name_query(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_env_info
        save_environments([
            EnvironmentEntry(hostname="pc1", name="Home Office", location="casa")
        ])
        with patch("nexus._legacy_main.get_current_hostname", return_value="other"):
            cmd_env_info(argparse.Namespace(name="home"))
        out = capsys.readouterr().out
        assert "Home Office" in out

    def test_info_by_hostname_query(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_env_info
        save_environments([
            EnvironmentEntry(hostname="my-laptop", name="Laptop", location="mobile")
        ])
        with patch("nexus._legacy_main.get_current_hostname", return_value="other"):
            cmd_env_info(argparse.Namespace(name="my-laptop"))
        out = capsys.readouterr().out
        assert "Laptop" in out

    def test_info_not_found(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_env_info
        save_environments([
            EnvironmentEntry(hostname="pc1", name="Home", location="casa")
        ])
        cmd_env_info(argparse.Namespace(name="nonexistent"))
        out = capsys.readouterr().out
        assert "não encontrado" in out or "nonexistent" in out

    def test_info_no_env_registered_for_host(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_env_info
        # No environments saved, and name=None → find_environment returns None
        with patch("nexus.environment.get_current_hostname", return_value="unknown-host"):
            cmd_env_info(argparse.Namespace(name=None))
        out = capsys.readouterr().out
        assert "Nenhum" in out or "setup" in out

    def test_info_shows_paths(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_env_info
        save_environments([
            EnvironmentEntry(
                hostname="mypc",
                name="My PC",
                location="home",
                paths={"nexus": "/home/user/nexus"},
            )
        ])
        with patch("nexus.environment.get_current_hostname", return_value="mypc"), \
             patch("nexus._legacy_main.get_current_hostname", return_value="mypc"):
            cmd_env_info(argparse.Namespace(name=None))
        out = capsys.readouterr().out
        assert "nexus" in out
        assert "/home/user/nexus" in out

    def test_info_shows_absent(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_env_info
        save_environments([
            EnvironmentEntry(
                hostname="mypc",
                name="My PC",
                location="home",
                absent=["gone-project"],
            )
        ])
        with patch("nexus.environment.get_current_hostname", return_value="mypc"), \
             patch("nexus._legacy_main.get_current_hostname", return_value="mypc"):
            cmd_env_info(argparse.Namespace(name=None))
        out = capsys.readouterr().out
        assert "gone-project" in out

    def test_info_shows_current_marker(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_env_info
        save_environments([
            EnvironmentEntry(hostname="mypc", name="My PC", location="home")
        ])
        with patch("nexus.environment.get_current_hostname", return_value="mypc"), \
             patch("nexus._legacy_main.get_current_hostname", return_value="mypc"):
            cmd_env_info(argparse.Namespace(name=None))
        out = capsys.readouterr().out
        assert "atual" in out


class TestCmdEnvSetup:
    def test_setup_registers_new_env(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_env_setup
        mock_input.side_effect = ["My PC", "home"]
        with patch("nexus.environment.get_current_hostname", return_value="new-host"), \
             patch("nexus._legacy_main.get_current_hostname", return_value="new-host"):
            cmd_env_setup(argparse.Namespace())
        envs = load_environments()
        assert len(envs) == 1
        assert envs[0].hostname == "new-host"
        assert envs[0].name == "My PC"
        assert envs[0].location == "home"

    def test_setup_skips_if_already_registered(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_env_setup
        save_environments([
            EnvironmentEntry(hostname="existing-host", name="Existing", location="home")
        ])
        with patch("nexus.environment.get_current_hostname", return_value="existing-host"), \
             patch("nexus._legacy_main.get_current_hostname", return_value="existing-host"):
            cmd_env_setup(argparse.Namespace())
        out = capsys.readouterr().out
        assert "já registrado" in out
        # Should not add a duplicate
        envs = load_environments()
        assert len(envs) == 1

    def test_setup_uses_hostname_as_default_name(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_env_setup
        # User enters empty string for name → hostname is used as default
        mock_input.side_effect = ["", "home"]
        with patch("nexus.environment.get_current_hostname", return_value="my-hostname"), \
             patch("nexus._legacy_main.get_current_hostname", return_value="my-hostname"):
            cmd_env_setup(argparse.Namespace())
        envs = load_environments()
        assert len(envs) == 1
        assert envs[0].name == "my-hostname"

    def test_setup_uses_unknown_as_default_location(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_env_setup
        # User enters empty string for location → "unknown" is used as default
        mock_input.side_effect = ["My PC", ""]
        with patch("nexus.environment.get_current_hostname", return_value="new-host"), \
             patch("nexus._legacy_main.get_current_hostname", return_value="new-host"):
            cmd_env_setup(argparse.Namespace())
        envs = load_environments()
        assert len(envs) == 1
        assert envs[0].location == "unknown"

    def test_setup_ctrl_c_cancels(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_env_setup
        mock_input.side_effect = KeyboardInterrupt
        with patch("nexus.environment.get_current_hostname", return_value="new-host"), \
             patch("nexus._legacy_main.get_current_hostname", return_value="new-host"):
            cmd_env_setup(argparse.Namespace())
        out = capsys.readouterr().out
        assert "Cancelado" in out
        assert load_environments() == []

    def test_setup_prints_hostname(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_env_setup
        mock_input.side_effect = ["My PC", "home"]
        with patch("nexus.environment.get_current_hostname", return_value="detected-host"), \
             patch("nexus._legacy_main.get_current_hostname", return_value="detected-host"):
            cmd_env_setup(argparse.Namespace())
        out = capsys.readouterr().out
        assert "detected-host" in out

    def test_setup_prints_success_message(self, nexus_env, mock_input, capsys):
        from nexus._legacy_main import cmd_env_setup
        mock_input.side_effect = ["My PC", "home"]
        with patch("nexus.environment.get_current_hostname", return_value="new-host"), \
             patch("nexus._legacy_main.get_current_hostname", return_value="new-host"):
            cmd_env_setup(argparse.Namespace())
        out = capsys.readouterr().out
        assert "registrado" in out


class TestCmdEnvDispatcher:
    def test_list_subcommand(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_env
        result = cmd_env(argparse.Namespace(env_cmd="list"))
        assert result == 0

    def test_default_subcommand(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_env
        # env_cmd=None falls back to "list"
        result = cmd_env(argparse.Namespace(env_cmd=None))
        assert result == 0

    def test_info_subcommand(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_env
        with patch("nexus.environment.get_current_hostname", return_value="unknown-host"):
            result = cmd_env(argparse.Namespace(env_cmd="info", name=None))
        assert result == 0

    def test_setup_subcommand_already_registered(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_env
        save_environments([
            EnvironmentEntry(hostname="some-host", name="Some", location="place")
        ])
        with patch("nexus.environment.get_current_hostname", return_value="some-host"), \
             patch("nexus._legacy_main.get_current_hostname", return_value="some-host"):
            result = cmd_env(argparse.Namespace(env_cmd="setup"))
        assert result == 0

    def test_unknown_subcmd(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_env
        result = cmd_env(argparse.Namespace(env_cmd="unknown"))
        assert result == 1

    def test_unknown_subcmd_prints_message(self, nexus_env, capsys):
        from nexus._legacy_main import cmd_env
        cmd_env(argparse.Namespace(env_cmd="bogus"))
        out = capsys.readouterr().out
        assert "bogus" in out or "desconhecido" in out

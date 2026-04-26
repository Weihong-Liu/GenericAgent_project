import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generic_agent_engineered.config import (
    RuntimeSettings,
    find_project_config_path,
    get_agent_home,
    get_project_config_path,
    resolve_runtime_settings,
)


class RuntimeSettingsTests(unittest.TestCase):
    def test_home_uses_env_override(self):
        env = {"GENERIC_AGENT_HOME": "/tmp/generic-agent-test"}
        self.assertEqual(get_agent_home(env), Path("/tmp/generic-agent-test"))

    def test_from_env_defaults(self):
        settings = RuntimeSettings.from_env()
        self.assertTrue(settings.default_provider)
        self.assertTrue(settings.default_model)
        self.assertEqual(settings.auth_path.name, "auth.json")

    def test_layered_precedence_cli_env_project_user_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            project = root / "project"
            nested = project / "src" / "package"
            home.mkdir()
            nested.mkdir(parents=True)

            (home / "settings.json").write_text(
                json.dumps(
                    {
                        "env": {
                            "GA_PROVIDER": "user-provider",
                            "GA_MODEL": "user-model",
                            "GA_LANG": "en",
                            "GA_VERBOSE": "true",
                            "GA_YOLO": "false",
                            "HTTPS_PROXY": "http://user-proxy",
                        }
                    }
                ),
                encoding="utf-8",
            )
            (project / ".generic-agent.yaml").write_text(
                "\n".join(
                    [
                        "runtime:",
                        "  provider: project-provider",
                        "  model: project-model",
                        "  yolo: true",
                        "  proxy: http://project-proxy",
                    ]
                ),
                encoding="utf-8",
            )

            settings = resolve_runtime_settings(
                cwd=nested,
                env={
                    "GENERIC_AGENT_HOME": str(home),
                    "GA_PROVIDER": "env-provider",
                    "GA_MODEL": "env-model",
                    "GA_VERBOSE": "false",
                },
                cli_overrides={"model": "cli-model"},
            )

        self.assertEqual(settings.home, home)
        self.assertEqual(settings.default_provider, "env-provider")
        self.assertEqual(settings.default_model, "cli-model")
        self.assertEqual(settings.language, "en")
        self.assertFalse(settings.verbose)
        self.assertTrue(settings.yolo)
        self.assertEqual(settings.proxy, "http://project-proxy")

    def test_project_config_path_resolution_walks_upward(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            nested = project / "a" / "b"
            nested.mkdir(parents=True)
            config_path = project / ".generic-agent" / "settings.json"
            config_path.parent.mkdir()
            config_path.write_text('{"env": {"GA_PROVIDER": "openai"}}', encoding="utf-8")

            self.assertEqual(find_project_config_path(nested), config_path.resolve())
            self.assertEqual(get_project_config_path(nested), config_path.resolve())

    def test_boolean_env_parsing(self):
        settings = RuntimeSettings.from_env({"GA_VERBOSE": "yes", "GA_YOLO": "0"})
        self.assertTrue(settings.verbose)
        self.assertFalse(settings.yolo)

    def test_proxy_env_resolution(self):
        settings = RuntimeSettings.from_env(
            {
                "HTTP_PROXY": "http://http-proxy",
                "HTTPS_PROXY": "http://https-proxy",
                "all_proxy": "socks5://all-proxy",
            }
        )
        self.assertEqual(settings.proxy, "http://https-proxy")

        settings = RuntimeSettings.from_env({"all_proxy": "socks5://all-proxy"})
        self.assertEqual(settings.proxy, "socks5://all-proxy")

    def test_json_project_settings_env_block_matches_free_code_style(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            nested = project / "pkg"
            nested.mkdir(parents=True)
            settings_path = project / ".generic-agent" / "settings.json"
            settings_path.parent.mkdir()
            settings_path.write_text(
                json.dumps(
                    {
                        "env": {
                            "GA_PROVIDER": "json-env-provider",
                            "GA_MODEL": "json-env-model",
                            "GA_VERBOSE": "true",
                            "HTTPS_PROXY": "http://json-proxy",
                            "OPENAI_API_KEY": "from-settings",
                        }
                    }
                ),
                encoding="utf-8",
            )

            settings = resolve_runtime_settings(cwd=nested, env={})

        self.assertEqual(settings.default_provider, "json-env-provider")
        self.assertEqual(settings.default_model, "json-env-model")
        self.assertTrue(settings.verbose)
        self.assertEqual(settings.proxy, "http://json-proxy")
        self.assertEqual(settings.environment["OPENAI_API_KEY"], "from-settings")

    def test_legacy_project_json_remains_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            nested = project / "pkg"
            nested.mkdir(parents=True)
            (project / ".generic-agent.json").write_text(
                json.dumps({"env": {"GA_PROVIDER": "legacy-json-provider"}}),
                encoding="utf-8",
            )

            settings = resolve_runtime_settings(cwd=nested, env={})

        self.assertEqual(settings.default_provider, "legacy-json-provider")

    def test_folder_project_settings_prefer_over_legacy_root_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            nested = project / "pkg"
            nested.mkdir(parents=True)
            (project / ".generic-agent.json").write_text(
                json.dumps({"env": {"GA_PROVIDER": "legacy-json-provider"}}),
                encoding="utf-8",
            )
            settings_path = project / ".generic-agent" / "settings.json"
            settings_path.parent.mkdir()
            settings_path.write_text(
                json.dumps({"env": {"GA_PROVIDER": "folder-json-provider"}}),
                encoding="utf-8",
            )

            settings = resolve_runtime_settings(cwd=nested, env={})

        self.assertEqual(settings.default_provider, "folder-json-provider")

    def test_json_env_var_is_lower_priority_than_explicit_env(self):
        settings = RuntimeSettings.from_env(
            {
                "GA_CONFIG_JSON": json.dumps(
                    {
                        "provider": "json-provider",
                        "model": "json-model",
                        "env": {
                            "GA_PROVIDER": "json-env-provider",
                            "GA_MODEL": "json-env-model",
                            "CUSTOM_FLAG": True,
                            "HTTPS_PROXY": "http://json-proxy",
                        },
                    }
                ),
                "GA_MODEL": "explicit-env-model",
            }
        )

        self.assertEqual(settings.default_provider, "json-provider")
        self.assertEqual(settings.default_model, "explicit-env-model")
        self.assertEqual(settings.proxy, "http://json-proxy")
        self.assertEqual(settings.environment["CUSTOM_FLAG"], "true")

    def test_json_env_var_can_set_agent_home(self):
        settings = RuntimeSettings.from_env(
            {"GA_CONFIG_JSON": json.dumps({"env": {"GENERIC_AGENT_HOME": "/tmp/json-home"}})}
        )
        self.assertEqual(settings.home, Path("/tmp/json-home"))

    def test_invalid_json_env_var_raises_clear_error(self):
        with self.assertRaisesRegex(ValueError, "GA_CONFIG_JSON"):
            RuntimeSettings.from_env({"GA_CONFIG_JSON": "[]"})


if __name__ == "__main__":
    unittest.main()

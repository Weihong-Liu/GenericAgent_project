import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generic_agent_engineered.providers.registry import build_provider_registry


class ProviderRegistryTests(unittest.TestCase):
    def test_resolves_aliases(self):
        registry = build_provider_registry()
        self.assertEqual(registry.resolve("claude").id, "anthropic")
        self.assertEqual(registry.resolve("qwen").id, "dashscope")
        self.assertEqual(registry.resolve("codex").id, "openai-codex")

    def test_unknown_provider_raises(self):
        registry = build_provider_registry()
        with self.assertRaises(KeyError):
            registry.resolve("missing")


if __name__ == "__main__":
    unittest.main()

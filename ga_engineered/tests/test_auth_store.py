import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generic_agent_engineered.auth.store import AuthRecord, AuthStore, create_pkce_pair


class AuthStoreTests(unittest.TestCase):
    def test_put_get_delete_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AuthStore(Path(tmp) / "auth.json")
            store.put(AuthRecord(provider_id="openai", api_key="sk-test"))
            self.assertEqual(store.get("openai").api_key, "sk-test")
            store.delete("openai")
            self.assertIsNone(store.get("openai"))

    def test_pkce_pair_shape(self):
        verifier, challenge = create_pkce_pair()
        self.assertGreaterEqual(len(verifier), 40)
        self.assertGreaterEqual(len(challenge), 40)
        self.assertNotIn("=", verifier)
        self.assertNotIn("=", challenge)


if __name__ == "__main__":
    unittest.main()

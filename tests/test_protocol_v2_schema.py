import json
import unittest
from pathlib import Path

from protocol.v2.e2e_protocol import REQUIRED_FIELDS, SURFACES, TRANSITIONS


ROOT = Path(__file__).parents[1]


class ProtocolV2SchemaTests(unittest.TestCase):
    def test_core_schema_matches_runtime_vocabulary(self):
        schema = json.loads((ROOT / "protocol/v2/manifest.schema.json").read_text())
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["$id"], "urn:e2e-testing:protocol:2.0")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["required"], list(REQUIRED_FIELDS))
        self.assertEqual(set(schema["$defs"]["run"]["properties"]["status"]["enum"]), set(TRANSITIONS))
        self.assertEqual(set(schema["$defs"]["surface"]["enum"]), SURFACES)
        self.assertNotIn("maxItems", schema["properties"]["systems"])

    def test_extension_envelope_is_strict_but_data_is_surface_owned(self):
        schema = json.loads((ROOT / "protocol/v2/manifest.schema.json").read_text())
        extension = schema["$defs"]["extension"]
        self.assertFalse(extension["additionalProperties"])
        self.assertEqual(extension["required"], ["id", "namespace", "version", "owner", "data"])
        self.assertEqual(extension["properties"]["data"], {"type": "object"})

    def test_web_migration_extension_has_stable_identity(self):
        schema = json.loads((ROOT / "protocol/v2/extensions/web.schema.json").read_text())
        self.assertEqual(schema["$id"], "urn:e2e-testing:extension:web:1.0")
        self.assertEqual(schema["required"], ["driver", "project", "target"])

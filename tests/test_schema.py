from __future__ import annotations

import unittest

import helpers  # noqa: F401  (sets sys.path)
import schema

PERSON = {
    "type": "object",
    "required": ["name", "age"],
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string", "pattern": "^[A-Z]"},
        "age": {"type": "integer", "minimum": 0, "maximum": 150},
        "tags": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        "role": {"type": ["string", "null"], "enum": [None, "dev", "lead"]},
        "extra": {"type": "object", "additionalProperties": {"type": "integer"}},
    },
}


class ValidateTest(unittest.TestCase):
    def test_valid_instance_has_no_errors(self):
        self.assertEqual(schema.validate({"name": "Ana", "age": 30, "tags": ["x"], "role": None}, PERSON), [])

    def test_missing_required_key(self):
        self.assertEqual(schema.validate({"name": "Ana"}, PERSON), ["$: missing required key 'age'"])

    def test_wrong_type_reports_path(self):
        self.assertEqual(schema.validate({"name": "Ana", "age": "30"}, PERSON), ["$.age: expected integer"])

    def test_boolean_is_not_integer(self):
        self.assertEqual(schema.validate({"name": "Ana", "age": True}, PERSON), ["$.age: expected integer"])

    def test_enum_pattern_minimum_maximum(self):
        errors = schema.validate({"name": "ana", "age": 200, "role": "boss"}, PERSON)
        self.assertIn("$.name: 'ana' does not match ^[A-Z]", errors)
        self.assertIn("$.age: 200 is greater than maximum 150", errors)
        self.assertIn("$.role: 'boss' not in [None, 'dev', 'lead']", errors)

    def test_additional_properties_false_and_schema(self):
        errors = schema.validate({"name": "Ana", "age": 1, "x": 1, "extra": {"a": "no"}}, PERSON)
        self.assertIn("$: unexpected key 'x'", errors)
        self.assertIn("$.extra.a: expected integer", errors)

    def test_array_min_items_and_item_errors(self):
        self.assertEqual(schema.validate({"name": "Ana", "age": 1, "tags": []}, PERSON),
                         ["$.tags: expected at least 1 item(s)"])
        self.assertEqual(schema.validate({"name": "Ana", "age": 1, "tags": [3]}, PERSON),
                         ["$.tags[0]: expected string"])


if __name__ == "__main__":
    unittest.main()

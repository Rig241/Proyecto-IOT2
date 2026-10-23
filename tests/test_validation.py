"""Pruebas del contrato de datos; ejecutar desde la raíz con las dependencias del puente."""
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("bridge_app", Path(__file__).resolve().parents[1] / "bridge/app.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MeasurementContract(unittest.TestCase):
    def test_numeric_measurements(self):
        data = {"voltaje": 220.5, "corriente": 1.23, "resistencia": 179.3, "fase": 45.2}
        self.assertEqual(module.parse_measurement(json.dumps(data).encode()), data)

    def test_rejects_incomplete_or_non_numeric_data(self):
        valid = {"voltaje": 220, "corriente": 1, "resistencia": 220, "fase": 0}
        invalid = [b"not-json", b"[]", b"null", b"{}", b"x" * 4097]
        for value in (True, None, "220.5", float("nan"), float("inf")):
            invalid.append(json.dumps({**valid, "voltaje": value}).encode())
        for payload in invalid:
            with self.subTest(payload=payload[:80]):
                with self.assertRaises(ValueError):
                    module.parse_measurement(payload)


if __name__ == "__main__":
    unittest.main()

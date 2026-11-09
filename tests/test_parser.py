import unittest
from carconnectivity_connectors.mercedes.parser import normalize
from scripts.vendor_mbapi_protos import rewrite_imports, UPSTREAM_FILES


class ParserTest(unittest.TestCase):
    def test_values_and_vehicle_timestamps(self):
        data = {'odo': {'value': 12345, 'metadata': {'timestamp': '2026-11-09T07:15:00Z'}},
                'soc': {'value': 0, 'metadata': {'status': 'VALUE_VALID'}},
                'position_lat': {'metadata': {'status': 'VALUE_NOT_AVAILABLE'}}}
        result = normalize(data)
        self.assertEqual(result['odometer'][0], 12345)
        self.assertEqual(result['odometer'][1].year, 2026)
        self.assertEqual(result['soc'][0], 0)
        self.assertIsNone(result['latitude'][0])
        self.assertEqual(result['odometer'][0], 12345.0)

    def test_missing_is_not_zero(self):
        result = normalize({})
        self.assertTrue(all(v[0] is None for v in result.values()))


class AdditionalTests(unittest.TestCase):
    def test_protobuf_int64_string_and_invalid_number(self):
        values = normalize({'soc': {'value': '69'}, 'rangeelectric': {'value': '418'},
                            'odo': {'value': 'broken'}})
        self.assertEqual(values['soc'][0], 69.0)
        self.assertEqual(values['electric_range'][0], 418.0)
        self.assertIsNone(values['odometer'][0])

    def test_no_fabricated_position_or_timestamp(self):
        values = normalize({'position_lat': {'value': '48.9'}})
        self.assertEqual(values['latitude'][0], 48.9)
        self.assertIsNone(values['longitude'][0])
        self.assertIsNone(values['latitude'][1])

    def test_generated_import_rewrite(self):
        source = 'import custom_components.mbapi2020.proto.vehicleapi_pb2 as vehicleapi__pb2\n'
        self.assertEqual(rewrite_imports(source), 'from . import vehicleapi_pb2 as vehicleapi__pb2\n')
        self.assertGreaterEqual(len(UPSTREAM_FILES), 10)

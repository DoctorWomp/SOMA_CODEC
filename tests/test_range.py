import copy
import http.client
import json
from pathlib import Path
import threading
import unittest
from http.server import ThreadingHTTPServer
from soma_range.contracts import Communication, Decision, Memory, Observation, PROTOCOL
from soma_range.runtime import decide, replay
from soma_range.server import Handler

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    return json.loads((ROOT / "configs/expo_demo.json").read_text())["observations"][0]


class ContractTests(unittest.TestCase):
    def test_communication_requires_private_recipient(self):
        item = fixture()
        item["sender_id"] = item.pop("source_id")
        item["visibility"] = "private"
        self.assertEqual(Communication.parse(item).recipient_id, "robot-r")
        item["recipient_id"] = None
        with self.assertRaises(ValueError):
            Communication.parse(item)
        item["visibility"] = "public"
        self.assertIsNone(Communication.parse(item).recipient_id)

    def test_schema_fields_match_typed_contracts(self):
        for name, contract in [("observation", Observation), ("decision", Decision),
                               ("communication", Communication)]:
            schema = json.loads((ROOT / f"contracts/{name}.schema.json").read_text())
            self.assertEqual(set(schema["properties"]), set(contract.__dataclass_fields__))
            self.assertEqual(set(schema["required"]), set(contract.__dataclass_fields__))
            self.assertFalse(schema["additionalProperties"])

    def test_rejects_invalid_boundary_inputs(self):
        for field, value in [("tick", True), ("tick", -1), ("tick", 1.5),
                             ("protocol", "v2"), ("recipient_id", ""),
                             ("source_id", 12), ("channel", "mind-reading"),
                             ("visibility", "global"), ("content", "x" * 4097),
                             ("content", None), ("trace_id", "x" * 129)]:
            with self.subTest(field=field, value=str(value)[:30]):
                item = fixture()
                item[field] = value
                with self.assertRaises(ValueError):
                    Observation.parse(item)
        item = fixture()
        item["hidden_world_state"] = {}
        with self.assertRaises(ValueError):
            Observation.parse(item)
        item = fixture()
        del item["source_id"]
        with self.assertRaises(ValueError):
            Observation.parse(item)

    def test_memory_does_not_leak_between_owners(self):
        memory = Memory()
        item = Observation.parse(fixture())
        memory.remember("robot-r", item)
        self.assertEqual(memory.recall("visitor-x"), ())
        self.assertEqual(memory.recall("robot-r"), (item,))
        with self.assertRaises(ValueError):
            memory.remember("visitor-x", item)

    def test_unknown_source_stays_unknown(self):
        item = fixture()
        item["source_id"] = None
        self.assertIsNone(decide(Observation.parse(item), "B").target_id)

    def test_matched_ab_has_no_fabricated_treatment(self):
        item = Observation.parse(fixture())
        a, b = decide(item, "A").wire(), decide(item, "B").wire()
        self.assertEqual(a.pop("horizon_arm"), "A")
        self.assertEqual(b.pop("horizon_arm"), "B")
        self.assertEqual(a, b)
        with self.assertRaises(ValueError):
            decide(item, "C")

    def test_replay_is_canonical_and_detects_changed_output(self):
        first = decide(Observation.parse(fixture()), "A").wire()
        self.assertEqual(replay([first]), replay([dict(reversed(list(first.items())))]))
        altered = copy.deepcopy(first)
        altered["action"] = "wait"
        self.assertNotEqual(replay([first]), replay([altered]))
        with self.assertRaises(ValueError):
            replay([first, first])
        earlier = dict(first, tick=0, trace_id="earlier")
        with self.assertRaises(ValueError):
            replay([first, earlier])
        for field, value in [("actor_id", ""), ("tick", True), ("action", "teleport"),
                             ("protocol", "bad"), ("horizon_arm", "C")]:
            with self.assertRaises(ValueError):
                replay([dict(first, **{field: value})])

    def test_all_demo_observations_round_trip(self):
        config = json.loads((ROOT / "configs/expo_demo.json").read_text())
        for item in config["observations"]:
            observation = Observation.parse(item)
            self.assertEqual(observation.protocol, PROTOCOL)
            self.assertEqual(decide(observation, "A").actor_id, item["recipient_id"])


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def request(self, method, path, body=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method, path, body=body, headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_http_godot_fixture_and_health(self):
        self.assertEqual(self.request("GET", "/health")[1]["adapter"], "offline-stub")
        status, decision = self.request("POST", "/v1/decision", json.dumps(
            {"observation": fixture(), "horizon_arm": "A"}))
        self.assertEqual(status, 200)
        self.assertEqual(decision["action"], "acknowledge")
        self.assertEqual(decision["observation_trace_id"], fixture()["trace_id"])

    def test_invalid_requests_fail_without_echoing_private_data(self):
        for body in ("{", "[]", "{}", "x" * 17000,
                     json.dumps({"observation": dict(fixture(), content="PRIVATE", tick=-1),
                                 "horizon_arm": "A"})):
            status, response = self.request("POST", "/v1/decision", body)
            self.assertEqual(status, 400)
            self.assertNotIn("PRIVATE", json.dumps(response))
        self.assertEqual(self.request("GET", "/missing")[0], 404)
        self.assertEqual(self.request("POST", "/missing", "{}")[0], 404)


if __name__ == "__main__":
    unittest.main()

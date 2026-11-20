"""Offline regression checks for the native reference transport, including early EOS."""
import json
import unittest
from hashlib import sha256

if __package__:
    from . import qwen_reference as ref
else:
    import qwen_reference as ref


def completion(path, body=None):
    if path == "/props":
        return {"total_slots": 1, "default_generation_settings": {"n_ctx": 6144}}
    assert path == "/completion" and body["temperature"] == 0 and body["top_k"] == 1
    assert body["id_slot"] == 0 and body["cache_prompt"] is False
    assert len(body["prompt"].encode()) + body["n_predict"] + 8 <= 6144
    if "json_schema" in body:
        content = json.dumps({key: "clock" for key in body["json_schema"]["required"]})
    else:
        content = sha256(body["prompt"].encode()).hexdigest() * 35
    return {"content": content, "model": ref.EDITION, "stop": True, "stop_type": "limit"}


class ReferenceTests(unittest.TestCase):
    def test_independent_inverse_and_low_address_prefix(self):
        fresh = lambda: ref.ReferenceEdition(request=completion)
        encoder = fresh()
        self.assertEqual(encoder.health()["edition"], ref.EDITION)
        page = ref.text.ALPHABET * 16
        self.assertEqual(fresh().unrank(encoder.rank(page)), page)
        maximum = (1 << (8 * ref.PAGE)) - 1
        for address in (17, maximum):
            self.assertEqual(fresh().rank(encoder.unrank(address)), address)
        seed = (17).to_bytes(ref.HALF, "big")
        opening = encoder.opening(seed)
        model_page = ref.text.decode(opening + encoder.continuation(opening))
        page = encoder.unrank(17)
        self.assertEqual(page[:-1], model_page[:-1])
        self.assertNotEqual(page[-1], model_page[-1])
        self.assertEqual(ref.parse_number(str(ref.Decimal(maximum))), maximum)

    def test_early_eos_has_a_defined_tail_and_runtime_failure_is_retryable(self):
        fail_once = True
        def empty(path, body=None):
            nonlocal fail_once
            if fail_once:
                fail_once = False
                return {"model": ref.EDITION, "stop": False, "content": ""}
            return {"model": ref.EDITION, "stop": True, "stop_type": "eos", "content": ""}

        edition = ref.ReferenceEdition(request=empty)
        with self.assertRaises(ref.ReferenceUnavailable):
            edition.unrank(41)
        page = edition.unrank(41)
        self.assertEqual(len(page), ref.PAGE)
        self.assertEqual(ref.ReferenceEdition(request=empty).rank(page), 41)

    def test_verbatim_domain_and_input_limits(self):
        edition = ref.ReferenceEdition(request=completion)
        for page in (" " * (ref.PAGE - 1), "漢" + " " * (ref.PAGE - 1)):
            with self.assertRaises(ValueError):
                edition.rank(page)
        for number in ("-1", "0x", "0x1" + "0" * (2 * ref.PAGE)):
            with self.assertRaises(ValueError):
                ref.parse_number(number)


if __name__ == "__main__":
    unittest.main()

"""The two Search editions route to their own queues and return their own identities."""
from time import monotonic, sleep
from unittest import TestCase, main
from unittest.mock import patch

import backend_app
from qwen35_reference import EDITION
from qwen_web_jobs import MODE_35, QwenJobs

PAGE = 'a' * 4096


class FakeClient:
    def __init__(self, *, endpoint):
        self.endpoint = endpoint

    def unrank(self, address):
        assert address == 32
        return PAGE

    def rank(self, page):
        assert page == PAGE
        return 32


class Qwen35WebTest(TestCase):
    def setUp(self):
        self.jobs = QwenJobs(FakeClient, default_endpoint='http://test.invalid', edition=EDITION)
        self.addCleanup(self.jobs.executor.shutdown)
        self.patcher = patch.object(backend_app, 'qwen35_jobs', self.jobs)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.web = backend_app.app.test_client()

    def result(self, action, **payload):
        response = self.web.post('/api/' + action, json={'mode': MODE_35, **payload})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json['mode'], MODE_35)
        location = response.headers['Location']
        self.assertTrue(location.startswith('/api/qwen35/jobs/'))
        end = monotonic() + 5
        while monotonic() < end:
            response = self.web.get(location)
            if response.status_code != 202:
                self.assertEqual(response.status_code, 200, response.json)
                self.assertEqual(response.json['mode'], MODE_35)
                self.assertEqual(response.json['edition'], EDITION)
                return response.json
            sleep(.01)
        self.fail('job did not finish')

    def test_open_and_find(self):
        opened = self.result('unrank', rank='32')
        self.assertEqual(opened['page'], PAGE)
        found = self.result('rank', text=opened['page'])
        self.assertEqual(found['rank'], '32')
        self.assertEqual(found['rank_hex'], '0x20')

    def test_page_validation_and_endpoint_isolation(self):
        response = self.web.post('/api/rank', json={'mode': MODE_35, 'text': 'a' * 4097})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['mode'], MODE_35)
        response = self.web.get('/api/qwen35/jobs/not-a-job')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json['mode'], MODE_35)


if __name__ == '__main__':
    main()

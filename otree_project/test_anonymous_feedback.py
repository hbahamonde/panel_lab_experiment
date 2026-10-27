"""Privacy and persistence tests without creating or touching oTree data."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from anonymous_feedback import FeedbackGateway, FeedbackStore, validate_answers


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / 'feedback.sqlite3'
        self.store = FeedbackStore(sqlite_path=str(self.path))

    def tearDown(self):
        self.temporary.cleanup()

    def test_only_answer_aggregates_are_stored(self):
        self.store.submit(dict(
            instructions='5', methods='4', payment='3', unclear='Example difficulty',
            improvement='Example improvement', purpose='Example purpose',
        ))
        self.store.submit(dict(instructions='4', payment='5', purpose='Other purpose'))
        exported = self.store.export(minimum_responses=0)
        self.assertEqual(set(exported), {
            'responses', 'instructions', 'methods', 'payment',
            'unclear', 'improvement', 'purpose',
        })
        self.assertEqual(exported['responses'], 2)
        self.assertEqual(exported['instructions']['4'], 1)
        self.assertEqual(exported['instructions']['5'], 1)
        self.assertEqual(exported['methods']['4'], 1)
        self.assertCountEqual(exported['purpose'], ['Example purpose', 'Other purpose'])
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute('SELECT * FROM pilot_feedback_aggregate').fetchall()
            columns = connection.execute('PRAGMA table_info(pilot_feedback_aggregate)').fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual([column[1] for column in columns], ['singleton', 'payload'])

    def test_blank_answers_are_allowed(self):
        self.store.submit({})
        self.assertEqual(self.store.export()['responses'], 1)

    def test_export_withholds_answers_until_five_responses(self):
        for _ in range(4):
            self.store.submit(dict(purpose='Private until the batch is ready'))
        self.assertNotIn('purpose', self.store.export())
        self.store.submit({})
        self.assertIn('purpose', self.store.export())

    def test_invalid_or_identifying_extra_fields_are_rejected(self):
        for bad in [dict(participant_code='abc'), dict(instructions='6'),
                    dict(unclear='x' * 601), dict(payment=True), [], 'text']:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    validate_answers(bad)
        self.assertFalse(self.path.exists())

    def test_concurrent_submissions_do_not_overwrite_counts(self):
        with ThreadPoolExecutor(max_workers=5) as executor:
            list(executor.map(lambda _: self.store.submit(dict(instructions='5')), range(20)))
        self.assertEqual(self.store.export()['responses'], 20)
        self.assertEqual(self.store.export()['instructions']['5'], 20)


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / 'feedback.sqlite3'
        self.store = FeedbackStore(sqlite_path=str(self.path))
        self.forwarded = []

        async def otree_app(scope, receive, send):
            self.forwarded.append(scope)
            await send(dict(type='http.response.start', status=204, headers=[]))
            await send(dict(type='http.response.body', body=b''))

        self.gateway = FeedbackGateway(otree_app, enabled=True, store=self.store)
        self.otree_app = otree_app

    async def asyncTearDown(self):
        self.temporary.cleanup()

    async def request(self, method='GET', body=b'', query=b'', path='/pilot-feedback', gateway=None):
        messages = []
        scope = dict(
            type='http', method=method, path=path, query_string=query,
            client=('PRIVATE-SEAT-IP', 12345),
            headers=[(b'content-type', b'application/json'), (b'cookie', b'PRIVATE-COOKIE'),
                     (b'referer', b'PRIVATE-PARTICIPANT-URL')],
        )

        async def receive():
            return dict(type='http.request', body=body, more_body=False)

        async def send(message):
            messages.append(message)

        await (gateway or self.gateway)(scope, receive, send)
        return messages

    async def test_form_is_outside_otree_and_sets_no_cookie(self):
        messages = await self.request()
        self.assertEqual(messages[0]['status'], 200)
        self.assertEqual(self.forwarded, [])
        self.assertNotIn(b'set-cookie', dict(messages[0]['headers']))
        self.assertEqual(dict(messages[0]['headers'])[b'referrer-policy'], b'no-referrer')
        self.assertIn(b"credentials: 'omit'", messages[1]['body'])

    async def test_submission_ignores_all_request_identifiers(self):
        messages = await self.request('POST', json.dumps(dict(instructions='5')).encode())
        self.assertEqual(messages[0]['status'], 200)
        data = json.dumps(self.store.export(minimum_responses=0))
        for identifier in ['PRIVATE-SEAT-IP', 'PRIVATE-COOKIE', 'PRIVATE-PARTICIPANT-URL']:
            self.assertNotIn(identifier, data)
        self.assertEqual(self.forwarded, [])

    async def test_disabled_form_and_query_parameters_are_rejected(self):
        disabled = FeedbackGateway(self.otree_app, enabled=False, store=self.store)
        self.assertEqual((await self.request(gateway=disabled))[0]['status'], 404)
        self.assertEqual((await self.request(query=b'participant=PRIVATE'))[0]['status'], 404)
        self.assertFalse(self.path.exists())

    async def test_bad_payload_does_not_create_storage(self):
        response = await self.request('POST', b'{"participant_code":"PRIVATE"}')
        self.assertEqual(response[0]['status'], 400)
        response = await self.request('POST', b'x' * 8193)
        self.assertEqual(response[0]['status'], 413)
        self.assertFalse(self.path.exists())

    async def test_other_otree_paths_are_preserved(self):
        messages = await self.request(path='/InitializeParticipant/xyz')
        self.assertEqual(messages[0]['status'], 204)
        self.assertEqual(len(self.forwarded), 1)

    async def test_plain_browser_form_posts_are_rejected(self):
        messages = []

        async def receive():
            return dict(type='http.request', body=b'instructions=5', more_body=False)

        async def send(message):
            messages.append(message)

        await self.gateway(dict(
            type='http', method='POST', path='/pilot-feedback', query_string=b'',
            headers=[(b'content-type', b'application/x-www-form-urlencoded')],
        ), receive, send)
        self.assertEqual(messages[0]['status'], 415)
        self.assertFalse(self.path.exists())


if __name__ == '__main__':
    unittest.main()

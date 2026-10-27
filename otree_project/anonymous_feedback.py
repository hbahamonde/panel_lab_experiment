"""Optional anonymous pilot feedback, stored apart from oTree research records.

There are no participant, session, payment, IP, timestamp, or response-order
fields. Closed responses are pooled as counts. Each open question has its own
shuffled list, so one person's answers cannot be joined across questions.
"""

import json
from contextlib import closing
import os
from pathlib import Path
import secrets
import sqlite3
import sys


FEEDBACK_PATH = '/pilot-feedback'
MAX_BODY_BYTES = 8192
MAX_TEXT_LENGTH = 600
RATING_KEYS = ('instructions', 'methods', 'payment')
TEXT_KEYS = ('unclear', 'improvement', 'purpose')
ANSWER_KEYS = set(RATING_KEYS + TEXT_KEYS)


def feedback_enabled():
    return os.environ.get('PRETEST_FEEDBACK_ENABLED', '').strip() == '1'


def empty_aggregate():
    return dict(
        responses=0,
        instructions={str(n): 0 for n in range(1, 6)},
        methods={str(n): 0 for n in range(1, 6)},
        payment={str(n): 0 for n in range(1, 6)},
        unclear=[], improvement=[], purpose=[],
    )


def validate_answers(value):
    if not isinstance(value, dict) or set(value) - ANSWER_KEYS:
        raise ValueError('Use only the six feedback questions.')
    clean = {}
    for key in ANSWER_KEYS:
        answer = value.get(key, '')
        if not isinstance(answer, str):
            raise ValueError('Answers must be text.')
        answer = answer.strip()
        if key in RATING_KEYS and answer not in ('', '1', '2', '3', '4', '5'):
            raise ValueError('Choose a rating from 1 to 5, or leave it unanswered.')
        if key in TEXT_KEYS and len(answer) > MAX_TEXT_LENGTH:
            raise ValueError('Please limit each written answer to 600 characters.')
        clean[key] = answer
    return clean


def add_answers(aggregate, answers):
    aggregate['responses'] += 1
    for key in RATING_KEYS:
        if answers[key]:
            aggregate[key][answers[key]] += 1
    for key in TEXT_KEYS:
        if answers[key]:
            aggregate[key].append(answers[key])
        secrets.SystemRandom().shuffle(aggregate[key])
    return aggregate


class FeedbackStore:
    """One aggregate row only, in a separate table or local sidecar database."""

    def __init__(self, *, database_url=None, sqlite_path=None):
        self.database_url = database_url
        self.sqlite_path = sqlite_path or os.environ.get(
            'PRETEST_FEEDBACK_DB',
            str(Path(__file__).with_name('pilot_feedback.sqlite3')),
        )

    @classmethod
    def from_environment(cls):
        return cls(database_url=os.environ.get('DATABASE_URL'))

    def _postgres_connection(self):
        import psycopg2
        return psycopg2.connect(self.database_url)

    def submit(self, answers):
        answers = validate_answers(answers)
        if self.database_url:
            with closing(self._postgres_connection()) as connection, connection:
                with connection.cursor() as cursor:
                    # Serialize first-use schema creation as well as updates.
                    cursor.execute('SELECT pg_advisory_xact_lock(%s)', (823740190,))
                    cursor.execute(
                        'CREATE TABLE IF NOT EXISTS pilot_feedback_aggregate '
                        '(singleton BOOLEAN PRIMARY KEY CHECK (singleton), payload JSONB NOT NULL)'
                    )
                    cursor.execute(
                        'INSERT INTO pilot_feedback_aggregate (singleton, payload) '
                        'VALUES (TRUE, %s::jsonb) ON CONFLICT (singleton) DO NOTHING',
                        (json.dumps(empty_aggregate()),),
                    )
                    cursor.execute(
                        'SELECT payload FROM pilot_feedback_aggregate '
                        'WHERE singleton = TRUE FOR UPDATE'
                    )
                    aggregate = add_answers(cursor.fetchone()[0], answers)
                    cursor.execute(
                        'UPDATE pilot_feedback_aggregate SET payload = %s::jsonb '
                        'WHERE singleton = TRUE', (json.dumps(aggregate),),
                    )
            return
        with sqlite3.connect(self.sqlite_path, timeout=30) as connection:
            connection.execute('BEGIN IMMEDIATE')
            connection.execute(
                'CREATE TABLE IF NOT EXISTS pilot_feedback_aggregate '
                '(singleton INTEGER PRIMARY KEY CHECK (singleton = 1), payload TEXT NOT NULL)'
            )
            row = connection.execute(
                'SELECT payload FROM pilot_feedback_aggregate WHERE singleton = 1'
            ).fetchone()
            aggregate = json.loads(row[0]) if row else empty_aggregate()
            add_answers(aggregate, answers)
            connection.execute(
                'INSERT INTO pilot_feedback_aggregate (singleton, payload) VALUES (1, ?) '
                'ON CONFLICT(singleton) DO UPDATE SET payload=excluded.payload',
                (json.dumps(aggregate),),
            )
        try:
            Path(self.sqlite_path).chmod(0o600)
        except OSError:
            pass

    def export(self, *, minimum_responses=5):
        if self.database_url:
            with closing(self._postgres_connection()) as connection, connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT to_regclass('pilot_feedback_aggregate')")
                    if cursor.fetchone()[0] is None:
                        aggregate = empty_aggregate()
                        row = None
                    else:
                        cursor.execute(
                            'SELECT payload FROM pilot_feedback_aggregate WHERE singleton = TRUE'
                        )
                        row = cursor.fetchone()
                        aggregate = row[0] if row else empty_aggregate()
        elif not Path(self.sqlite_path).exists():
            aggregate = empty_aggregate()
        else:
            with sqlite3.connect(self.sqlite_path) as connection:
                row = connection.execute(
                    'SELECT payload FROM pilot_feedback_aggregate WHERE singleton = 1'
                ).fetchone()
                aggregate = json.loads(row[0]) if row else empty_aggregate()
        if aggregate['responses'] < minimum_responses:
            return dict(
                responses=aggregate['responses'],
                status='Feedback is available only after at least five responses.',
            )
        for key in TEXT_KEYS:
            secrets.SystemRandom().shuffle(aggregate[key])
        return aggregate


RESPONSE_HEADERS = [
    (b'cache-control', b'no-store'),
    (b'referrer-policy', b'no-referrer'),
    (b'x-content-type-options', b'nosniff'),
    (b'x-frame-options', b'DENY'),
    (b'content-security-policy',
     b"default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
     b"connect-src 'self'; form-action 'none'; frame-ancestors 'none'; base-uri 'none'"),
]


async def respond(send, status, body, content_type='text/plain; charset=utf-8'):
    await send(dict(
        type='http.response.start', status=status,
        headers=RESPONSE_HEADERS + [(b'content-type', content_type.encode('ascii'))],
    ))
    await send(dict(type='http.response.body', body=body.encode('utf-8')))


class FeedbackGateway:
    """Route feedback before oTree's participant/session middleware runs."""

    def __init__(self, otree_app, *, enabled=None, store=None):
        self.otree_app = otree_app
        self.enabled = feedback_enabled() if enabled is None else enabled
        self.store = store or FeedbackStore.from_environment()

    async def __call__(self, scope, receive, send):
        if scope.get('type') != 'http' or scope.get('path') != FEEDBACK_PATH:
            await self.otree_app(scope, receive, send)
            return
        # Do not use or retain cookies, source IP, or referrer information.
        if not self.enabled or scope.get('query_string'):
            await respond(send, 404, 'Tämä palautelomake ei ole käytettävissä.')
            return
        method = scope.get('method')
        if method == 'GET':
            html = Path(__file__).with_name('pilot_feedback.html').read_text(encoding='utf-8')
            await respond(send, 200, html, 'text/html; charset=utf-8')
            return
        if method != 'POST':
            await respond(send, 405, 'Käytä palautelomaketta.')
            return
        content_type = dict(scope.get('headers', [])).get(b'content-type', b'')
        if content_type.split(b';', 1)[0].strip().lower() != b'application/json':
            await respond(send, 415, 'Lähetä palaute lomakkeella.')
            return
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            body.extend(message.get('body', b''))
            if len(body) > MAX_BODY_BYTES:
                await respond(send, 413, 'Vastaukset ovat liian pitkiä.')
                return
            if not message.get('more_body', False):
                break
        try:
            answers = validate_answers(json.loads(body))
        except (ValueError, TypeError, UnicodeDecodeError):
            await respond(send, 400, 'Tarkista vastauksesi ja yritä uudelleen.')
            return
        try:
            self.store.submit(answers)
        except Exception:
            # A traceback/request report could disclose the submitted free text.
            await respond(send, 503, 'Palautetta ei voitu tallentaa. Yritä myöhemmin uudelleen.')
            return
        await respond(send, 200, 'Kiitos. Anonyymi palautteesi on tallennettu.')


if __name__ == '__main__':
    if sys.argv[1:] != ['export']:
        raise SystemExit('Usage: python anonymous_feedback.py export')
    print(json.dumps(FeedbackStore.from_environment().export(), indent=2, ensure_ascii=False))

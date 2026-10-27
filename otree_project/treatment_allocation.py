"""Persistent, size-stratified treatment allocation for completed Block-1 pools.

Each four-pool block contains two recovery and two persistence assignments.
Assignments are consumed only at the Block-2 entry wait page. Pool UIDs make
retries idempotent. The audit export contains consumed allocations only.

PostgreSQL deployments keep the ledger in DATABASE_URL. Local deployments use
a separate SQLite file so allocation transactions cannot deadlock against an
open oTree transaction. Back up that ledger with the local research database.
"""

import argparse
from contextlib import closing
import csv
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys


RECOVERY = 'recovery'
PERSISTENCE = 'persistence'
POOL_SIZES = (5, 10, 15)
BLOCK_SIZE = 4
LOCK_ID = 823740192
AUDIT_COLUMNS = (
    'namespace', 'pool_uid', 'pool_size', 'sequence_index', 'block_number',
    'block_position', 'treatment', 'randomization_block_uid',
)


class AllocationStore:
    def __init__(self, *, database_url=None, sqlite_path=None):
        self.database_url = database_url
        if database_url and not database_url.startswith(('postgres://', 'postgresql://')):
            raise ValueError('The allocation DATABASE_URL must be PostgreSQL.')
        self.sqlite_path = Path(sqlite_path or os.environ.get(
            'TREATMENT_ALLOCATION_DB',
            str(Path(__file__).with_name('treatment_allocation.sqlite3')),
        ))

    @classmethod
    def from_environment(cls):
        database_url = os.environ.get('DATABASE_URL')
        if database_url and database_url.startswith('sqlite:'):
            database_url = None
        return cls(database_url=database_url)

    @staticmethod
    def _schema(cursor):
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS study_treatment_blocks ('
            'namespace TEXT NOT NULL, pool_size INTEGER NOT NULL, '
            'block_number INTEGER NOT NULL, assignment_order TEXT NOT NULL, '
            'PRIMARY KEY (namespace, pool_size, block_number))'
        )
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS study_treatment_allocations ('
            'namespace TEXT NOT NULL, pool_uid TEXT NOT NULL, '
            'pool_size INTEGER NOT NULL, sequence_index INTEGER NOT NULL, '
            'block_number INTEGER NOT NULL, block_position INTEGER NOT NULL, '
            'treatment TEXT NOT NULL, PRIMARY KEY (namespace, pool_uid), '
            'UNIQUE (namespace, pool_size, sequence_index))'
        )

    def assign_pools(self, namespace, pools):
        """Atomically obtain assignments for [(pool_uid, pool_size), ...]."""
        if not isinstance(namespace, str) or not namespace.strip() or len(namespace) > 120:
            raise ValueError('A nonempty study allocation namespace is required.')
        pools = list(pools)
        if len({uid for uid, _ in pools}) != len(pools):
            raise ValueError('A matching pool may occur only once in an allocation batch.')
        if any(size not in POOL_SIZES or not uid for uid, size in pools):
            raise ValueError('Production matching pools must contain 5, 10, or 15 people.')
        if self.database_url:
            import psycopg2
            with closing(psycopg2.connect(self.database_url)) as connection, connection:
                with connection.cursor() as cursor:
                    # Serialize schema creation and every allocation transaction.
                    cursor.execute('SELECT pg_advisory_xact_lock(%s)', (LOCK_ID,))
                    self._schema(cursor)
                    return self._assign(cursor, '%s', namespace, pools)
        self.sqlite_path.touch(mode=0o600, exist_ok=True)
        self.sqlite_path.chmod(0o600)
        with closing(sqlite3.connect(self.sqlite_path, timeout=30)) as connection, connection:
            connection.execute('BEGIN IMMEDIATE')
            cursor = connection.cursor()
            self._schema(cursor)
            return self._assign(cursor, '?', namespace, pools)

    def _assign(self, cursor, placeholder, namespace, pools):
        def execute(statement, values=()):
            cursor.execute(statement.replace('?', placeholder), values)

        assigned = {}
        for pool_uid, pool_size in pools:
            execute(
                'SELECT pool_size, sequence_index, block_number, block_position, treatment '
                'FROM study_treatment_allocations WHERE namespace=? AND pool_uid=?',
                (namespace, pool_uid),
            )
            row = cursor.fetchone()
            if row:
                if row[0] != pool_size:
                    raise RuntimeError('A stored matching pool changed size.')
            else:
                execute(
                    'SELECT COALESCE(MAX(sequence_index),0) '
                    'FROM study_treatment_allocations WHERE namespace=? AND pool_size=?',
                    (namespace, pool_size),
                )
                sequence_index = cursor.fetchone()[0] + 1
                block_number = (sequence_index - 1) // BLOCK_SIZE + 1
                block_position = (sequence_index - 1) % BLOCK_SIZE + 1
                execute(
                    'SELECT assignment_order FROM study_treatment_blocks '
                    'WHERE namespace=? AND pool_size=? AND block_number=?',
                    (namespace, pool_size, block_number),
                )
                block = cursor.fetchone()
                if block:
                    order = json.loads(block[0])
                else:
                    order = [RECOVERY, RECOVERY, PERSISTENCE, PERSISTENCE]
                    secrets.SystemRandom().shuffle(order)
                    execute(
                        'INSERT INTO study_treatment_blocks '
                        '(namespace,pool_size,block_number,assignment_order) VALUES (?,?,?,?)',
                        (namespace, pool_size, block_number, json.dumps(order)),
                    )
                if len(order) != BLOCK_SIZE or sorted(order) != sorted(
                    [RECOVERY, RECOVERY, PERSISTENCE, PERSISTENCE]
                ):
                    raise RuntimeError('The stored treatment-allocation block is invalid.')
                treatment = order[block_position - 1]
                row = (pool_size, sequence_index, block_number, block_position, treatment)
                execute(
                    'INSERT INTO study_treatment_allocations '
                    '(namespace,pool_uid,pool_size,sequence_index,block_number,'
                    'block_position,treatment) VALUES (?,?,?,?,?,?,?)',
                    (namespace, pool_uid, *row),
                )
            assigned[pool_uid] = dict(
                namespace=namespace, pool_uid=pool_uid, pool_size=row[0],
                sequence_index=row[1], block_number=row[2], block_position=row[3],
                treatment=row[4],
                randomization_block_uid=f'{namespace}:size-{row[0]}:block-{row[2]}',
            )
        return assigned

    def export(self, namespace):
        """Read consumed allocations without exposing unused block positions."""
        query = (
            'SELECT namespace,pool_uid,pool_size,sequence_index,block_number,'
            'block_position,treatment FROM study_treatment_allocations '
            'WHERE namespace={} ORDER BY pool_size,sequence_index'
        )
        if self.database_url:
            import psycopg2
            with closing(psycopg2.connect(self.database_url)) as connection, connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT to_regclass('study_treatment_allocations')")
                    if cursor.fetchone()[0] is None:
                        return []
                    cursor.execute(query.format('%s'), (namespace,))
                    rows = cursor.fetchall()
        elif not self.sqlite_path.exists():
            return []
        else:
            with closing(sqlite3.connect(self.sqlite_path)) as connection:
                exists = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name='study_treatment_allocations'"
                ).fetchone()
                if not exists:
                    return []
                rows = connection.execute(query.format('?'), (namespace,)).fetchall()
        return [dict(zip(AUDIT_COLUMNS, (*row,
            f'{row[0]}:size-{row[2]}:block-{row[4]}')))
            for row in rows]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['export'])
    parser.add_argument('--namespace', required=True)
    args = parser.parse_args()
    writer = csv.DictWriter(sys.stdout, fieldnames=AUDIT_COLUMNS)
    writer.writeheader()
    writer.writerows(AllocationStore.from_environment().export(args.namespace))

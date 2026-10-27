"""Allocation tests use temporary ledgers, never the study database."""

from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from treatment_allocation import AllocationStore, PERSISTENCE, RECOVERY


def consume_in_process(arguments):
    ledger_path, pool_uid = arguments
    return AllocationStore(sqlite_path=ledger_path).assign_pools(
        'concurrency-test', [(pool_uid, 5)],
    )[pool_uid]


class AllocationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'allocation.sqlite3'
        self.store = AllocationStore(sqlite_path=self.path)

    def tearDown(self):
        self.directory.cleanup()

    def test_balance_and_separate_size_strata(self):
        for size in (5, 10, 15):
            for number in range(12):
                self.store.assign_pools('production', [(f'{size}-{number}', size)])
        grouped = defaultdict(list)
        for row in self.store.export('production'):
            grouped[(row['pool_size'], row['block_number'])].append(row)
        self.assertEqual(len(grouped), 9)
        for rows in grouped.values():
            self.assertEqual(Counter(row['treatment'] for row in rows),
                             {RECOVERY: 2, PERSISTENCE: 2})
            self.assertEqual(sorted(row['block_position'] for row in rows), [1, 2, 3, 4])

    def test_restarts_and_duplicate_requests_do_not_consume_twice(self):
        first = self.store.assign_pools('production', [('cohort-1-pool-1', 5)])
        restarted = AllocationStore(sqlite_path=self.path)
        self.assertEqual(first, restarted.assign_pools(
            'production', [('cohort-1-pool-1', 5)]))
        self.assertEqual(len(restarted.export('production')), 1)
        second = restarted.assign_pools('production', [('cohort-2-pool-1', 5)])
        self.assertEqual(second['cohort-2-pool-1']['sequence_index'], 2)

    def test_namespaces_isolate_production_and_demo(self):
        self.store.assign_pools('production', [('same-uid', 5)])
        demo = self.store.assign_pools('development', [('same-uid', 5)])
        self.assertEqual(demo['same-uid']['sequence_index'], 1)
        self.assertEqual(len(self.store.export('production')), 1)

    def test_transaction_rolls_back_entire_invalid_batch(self):
        self.store.assign_pools('production', [('existing', 5)])
        with self.assertRaises(RuntimeError):
            self.store.assign_pools('production', [('new', 10), ('existing', 15)])
        self.assertEqual(len(self.store.export('production')), 1)

    def test_incomplete_block_export_hides_future_positions(self):
        self.store.assign_pools('production', [('one', 15)])
        rows = self.store.export('production')
        self.assertEqual(len(rows), 1)
        self.assertNotIn('assignment_order', rows[0])
        self.assertEqual(rows[0]['randomization_block_uid'], 'production:size-15:block-1')

    def test_ledger_is_private(self):
        self.store.assign_pools('production', [('one', 5)])
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)

    def test_concurrent_processes_consume_each_position_once(self):
        with ProcessPoolExecutor(max_workers=4) as executor:
            rows = list(executor.map(consume_in_process,
                [(str(self.path), f'pool-{number}') for number in range(24)]))
        self.assertEqual(sorted(row['sequence_index'] for row in rows), list(range(1, 25)))
        groups = defaultdict(list)
        for row in rows:
            groups[row['block_number']].append(row['treatment'])
        for treatments in groups.values():
            self.assertEqual(Counter(treatments), {RECOVERY: 2, PERSISTENCE: 2})


class MetadataRecoveryTests(unittest.TestCase):
    def test_partial_metadata_copies_are_recovered_without_redrawing(self):
        from block2_reversal import restore_allocation_metadata
        metadata = dict(treatment=RECOVERY, block_number=1, pool_size=5)
        participants = [SimpleNamespace(vars=dict(
            matching_pool_id=1, treatment=RECOVERY,
            randomization_stratum=1, matching_pool_size=5,
        )) for _ in range(5)]
        players = [SimpleNamespace(participant=participant) for participant in participants]
        subsession = SimpleNamespace(session=SimpleNamespace(vars=dict(
            treatment_allocation_by_pool={1: metadata})))
        restore_allocation_metadata(subsession, players)
        self.assertTrue(all(p.vars['treatment_allocation'] == metadata for p in participants))
        subsession.session.vars.pop('treatment_allocation_by_pool')
        for participant in participants[1:]:
            participant.vars.pop('treatment_allocation')
        restore_allocation_metadata(subsession, players)
        self.assertEqual(subsession.session.vars['treatment_allocation_by_pool'], {1: metadata})
        self.assertTrue(all(p.vars['treatment_allocation'] == metadata for p in participants))

    def test_conflicting_metadata_is_rejected(self):
        from block2_reversal import restore_allocation_metadata
        participant = SimpleNamespace(vars=dict(
            matching_pool_id=1, treatment=PERSISTENCE,
            randomization_stratum=1, matching_pool_size=5,
        ))
        subsession = SimpleNamespace(session=SimpleNamespace(vars=dict(
            treatment_allocation_by_pool={1: dict(
                treatment=RECOVERY, block_number=1, pool_size=5)})))
        with self.assertRaises(RuntimeError):
            restore_allocation_metadata(subsession, [SimpleNamespace(participant=participant)])


@unittest.skipUnless(os.environ.get('ALLOCATION_TEST_POSTGRES_URL'),
                     'Set an isolated PostgreSQL test database to exercise PostgreSQL locking.')
class PostgresAllocationTests(unittest.TestCase):
    def test_idempotency_and_completed_block_balance(self):
        import uuid
        store = AllocationStore(database_url=os.environ['ALLOCATION_TEST_POSTGRES_URL'])
        namespace = f'isolated-test-{uuid.uuid4()}'
        pools = [(f'pool-{number}', 5) for number in range(4)]
        rows = store.assign_pools(namespace, pools)
        self.assertEqual(Counter(row['treatment'] for row in rows.values()),
                         {RECOVERY: 2, PERSISTENCE: 2})
        self.assertEqual(rows, store.assign_pools(namespace, pools))


if __name__ == '__main__':
    unittest.main()

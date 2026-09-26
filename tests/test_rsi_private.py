"""RSI arithmetic, native engine parity, and private gates on invented archives."""
from contextlib import closing
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
import json
import os
from pathlib import Path
import sqlite3

import pytest

from tidelab import rsi_private as rsi
from tidelab import historical_batch as batch
from tidelab.domain import canonical_json, parse_utc, isoformat_utc
from tidelab.historical_input import FIELDS
from tidelab.package_lean_parity import run_parity, validate_input
from tidelab.storage import TideStore
from tidelab.strategy_batch import CloseSeries, _boolean, parse_package, replay_package, UnsupportedPackage

ROOT = Path(__file__).resolve().parents[1]

def record():
    return batch.read(ROOT / 'research/examples/strategy-batch-synthetic-record-v1.json')

def fixture(values):
    return {'kind': 'tidelab_synthetic', 'interval_seconds': 3600, 'bars': [
        {'start_utc': isoformat_utc(parse_utc('2026-01-01T00:00:00Z') + timedelta(hours=i)),
         'open': str(v + Decimal('2')), 'close': str(v)} for i, v in enumerate(map(Decimal, values))]}


def test_rsi_golden_seeding_boundaries_and_no_future_dependence():
    assert CloseSeries([Decimal(10)] * 40).rsi14 == [100] * 40
    assert CloseSeries(map(Decimal, range(1, 41))).rsi14 == [100] * 40
    assert CloseSeries(map(Decimal, range(40, 0, -1))).rsi14[1:] == [0] * 39
    # Fourteen deltas: seven +3, seven -7 => mean gain1.5/loss3.5 => RSI30.
    values = [Decimal(100)]
    for delta in [3] * 7 + [-7] * 7 + [14]: values.append(values[-1] + delta)
    series = CloseSeries(values)
    assert abs(series.rsi14[14] - 30) < Decimal('1e-24')
    # Wilder's next step => gains(19.5+14)/14, losses45.5/14.
    assert abs(series.rsi14[15] - Decimal(3350) / 79) < Decimal('1e-24')
    assert CloseSeries(values + [Decimal('99999')]).rsi14[:len(values)] == series.rsi14
    candidate = rsi.package(record())
    exact = CloseSeries([Decimal(1)]); exact.rsi14 = [Decimal(30)]
    assert not _boolean(candidate['rule']['entry'], exact, 0)
    exact.rsi14 = [Decimal(70)]
    assert not _boolean(candidate['rule']['exit'], exact, 0)
    exact.rsi14 = [Decimal('29.999')]
    assert _boolean(candidate['rule']['entry'], exact, 0)
    exact.rsi14 = [Decimal('70.001')]
    assert _boolean(candidate['rule']['exit'], exact, 0)


@pytest.mark.parametrize('change', ['v1', 'period', 'lag', 'boolean'])
def test_only_versioned_exact_rsi_operator(change):
    candidate = rsi.package(record())
    if change == 'v1': candidate['schema_version'] = 1
    else: candidate['rule']['entry']['left'][{'boolean': 'lag'}.get(change, change)] = {'period': 13, 'lag': 1, 'boolean': False}[change]
    with pytest.raises(UnsupportedPackage): parse_package(candidate, record())


@pytest.mark.skipif(not os.environ.get('TIDELAB_LEAN_ROOT'), reason='actual pinned LEAN CI')
@pytest.mark.parametrize('case', ['wave', 'flat', 'tiny_loss', 'stress', 'boundary30', 'boundary70', 'scored', 'scored_stress'])
def test_rsi_actual_native_lean(tmp_path, case):
    values = ([100, 103, 96] + [96] * 38 if case == 'boundary30' else
              [100, 107, 104] + [104] * 38 if case == 'boundary70' else
              [100] * 40 if case == 'flat' else
              [Decimal('100') - Decimal(i) / Decimal('100000000') for i in range(40)] if case == 'tiny_loss' else
              list(range(150, 90, -1)) + list(range(90, 170)) + list(range(170, 110, -1)))
    if case.startswith('scored'): values = [100] * 336 + values
    candidate, rec, bars = rsi.package(record()), record(), fixture(values)
    for name, value in [('package', candidate), ('record', rec), ('bars', bars)]: batch.write(tmp_path / (name + '.json'), value)
    result = run_parity(tmp_path / 'package.json', tmp_path / 'record.json', tmp_path / 'bars.json',
                        Path(os.environ['TIDELAB_LEAN_ROOT']), os.environ.get('TIDELAB_DOTNET', 'dotnet'), tmp_path / 'attempt',
                        cost=rsi.COSTS['stress' if 'stress' in case else 'baseline'],
                        score_start=336 if case.startswith('scored') else 0)
    assert result['status'] == 'matched', result


def invented_archive(tmp_path, monkeypatch):
    monkeypatch.setattr(rsi, 'ROOT', tmp_path)
    monkeypatch.setattr(rsi, 'gate', lambda _: 'a' * 40)
    monkeypatch.setattr(rsi, 'authority', record)
    (tmp_path / 'data/strategy_intake').mkdir(parents=True)
    base = tmp_path / 'data/okx'; base.mkdir()
    database = base / 'research.sqlite3'; TideStore(database).initialize()
    archives = {}
    with sqlite3.connect(database) as db:
        for market in rsi.MARKETS:
            rows = []
            for i in range(rsi.ROWS):
                when = parse_utc(rsi.FIRST) + timedelta(hours=i)
                stamp = isoformat_utc(when); period = (when + timedelta(hours=8)).strftime('%Y-%m')
                name = f"{market.removeprefix('okx:')}-candlesticks-{period}.zip"
                if name not in archives:
                    raw = ('Invented archive bytes, no downloaded data:' + name).encode()
                    (base / name).write_bytes(raw); archives[name] = batch.digest(raw)
                price = str(100 + abs((i % 160) - 80))
                payload = canonical_json(dict(open=price, close=price, high=price, low=price, volume='100'))
                native = canonical_json(dict(archive_period=period, archive_sha256=archives[name], minute_rows=60))
                rows.append((f'{market}-{i}', 1, 'okx', market, 'bar', stamp, stamp, rsi.SOURCE, 3600, 1, payload, native))
            db.executemany(f"INSERT INTO market_events ({','.join(FIELDS)}) VALUES ({','.join('?' for _ in FIELDS)})", rows)
        # Outside-window invalid payload must never be parsed.
        row = list(rows[-1]); row[0] = 'outside'; row[5] = rsi.END; row[10] = 'INVALID OUTSIDE WINDOW'
        db.execute(f"INSERT INTO market_events ({','.join(FIELDS)}) VALUES ({','.join('?' for _ in FIELDS)})", row)
    return database


def test_full_private_route_uses_invented_archives_once(tmp_path, monkeypatch):
    invented_archive(tmp_path, monkeypatch)
    rsi.initialize('test')
    original = rsi.rows_for
    def after_reservation(db, market):
        assert rsi.canonical_registry().access(rsi.GRANT, 'snapshot')
        return original(db, market)
    monkeypatch.setattr(rsi, 'rows_for', after_reservation)
    assert rsi.prepare('test')['status'] == 'prepared'
    import subprocess, sys
    snapshot = rsi.study() / 'snapshot.sqlite3'
    observed = subprocess.check_output([sys.executable, '-c', 'from pathlib import Path; from hashlib import sha256; import sys; print(sha256(Path(sys.argv[1]).read_bytes()).hexdigest())', str(snapshot)], text=True).strip()
    assert observed == batch.read(rsi.study() / 'prepared.json')['snapshot_file_sha256']
    assert not snapshot.with_name(snapshot.name + '-wal').exists()
    with pytest.raises(sqlite3.IntegrityError): rsi.prepare('test')
    assert rsi.execute('test') == {'status': 'reviewed', 'jobs': 30, 'results_private': True}
    summary = batch.read(rsi.study() / 'attempt/summary.json')
    assert len(summary['jobs']) == 30 and all(x['status'] == 'completed' for x in summary['jobs'])
    assert all(x['metrics']['evidence'] == 'descriptive_private_historical_scenario' for x in summary['jobs'])
    assert batch.recover(rsi.study() / 'attempt', rsi.registry_path()) == summary
    with closing(sqlite3.connect(rsi.registry_path())) as db:
        assert db.execute('SELECT COUNT(*) FROM trial_attempts').fetchone()[0] == 30
        with pytest.raises(sqlite3.IntegrityError): db.execute("DELETE FROM research_access")
    with pytest.raises(sqlite3.IntegrityError): rsi.execute('test')
    # Established store cannot be silently recreated.
    rsi.registry_path().rename(rsi.registry_path().with_suffix('.preserved'))
    with pytest.raises(ValueError, match='canonical_program_store_missing'): rsi.canonical_registry()
    with pytest.raises(ValueError, match='already_initialized'): rsi.initialize('test')


def test_failed_snapshot_stays_consumed(tmp_path, monkeypatch):
    monkeypatch.setattr(rsi, 'ROOT', tmp_path)
    monkeypatch.setattr(rsi, 'gate', lambda _: 'a' * 40)
    monkeypatch.setattr(rsi, 'authority', record)
    (tmp_path / 'data/strategy_intake').mkdir(parents=True)
    rsi.initialize('test')
    with pytest.raises(sqlite3.OperationalError): rsi.prepare('test')
    assert (rsi.study() / 'preparation-failed.json').exists()
    with pytest.raises(sqlite3.IntegrityError): rsi.prepare('test')
    with pytest.raises(ValueError, match='not_prepared'): rsi.execute('test')


def test_policy_and_disposition_precedence():
    rec = record(); descriptor = {'test': 'invented'}
    policy = rsi.ApprovedRSIPolicy(rec, descriptor)
    plan = rsi.make_plan(descriptor, rec); policy.preflight(plan, descriptor)
    altered = deepcopy(plan); altered['partitions']['validation'] = {'start': rsi.END}
    with pytest.raises(ValueError, match='outside_approved'): policy.preflight(altered, descriptor)
    candidate = rsi.package(rec); candidate['rule']['target_fraction'] = '0.5'
    with pytest.raises(ValueError, match='outside_selected'): policy.package(candidate, rec)
    jobs = [dict(index=i, status='completed', metrics=dict(net_return='0.1' if i % 6 < 2 else '0.05', round_trips=20, max_drawdown='0.15')) for i in range(30)]
    jobs[0]['metrics']['round_trips'] = 19
    jobs[6]['metrics']['net_return'] = '-0.01'
    jobs[17]['status'] = 'failed'
    verdict = rsi.review({'jobs': jobs})
    assert [x['status'] for x in verdict['markets']] == ['inconclusive', 'not_nominated', 'incomplete', 'eligible_for_deeper_review', 'eligible_for_deeper_review']
    assert verdict['status'] == 'incomplete' and verdict['eligibility_provisional']
    assert not verdict['automatic_promotion']

@pytest.mark.parametrize('damage', ['gap', 'duplicate', 'source', 'unclosed', 'nan', 'provenance'])
def test_private_rows_reject_bad_inputs(monkeypatch, damage):
    monkeypatch.setattr(rsi, 'ROWS', 2)
    rows = []
    for i in range(2):
        when = isoformat_utc(parse_utc(rsi.FIRST) + timedelta(hours=i))
        rows.append(dict(zip(FIELDS, [str(i), 1, 'okx', rsi.MARKETS[0], 'bar', when, when, rsi.SOURCE,
                                     3600, 1, canonical_json(dict(open='1', high='1', low='1', close='1', volume='1')),
                                     canonical_json(dict(archive_period='2023-12', archive_sha256='a'*64, minute_rows=60))])))
    assert len(rsi.validate_rows(rows, rsi.MARKETS[0])[0]) == 2
    if damage == 'gap': rows.pop()
    if damage == 'duplicate': rows[1]['event_time_utc'] = rows[0]['event_time_utc']
    if damage == 'source': rows[0]['source'] = 'wrong'
    if damage == 'unclosed': rows[0]['closed'] = 0
    if damage == 'nan': rows[0]['payload_json'] = canonical_json(dict(open='NaN', high='1', low='1', close='1', volume='1'))
    if damage == 'provenance': rows[0]['native_json'] = canonical_json(dict(archive_period='2024-01', archive_sha256='a'*64, minute_rows=60))
    with pytest.raises(ValueError): rsi.validate_rows(rows, rsi.MARKETS[0])


def test_current_terms_required_before_initialization(monkeypatch):
    monkeypatch.setattr(rsi, 'integrated_head', lambda: 'a' * 40)
    monkeypatch.setattr(rsi, 'authority', record)
    with pytest.raises(ValueError, match='current_day_terms'): rsi.gate('2000-01-01')

// Candidate apparatus for Faraday's existing numbered runner.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const requirements = [
  'VEDIC_PYTHON', 'VEDIC_COMPILER', 'VEDIC_FACTORY_REPO',
  'VEDIC_ORIENT_ARCHIVE', 'VEDIC_ORIENT_BUILD_RECEIPT',
];

const point = (longitude, latitude) => ({ longitude, latitude });

function run(phrase, values, file) {
  writeFileSync(file, JSON.stringify(values));
  const result = spawnSync(process.env.VEDIC_PYTHON, [
    process.env.VEDIC_COMPILER, phrase, '--input', file,
    '--factory-repo', process.env.VEDIC_FACTORY_REPO,
    '--archive', process.env.VEDIC_ORIENT_ARCHIVE,
    '--build-receipt', process.env.VEDIC_ORIENT_BUILD_RECEIPT,
  ], { encoding: 'utf8', timeout: 40_000 });
  if (result.error) throw result.error;
  return { exit: result.status, receipt: JSON.parse(result.stdout) };
}

export default async function experiment() {
  for (const name of requirements) assert.ok(process.env[name], name);
  const root = mkdtempSync(join(tmpdir(), 'faraday-vedic-orient-'));
  const request = join(root, 'coords.json');
  const input = (a, b, unit = 'degrees') => ({
    crs: 'WGS84', unit, point_a: a, point_b: b,
  });
  const observed = {};
  const failure = [];
  const confirm = (name, actual, predicate) => {
    observed[name] = actual;
    if (!predicate(actual)) failure.push(name);
  };
  try {
    for (const [name, phrase, a, b, degrees, direction] of [
      ['equator', 'ORIENT', point(0, 0), point(1, 0), 1, 90],
      ['antimeridian', 'measure distance and bearing', point(179, 0), point(-179, 0), 2, 90],
      ['meridian', 'orient', point(20, 10), point(20, 13), 3, 0],
    ]) {
      const result = run(phrase, input(a, b), request);
      const output = result.receipt.package_execution?.pattern.output;
      const expected = { distance_km: 6378.137 * degrees * (Math.PI / 180), initial_bearing_deg: direction };
      confirm(name, {
        exit: result.exit, state: result.receipt.state, command_id: result.receipt.plan?.command_id,
        components: result.receipt.plan?.components, output, expected,
        pattern_sha256: result.receipt.package_execution?.pattern_sha256,
      }, (x) => x.exit === 0 && x.state === 'EXECUTED_PRIVATE_PACKAGE'
        && x.command_id === 'GG2050-VEDIC-000006'
        && x.components.join(',') === 'GG2050-VEDIC-000001,GG2050-VEDIC-000005'
        && Math.abs(x.output.distance_km - expected.distance_km) <= 1e-9
        && Math.abs(x.output.initial_bearing_deg - direction) <= 1e-9);
    }
    for (const [name, phrase, data, reason, packageReason] of [
      ['coincident', 'ORIENT', input(point(3, 4), point(3, 4)), 'PACKAGE_REFUSED', 'UPSTREAM_RESULT_REFUSED'],
      ['antipodal', 'ORIENT', input(point(0, 0), point(180, 0)), 'PACKAGE_REFUSED', 'UPSTREAM_RESULT_REFUSED'],
      ['polar_origin', 'ORIENT', input(point(0, 90), point(1, 20)), 'PACKAGE_REFUSED', 'UPSTREAM_RESULT_REFUSED'],
      ['wrong_units', 'ORIENT', input(point(0, 0), point(1, 0), 'radians'), 'PACKAGE_REFUSED', 'INPUT_UNITS'],
      ['missing_coordinate', 'ORIENT', input(point(0, 0), { longitude: 1 }), 'PACKAGE_REFUSED', 'FIELDS'],
      ['ambiguous_term', 'AREA', {}, 'AMBIGUOUS_COMMAND'],
      ['unadmitted', 'CHECK POWER CAP', {}, 'PACKAGE_NOT_ADMITTED'],
    ]) {
      const result = run(phrase, data, request);
      confirm(name, result, x => x.exit === 2 && x.receipt.state === 'REFUSED'
        && x.receipt.reason === reason
        && x.receipt.package_reason === packageReason);
    }
  } finally {
    rmSync(root, { recursive: true });
  }
  return {
    did: 'Fired the existing VEDIC ORIENT package on three independently calculable spherical cases and seven refusals.',
    observed: JSON.stringify({ cases: observed, failed: failure }),
    shows: 'One existing command drives two canonical geodesy operations through the byte-pinned package. The cases exercise its declared units and scope.',
    result: failure.length ? 'REFUTED' : 'CONFIRMED',
  };
}

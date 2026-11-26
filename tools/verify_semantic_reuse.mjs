// Replay selected compiled Stars functions and the original firm-capacity engine.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const [stars, engine] = process.argv.slice(2);
assert.ok(stars && engine, 'Usage: node tools/verify_semantic_reuse.mjs STARS_REPO ENGINE_REPO');
const starsCommit = '1cf9c7530c7d287ccf9b3cffd70f693fb83c8402';
const engineCommit = '7c2a7b42905674fdcd3aa4bb50af14bc352a7747';
const gitFile = (repo, commit, path, blob) => {
  const raw = execFileSync('git', ['-C', repo, 'show', `${commit}:${path}`], {
    env: { ...process.env, GIT_NO_LAZY_FETCH: '1', GIT_NO_REPLACE_OBJECTS: '1' },
  });
  const actual = createHash('sha1').update(`blob ${raw.length}\0`).update(raw).digest('hex');
  assert.equal(actual, blob);
  return raw;
};

const root = mkdtempSync(join(tmpdir(), 'vedic-semantic-reuse-'));
const load = async (name, raw) => {
  const file = join(root, name);
  writeFileSync(file, raw);
  return import(pathToFileURL(file));
};
try {
  const libraryBlob = '0390a4ecbf9d5c7dd171fbd923a58f4be15f05fb';
  const library = gitFile(stars, starsCommit, 'library/standalone.mjs', libraryBlob).toString('utf8');
  const exportCount = [...library.matchAll(/^export const f\d+_/gm)].length;
  assert.equal(exportCount, 766);
  const compiledSymbols = ['f8767_representativePoint', 'f8768_voltagesKv', 'f5197_createGeoJSONCircle'];
  const excerpts = compiledSymbols.map(name => {
    const start = library.indexOf(`\nexport const ${name} = function `);
    assert.ok(start >= 0);
    const end = library.indexOf('\n// Family #', start + 1);
    const excerpt = library.slice(start + 1, end).trimEnd();
    assert.ok(excerpt.endsWith('};') && !excerpt.includes('\nexport '));
    return excerpt;
  });
  const compiled = await load('compiled-excerpts.mjs', excerpts.join('\n'));
  const geodesy = await load('geodesy.mjs', gitFile(engine, engineCommit, 'engine/v9-geodesy.js',
    '14023f06d4ef2ea806437863bd35dee954c46b11'));
  const firm = await load('firm.mjs', gitFile(engine, engineCommit, 'engine/firm-capacity.js',
    '8c87c71f29cc27970305c3109efeb22b66fbe568'));

  const checks = [
    [compiled.f8767_representativePoint, geodesy.representativePoint, null, null],
    [compiled.f8767_representativePoint, geodesy.representativePoint,
      { type: 'Point', coordinates: [-2, 52, 15] }, [-2, 52]],
    [compiled.f8767_representativePoint, geodesy.representativePoint,
      { type: 'Polygon', coordinates: [[[0, 0], [8, 0], [0, 8], [0, 0]]] }, [2, 2]],
    [compiled.f8768_voltagesKv, geodesy.voltagesKv, null, []],
    [compiled.f8768_voltagesKv, geodesy.voltagesKv, { kv: '132;33;132' }, [132, 33]],
    [compiled.f8768_voltagesKv, geodesy.voltagesKv, { KV: '33;0', VOLTAGE: '33000;11000' }, [33, 11]],
  ];
  for (const [a, b, value, expected] of checks) {
    assert.deepEqual(a(value), expected);
    assert.deepEqual(b(value), expected);
  }

  const vertex = compiled.f5197_createGeoJSONCircle(0, 80, 500).features[0].geometry.coordinates[0][0];
  const compiledRadiusKm = geodesy.distanceKm(0, 80, ...vertex);
  assert.ok(Math.abs(compiledRadiusKm - 500) > 1);

  const boundary = firm.assessAgainstFirm({ units: [20, 15], demandMva: 15 });
  assert.deepEqual([boundary.withinFirm, boundary.firmMva, boundary.shortfallMva], [true, 15, 0]);
  const excess = firm.assessAgainstFirm({ units: [20, 15], demandMva: 16 });
  assert.deepEqual([excess.withinFirm, excess.withinInstalled, excess.shortfallMva], [false, true, 1]);
  const single = firm.assessAgainstFirm({ units: [20], demandMva: 10 });
  assert.deepEqual([single.withinFirm, single.firmMva, single.utilisationOfFirm], [false, 0, Infinity]);
  assert.throws(() => firm.assessAgainstFirm({ units: [], demandMva: 10 }));
  assert.throws(() => firm.assessAgainstFirm({ units: [20] }));

  console.log(JSON.stringify({
    starsCommit, engineCommit, libraryBlob, exportCount,
    existingCompiledMatches: ['GG2050-VEDIC-000002', 'GG2050-VEDIC-000003'],
    compiledParityCases: checks.length,
    withheldGeodesicAlias: { familyId: 5197, requestedRadiusKm: 500, actualVertexDistanceKm: compiledRadiusKm },
    firmCapacityCases: 5, zeroFirmUtilisation: 'Infinity',
    packageAdmissions: 0,
  }, null, 2));
} finally {
  rmSync(root, { recursive: true });
}

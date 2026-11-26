/** Static Acorn enrichment for pinned canonical files. Input source is never evaluated. */
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const requires = createRequire(resolve(process.argv[2], 'package.json'));
const acorn = requires('acorn');
const walk = requires('acorn-walk');
const files = JSON.parse(readFileSync(0, 'utf8'));

function groups(file) {
  if (!file.path.endsWith('.html')) return [{ code: file.text, line: 0 }];
  const units = [];
  for (const block of file.text.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi)) {
    if (/\bsrc\s*=/i.test(block[1])) continue;
    const mime = block[1].match(/\btype\s*=\s*["']?([^"'\s>]+)/i)?.[1];
    if (mime && !/^(module|text\/javascript|application\/javascript)$/i.test(mime)) continue;
    const start = block.index + block[0].indexOf('>') + 1;
    units.push({ code: block[2], line: file.text.slice(0, start).split('\n').length - 1 });
  }
  return units;
}

function declaredNames(node) {
  if (node?.id?.name) return [node.id.name];
  if (node?.type !== 'VariableDeclaration') return [];
  return node.declarations.map(item => item.id.name).filter(Boolean);
}

function parseUnit(unit, result) {
  let tree;
  const comments = [];
  for (const sourceType of ['module', 'script']) {
    try {
      comments.length = 0;
      tree = acorn.parse(unit.code, {
        ecmaVersion: 'latest', sourceType, locations: true, onComment: comments,
        allowHashBang: true, allowReturnOutsideFunction: true, allowAwaitOutsideFunction: true,
      });
      break;
    } catch (error) {
      if (sourceType === 'script') result.issues.push({ line: unit.line + 1, type: error.name });
    }
  }
  if (!tree) return;

  const exported = new Set();
  const line = node => node.loc.start.line + unit.line;
  const spelling = node => unit.code.slice(node.start, node.end);
  for (const statement of tree.body) {
    const isExport = statement.type === 'ExportNamedDeclaration' || statement.type === 'ExportDefaultDeclaration';
    if (isExport) {
      declaredNames(statement.declaration).forEach(name => exported.add(name));
      for (const item of statement.specifiers ?? []) {
        if (item.local?.name) exported.add(item.local.name);
        result.exports.push(item.exported?.name ?? item.exported?.value);
      }
      if (statement.type === 'ExportDefaultDeclaration') result.exports.push('default');
      else result.exports.push(...declaredNames(statement.declaration));
    }
    if (statement.source?.value && /^(Import|Export)/.test(statement.type)) {
      result.imports.push({ module: statement.source.value, line: line(statement) });
    }
    const declaration = isExport ? statement.declaration : statement;
    if (declaration?.type === 'VariableDeclaration' && declaration.kind === 'const') {
      for (const item of declaration.declarations) {
        if (item.id.type !== 'Identifier') continue;
        result.constants.push({ name: item.id.name, line: line(item), exported: isExport,
          initializer_kind: item.init?.type ?? null,
          literal_json: item.init?.type === 'Literal' && !item.init.regex && !item.init.bigint
            ? JSON.stringify(item.init.value) : null });
      }
    }
  }

  walk.fullAncestor(tree, (node, _state, ancestors) => {
    const parent = ancestors.at(-2);
    if (node.type === 'ThrowStatement') {
      const context = ancestors.slice(0, -1).reverse().find(item => item.type === 'IfStatement');
      result.refusals.push({ line: line(node),
        condition_hint: context ? spelling(context.test).slice(0, 240) : null,
        directly_guarded: context?.consequent === node || context?.consequent?.body?.length === 1 &&
          context.consequent.body[0] === node,
        error_kind: node.argument?.callee?.name ?? null });
    }
    if (!['FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression', 'ClassDeclaration', 'ClassExpression'].includes(node.type)) return;
    const functionName = node.id?.name ?? parent?.id?.name ?? parent?.key?.name ?? null;
    const scope = parent?.type.startsWith('Export') || parent?.type === 'Program'
      ? 'top_level' : (parent?.type === 'VariableDeclarator' && ancestors.at(-4)?.type === 'Program')
        ? 'top_level' : 'nested_or_member';
    const anchor = parent?.type.startsWith('Export') ? parent.start : node.start;
    const closest = comments.findLast(c => c.end <= anchor && !unit.code.slice(c.end, anchor).trim());
    result.symbols.push({
      name: functionName, kind: node.type, first_line: line(node),
      last_line: node.loc.end.line + unit.line, scope,
      exported_binding: scope === 'top_level' && (exported.has(functionName) || parent?.type.startsWith('Export')),
      parameters: (node.params ?? []).map(param => spelling(param)),
      doc_comment: closest?.type === 'Block' ? closest.value.trim().slice(0, 900) : null,
      async: node.async ?? false,
    });
  });
}

const output = [];
for (const file of files) {
  const record = { repository: file.repository, path: file.path, commit: file.commit, blob: file.blob,
    symbols: [], imports: [], constants: [], refusals: [], exports: [], issues: [] };
  for (const unit of groups(file)) parseUnit(unit, record);
  record.exports = [...new Set(record.exports.filter(Boolean))].sort();
  output.push(record);
}
process.stdout.write(JSON.stringify({ acorn_version: acorn.version, files: output }));

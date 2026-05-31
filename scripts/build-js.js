/**
 * JavaScript build script using esbuild.
 * Implements code splitting and asset optimization (Requirement 11.4).
 */

import * as esbuild from 'esbuild';
import { existsSync, mkdirSync } from 'fs';
import { join } from 'path';

const outDir = 'src/stockai/web/static/js/dist';

// Ensure output directory exists
if (!existsSync(outDir)) {
  mkdirSync(outDir, { recursive: true });
}

const entryPoints = [
  'src/stockai/web/static/js/app.js',
  'src/stockai/web/static/js/dashboard.js',
  'src/stockai/web/static/js/portfolio.js',
  'src/stockai/web/static/js/watchlist.js',
  'src/stockai/web/static/js/stock.js',
  'src/stockai/web/static/js/backtest.js',
  'src/stockai/web/static/js/coach.js',
  'src/stockai/web/static/js/journal.js',
  'src/stockai/web/static/js/scan.js',
].filter(ep => existsSync(ep));

try {
  const result = await esbuild.build({
    entryPoints,
    bundle: true,
    splitting: true,       // Code splitting (Requirement 11.4)
    format: 'esm',
    outdir: outDir,
    minify: true,          // Minification (Requirement 11.4)
    sourcemap: true,
    target: ['es2020'],
    treeShaking: true,     // Remove unused code
    metafile: true,
    logLevel: 'info',
  });

  // Report bundle sizes
  const text = await esbuild.analyzeMetafile(result.metafile, { verbose: false });
  console.log(text);
  console.log('✅ JavaScript build complete');
} catch (err) {
  console.error('❌ Build failed:', err.message);
  process.exit(1);
}

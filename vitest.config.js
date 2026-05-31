/**
 * Vitest configuration for StockAI frontend tests.
 * Covers unit tests, property-based tests, and accessibility tests.
 */

import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // Use jsdom for DOM testing
    environment: 'jsdom',

    // Setup files run before each test file
    setupFiles: ['tests/frontend/setup.js'],

    // Test file patterns
    include: [
      'tests/frontend/**/*.test.js',
      'tests/frontend/**/*.spec.js',
    ],

    // Coverage configuration (Requirement 11.6 - code coverage)
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html', 'lcov'],
      reportsDirectory: 'coverage',
      include: ['src/stockai/web/static/js/**/*.js'],
      exclude: ['src/stockai/web/static/js/dist/**'],
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 70,
        statements: 80,
      },
    },

    // Reporter
    reporter: ['verbose'],

    // Globals (makes describe/it/expect available without imports)
    globals: true,
  },
});

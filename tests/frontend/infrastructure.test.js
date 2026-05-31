/**
 * Infrastructure smoke tests.
 * Verifies that the testing frameworks are correctly configured.
 */

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { screen } from '@testing-library/dom';
import axe from 'axe-core';
import { render, createFromHTML } from './utils/helpers.js';

describe('Testing Infrastructure', () => {
  it('vitest is working', () => {
    expect(1 + 1).toBe(2);
  });

  it('jsdom environment is available', () => {
    expect(typeof document).toBe('object');
    expect(typeof window).toBe('object');
  });

  it('Testing Library DOM is working', () => {
    render('<button>Click me</button>');
    const btn = screen.getByRole('button', { name: 'Click me' });
    expect(btn).toBeTruthy();
  });

  it('jest-dom matchers are available', () => {
    render('<button disabled>Disabled</button>');
    const btn = screen.getByRole('button');
    expect(btn).toBeDisabled();
  });

  it('fast-check property testing is working', () => {
    // Property: string length is always non-negative
    fc.assert(
      fc.property(fc.string(), (s) => s.length >= 0)
    );
  });

  it('axe-core is available', () => {
    expect(typeof axe.run).toBe('function');
  });

  it('axe-core can audit a simple accessible element', async () => {
    render('<main><h1>Test Page</h1><p>Content</p></main>');
    const results = await axe.run(document.body);
    // A simple accessible page should have no critical violations
    const critical = results.violations.filter(v => v.impact === 'critical');
    expect(critical).toHaveLength(0);
  });
});

describe('fast-check property examples', () => {
  it('array length is always non-negative', () => {
    fc.assert(
      fc.property(fc.array(fc.integer()), (arr) => arr.length >= 0)
    );
  });

  it('number addition is commutative', () => {
    fc.assert(
      fc.property(fc.integer(), fc.integer(), (a, b) => a + b === b + a)
    );
  });
});

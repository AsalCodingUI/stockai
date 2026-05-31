/**
 * Vitest global test setup.
 * Configures Testing Library matchers and global test utilities.
 */

import '@testing-library/jest-dom';
import { afterEach } from 'vitest';

// Clean up DOM after each test
afterEach(() => {
  document.body.innerHTML = '';
  document.head.innerHTML = '';
});

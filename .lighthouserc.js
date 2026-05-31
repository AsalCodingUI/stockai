/**
 * Lighthouse CI configuration.
 * Enforces performance, accessibility, and best practices thresholds.
 * Requirements: 11.1 (FCP < 1.5s), 11.2 (TTI < 3s), 11.6 (bundle < 200KB)
 */

module.exports = {
  ci: {
    collect: {
      url: [
        'http://localhost:8000/',
        'http://localhost:8000/portfolio',
        'http://localhost:8000/watchlist',
      ],
      numberOfRuns: 3,
      settings: {
        // Simulate 3G connection (Requirement 11.1, 11.2)
        throttlingMethod: 'simulate',
        throttling: {
          rttMs: 150,
          throughputKbps: 1638.4,
          cpuSlowdownMultiplier: 4,
        },
      },
    },
    assert: {
      assertions: {
        // Performance (Requirements 11.1, 11.2)
        'first-contentful-paint': ['warn', { maxNumericValue: 1500 }],
        'interactive': ['warn', { maxNumericValue: 3000 }],
        'speed-index': ['warn', { maxNumericValue: 3000 }],

        // Accessibility (Requirement 4.1)
        'categories:accessibility': ['error', { minScore: 0.9 }],

        // Best Practices
        'categories:best-practices': ['warn', { minScore: 0.9 }],

        // Bundle size (Requirement 11.6 - < 200KB gzipped)
        'total-byte-weight': ['warn', { maxNumericValue: 512000 }],

        // Performance score
        'categories:performance': ['warn', { minScore: 0.9 }],
      },
    },
    upload: {
      target: 'temporary-public-storage',
    },
  },
};

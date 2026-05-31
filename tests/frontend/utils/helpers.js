/**
 * Shared test utilities and helpers for frontend tests.
 */

import axe from 'axe-core';

/**
 * Load a CSS file's text content into a <style> tag in the document head.
 * Used to test CSS custom properties and design tokens.
 */
export function injectCSS(cssText) {
  const style = document.createElement('style');
  style.textContent = cssText;
  document.head.appendChild(style);
  return style;
}

/**
 * Create a DOM element from an HTML string.
 */
export function createFromHTML(html) {
  const template = document.createElement('template');
  template.innerHTML = html.trim();
  return template.content.firstElementChild;
}

/**
 * Append an element to document.body and return it.
 */
export function render(element) {
  if (typeof element === 'string') {
    document.body.innerHTML = element;
    return document.body.firstElementChild;
  }
  document.body.appendChild(element);
  return element;
}

/**
 * Run axe accessibility audit on a DOM element or selector.
 * Returns the axe results object.
 */
export async function runAxe(element = document.body, options = {}) {
  const results = await axe.run(element, options);
  return results;
}

/**
 * Assert that an element has no axe accessibility violations.
 */
export async function expectNoA11yViolations(element = document.body, options = {}) {
  const results = await runAxe(element, options);
  if (results.violations.length > 0) {
    const messages = results.violations.map(v =>
      `[${v.impact}] ${v.id}: ${v.description}\n  Nodes: ${v.nodes.map(n => n.html).join(', ')}`
    ).join('\n');
    throw new Error(`Accessibility violations found:\n${messages}`);
  }
}

/**
 * Get computed CSS custom property value from an element.
 */
export function getCSSVar(varName, element = document.documentElement) {
  return getComputedStyle(element).getPropertyValue(varName).trim();
}

/**
 * Wait for a condition to be true (polling).
 */
export function waitFor(condition, timeout = 1000, interval = 50) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const check = () => {
      if (condition()) {
        resolve();
      } else if (Date.now() - start > timeout) {
        reject(new Error('waitFor timed out'));
      } else {
        setTimeout(check, interval);
      }
    };
    check();
  });
}

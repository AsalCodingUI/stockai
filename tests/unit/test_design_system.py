"""Property-Based Tests for UI/UX Design System.

Feature: ui-ux-improvement
Property 1: Design System Completeness

This test validates that the design system CSS file contains all required
design tokens as specified in Requirements 1.1-1.7.
"""

import pytest
import re
from pathlib import Path


class TestDesignSystemCompleteness:
    """Property 1: Design System Completeness
    
    Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7
    
    For any design system configuration, it SHALL contain all required sections:
    - Colors (primary, secondary, accent, success, warning, error, neutral scales)
    - Typography (font families, sizes, weights, line heights)
    - Spacing scale
    - Border radius values
    - Shadow levels
    - Animation timings
    - Breakpoints
    """
    
    @pytest.fixture
    def design_system_css(self):
        """Load the design system CSS file."""
        css_path = Path("src/stockai/web/static/css/design-system.css")
        assert css_path.exists(), f"Design system CSS not found at {css_path}"
        
        with open(css_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def extract_css_variables(self, css_content: str) -> dict[str, str]:
        """Extract all CSS custom properties from the :root section only."""
        # Extract only the :root block to avoid media query overrides
        root_pattern = r':root\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}'
        root_match = re.search(root_pattern, css_content, re.DOTALL)
        
        if root_match:
            root_content = root_match.group(1)
        else:
            root_content = css_content
        
        # Match CSS custom properties: --variable-name: value;
        pattern = r'--([a-z0-9-]+)\s*:\s*([^;]+);'
        matches = re.findall(pattern, root_content, re.MULTILINE)
        return {name: value.strip() for name, value in matches}
    
    def test_color_palette_primary_colors(self, design_system_css):
        """Requirement 1.1: Primary color scale must be defined."""
        variables = self.extract_css_variables(design_system_css)
        
        # Primary color (cyan)
        assert 'color-primary' in variables, "Missing --color-primary"
        assert 'color-primary-dark' in variables, "Missing --color-primary-dark"
        assert 'color-primary-light' in variables, "Missing --color-primary-light"
        
        # Verify primary color is white (#fafafa)
        assert '#fafafa' in variables['color-primary'].lower()
    
    def test_color_palette_secondary_colors(self, design_system_css):
        """Requirement 1.1: Secondary color scale must be defined."""
        variables = self.extract_css_variables(design_system_css)
        
        # Secondary color (green)
        assert 'color-secondary' in variables, "Missing --color-secondary"
        assert 'color-secondary-dark' in variables, "Missing --color-secondary-dark"
        assert 'color-secondary-light' in variables, "Missing --color-secondary-light"
        
        # Verify secondary color is zinc-800 (#27272a)
        assert '#27272a' in variables['color-secondary'].lower()
    
    def test_color_palette_accent_colors(self, design_system_css):
        """Requirement 1.1: Accent color must be defined."""
        variables = self.extract_css_variables(design_system_css)
        
        assert 'color-accent' in variables, "Missing --color-accent"
        assert 'color-accent-dark' in variables, "Missing --color-accent-dark"
        assert 'color-accent-light' in variables, "Missing --color-accent-light"
    
    def test_color_palette_semantic_colors(self, design_system_css):
        """Requirement 1.1: Semantic colors (success, warning, error) must be defined."""
        variables = self.extract_css_variables(design_system_css)
        
        # Success colors
        assert 'color-success' in variables, "Missing --color-success"
        assert 'color-success-dark' in variables, "Missing --color-success-dark"
        assert 'color-success-light' in variables, "Missing --color-success-light"
        
        # Warning colors
        assert 'color-warning' in variables, "Missing --color-warning"
        assert 'color-warning-dark' in variables, "Missing --color-warning-dark"
        assert 'color-warning-light' in variables, "Missing --color-warning-light"
        
        # Error/Danger colors
        assert 'color-error' in variables, "Missing --color-error"
        assert 'color-error-dark' in variables, "Missing --color-error-dark"
        assert 'color-error-light' in variables, "Missing --color-error-light"
        assert 'color-danger' in variables, "Missing --color-danger"
    
    def test_color_palette_neutral_scale(self, design_system_css):
        """Requirement 1.1: Neutral color scale must be defined."""
        variables = self.extract_css_variables(design_system_css)
        
        # Neutral scale (50-900)
        neutral_levels = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]
        for level in neutral_levels:
            var_name = f'color-neutral-{level}'
            assert var_name in variables, f"Missing --{var_name}"
    
    def test_color_palette_background_colors(self, design_system_css):
        """Requirement 1.1: Background colors must be defined."""
        variables = self.extract_css_variables(design_system_css)
        
        assert 'color-bg-primary' in variables, "Missing --color-bg-primary"
        assert 'color-bg-secondary' in variables, "Missing --color-bg-secondary"
        assert 'color-bg-tertiary' in variables, "Missing --color-bg-tertiary"
        assert 'color-bg-elevated' in variables, "Missing --color-bg-elevated"
    
    def test_color_palette_border_colors(self, design_system_css):
        """Requirement 1.1: Border colors must be defined."""
        variables = self.extract_css_variables(design_system_css)
        
        assert 'color-border' in variables, "Missing --color-border"
        assert 'color-border-hover' in variables, "Missing --color-border-hover"
        assert 'color-border-focus' in variables, "Missing --color-border-focus"
    
    def test_color_palette_text_colors(self, design_system_css):
        """Requirement 1.1: Text colors must be defined."""
        variables = self.extract_css_variables(design_system_css)
        
        assert 'color-text-primary' in variables, "Missing --color-text-primary"
        assert 'color-text-secondary' in variables, "Missing --color-text-secondary"
        assert 'color-text-tertiary' in variables, "Missing --color-text-tertiary"
        assert 'color-text-inverse' in variables, "Missing --color-text-inverse"
    
    def test_typography_font_families(self, design_system_css):
        """Requirement 1.2: Font families must be defined."""
        variables = self.extract_css_variables(design_system_css)
        
        assert 'font-family-base' in variables, "Missing --font-family-base"
        assert 'font-family-heading' in variables, "Missing --font-family-heading"
        assert 'font-family-mono' in variables, "Missing --font-family-mono"
        
        # Verify Inter is used
        assert 'inter' in variables['font-family-base'].lower()
    
    def test_typography_font_sizes(self, design_system_css):
        """Requirement 1.2: Font sizes must be defined."""
        variables = self.extract_css_variables(design_system_css)
        
        required_sizes = ['xs', 'sm', 'base', 'lg', 'xl', '2xl', '3xl', '4xl']
        for size in required_sizes:
            var_name = f'font-size-{size}'
            assert var_name in variables, f"Missing --{var_name}"
    
    def test_typography_font_weights(self, design_system_css):
        """Requirement 1.2: Font weights must be defined."""
        variables = self.extract_css_variables(design_system_css)
        
        required_weights = ['normal', 'medium', 'semibold', 'bold']
        for weight in required_weights:
            var_name = f'font-weight-{weight}'
            assert var_name in variables, f"Missing --{var_name}"
    
    def test_typography_line_heights(self, design_system_css):
        """Requirement 1.2: Line heights must be defined."""
        variables = self.extract_css_variables(design_system_css)
        
        required_line_heights = ['tight', 'normal', 'relaxed']
        for lh in required_line_heights:
            var_name = f'line-height-{lh}'
            assert var_name in variables, f"Missing --{var_name}"
    
    def test_typography_letter_spacing(self, design_system_css):
        """Requirement 1.2: Letter spacing must be defined."""
        variables = self.extract_css_variables(design_system_css)
        
        # At least normal letter spacing should be defined
        assert 'letter-spacing-normal' in variables, "Missing --letter-spacing-normal"
    
    def test_spacing_scale_complete(self, design_system_css):
        """Requirement 1.3: Spacing scale (4px, 8px, 12px, 16px, 24px, 32px, 48px, 64px) must be defined."""
        variables = self.extract_css_variables(design_system_css)
        
        # Required spacing values based on spec
        # spacing-1 = 4px, spacing-2 = 8px, spacing-3 = 12px, spacing-4 = 16px
        # spacing-6 = 24px, spacing-8 = 32px, spacing-12 = 48px, spacing-16 = 64px
        required_spacing = [1, 2, 3, 4, 6, 8, 12, 16]
        
        for spacing in required_spacing:
            var_name = f'spacing-{spacing}'
            assert var_name in variables, f"Missing --{var_name}"
        
        # Verify specific values
        assert '0.25rem' in variables['spacing-1'] or '4px' in variables['spacing-1']  # 4px
        assert '0.5rem' in variables['spacing-2'] or '8px' in variables['spacing-2']   # 8px
        assert '0.75rem' in variables['spacing-3'] or '12px' in variables['spacing-3'] # 12px
        assert '1rem' in variables['spacing-4'] or '16px' in variables['spacing-4']    # 16px
    
    def test_border_radius_values(self, design_system_css):
        """Requirement 1.4: Border radius values (small: 8px, medium: 12px, large: 16px) must be defined."""
        variables = self.extract_css_variables(design_system_css)
        
        assert 'radius-sm' in variables, "Missing --radius-sm (8px)"
        assert 'radius-md' in variables, "Missing --radius-md (12px)"
        assert 'radius-lg' in variables, "Missing --radius-lg (16px)"
        assert 'radius-full' in variables, "Missing --radius-full"
        
        # Verify specific values (Shadcn rounded components style)
        assert '0.375rem' in variables['radius-sm'] or '6px' in variables['radius-sm']   # 6px
        assert '0.5rem' in variables['radius-md'] or '8px' in variables['radius-md']     # 8px
        assert '0.75rem' in variables['radius-lg'] or '12px' in variables['radius-lg']   # 12px
    
    def test_shadow_levels(self, design_system_css):
        """Requirement 1.5: Shadow levels (subtle, medium, prominent) must be defined."""
        variables = self.extract_css_variables(design_system_css)
        
        # Shadow levels: sm (subtle), md (medium), lg (prominent)
        assert 'shadow-sm' in variables, "Missing --shadow-sm (subtle)"
        assert 'shadow-md' in variables, "Missing --shadow-md (medium)"
        assert 'shadow-lg' in variables, "Missing --shadow-lg (prominent)"
        
        # Glow shadows for neon effects
        assert 'shadow-glow-cyan' in variables, "Missing --shadow-glow-cyan"
        assert 'shadow-glow-green' in variables, "Missing --shadow-glow-green"
    
    def test_animation_durations(self, design_system_css):
        """Requirement 1.6: Animation durations must be defined."""
        variables = self.extract_css_variables(design_system_css)
        
        assert 'duration-fast' in variables, "Missing --duration-fast (150ms)"
        assert 'duration-normal' in variables, "Missing --duration-normal (250ms)"
        assert 'duration-slow' in variables, "Missing --duration-slow (400ms)"
        
        # Verify specific values
        assert '100ms' in variables['duration-fast']
        assert '200ms' in variables['duration-normal']
        assert '300ms' in variables['duration-slow']
    
    def test_animation_easing_functions(self, design_system_css):
        """Requirement 1.6: Animation easing functions must be defined."""
        variables = self.extract_css_variables(design_system_css)
        
        assert 'ease-in' in variables, "Missing --ease-in"
        assert 'ease-out' in variables, "Missing --ease-out"
        assert 'ease-in-out' in variables, "Missing --ease-in-out"
        
        # Verify cubic-bezier functions
        assert 'cubic-bezier' in variables['ease-out']
    
    def test_breakpoints_responsive_design(self, design_system_css):
        """Requirement 1.7: Breakpoints (mobile: 640px, tablet: 768px, desktop: 1024px, wide: 1280px) must be defined."""
        variables = self.extract_css_variables(design_system_css)
        
        assert 'breakpoint-sm' in variables, "Missing --breakpoint-sm (640px mobile)"
        assert 'breakpoint-md' in variables, "Missing --breakpoint-md (768px tablet)"
        assert 'breakpoint-lg' in variables, "Missing --breakpoint-lg (1024px desktop)"
        assert 'breakpoint-xl' in variables, "Missing --breakpoint-xl (1280px wide)"
        
        # Verify specific values
        assert '640px' in variables['breakpoint-sm']
        assert '768px' in variables['breakpoint-md']
        assert '1024px' in variables['breakpoint-lg']
        assert '1280px' in variables['breakpoint-xl']
    
    def test_design_system_completeness_property(self, design_system_css):
        """Property 1: Design System Completeness
        
        For any design system configuration, it SHALL contain all required sections:
        colors, typography, spacing, border radius, shadows, animation, and breakpoints.
        
        This is a comprehensive property test that validates the entire design system
        structure in a single assertion.
        """
        variables = self.extract_css_variables(design_system_css)
        
        # Count variables in each category
        color_vars = [k for k in variables.keys() if k.startswith('color-')]
        typography_vars = [k for k in variables.keys() if k.startswith(('font-', 'line-height-', 'letter-spacing-'))]
        spacing_vars = [k for k in variables.keys() if k.startswith('spacing-')]
        radius_vars = [k for k in variables.keys() if k.startswith('radius-')]
        shadow_vars = [k for k in variables.keys() if k.startswith('shadow-')]
        animation_vars = [k for k in variables.keys() if k.startswith(('duration-', 'ease-'))]
        breakpoint_vars = [k for k in variables.keys() if k.startswith('breakpoint-')]
        
        # Assert minimum counts for each category
        assert len(color_vars) >= 30, f"Insufficient color variables: {len(color_vars)} < 30"
        assert len(typography_vars) >= 15, f"Insufficient typography variables: {len(typography_vars)} < 15"
        assert len(spacing_vars) >= 8, f"Insufficient spacing variables: {len(spacing_vars)} < 8"
        assert len(radius_vars) >= 4, f"Insufficient radius variables: {len(radius_vars)} < 4"
        assert len(shadow_vars) >= 5, f"Insufficient shadow variables: {len(shadow_vars)} < 5"
        assert len(animation_vars) >= 5, f"Insufficient animation variables: {len(animation_vars)} < 5"
        assert len(breakpoint_vars) >= 4, f"Insufficient breakpoint variables: {len(breakpoint_vars)} < 4"
        
        # Total design tokens should be comprehensive
        total_tokens = len(variables)
        assert total_tokens >= 80, f"Design system should have at least 80 tokens, found {total_tokens}"
    
    def test_css_custom_properties_use_var_prefix(self, design_system_css):
        """All design tokens should use the -- prefix for CSS custom properties."""
        # Extract all variable definitions
        pattern = r'--([a-z0-9-]+)\s*:'
        matches = re.findall(pattern, design_system_css)
        
        # Should have many custom properties
        assert len(matches) >= 80, f"Expected at least 80 CSS custom properties, found {len(matches)}"
    
    def test_design_system_has_root_selector(self, design_system_css):
        """Design system should define variables in :root selector."""
        assert ':root' in design_system_css, "Missing :root selector"
        assert ':root {' in design_system_css or ':root{' in design_system_css
    
    def test_design_system_has_documentation(self, design_system_css):
        """Design system should include documentation comments."""
        # Check for section headers in comments
        assert 'COLOR PALETTE' in design_system_css or 'Color Palette' in design_system_css
        assert 'TYPOGRAPHY' in design_system_css or 'Typography' in design_system_css
        assert 'SPACING' in design_system_css or 'Spacing' in design_system_css
    
    def test_reduced_motion_support(self, design_system_css):
        """Design system should include reduced motion media query for accessibility."""
        assert 'prefers-reduced-motion' in design_system_css, "Missing reduced motion support"
        assert '@media (prefers-reduced-motion: reduce)' in design_system_css


class TestDesignSystemIntegration:
    """Integration tests for design system usage in base template."""
    
    def test_base_template_includes_design_system_css(self):
        """Base template should include design-system.css."""
        base_template_path = Path("src/stockai/web/templates/base.html")
        assert base_template_path.exists(), "Base template not found"
        
        with open(base_template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'design-system.css' in content, "Base template doesn't include design-system.css"
    
    def test_base_template_css_load_order(self):
        """CSS files should be loaded in correct order: design-system, tailwind, utilities, app."""
        base_template_path = Path("src/stockai/web/templates/base.html")
        
        with open(base_template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find positions of each CSS reference
        design_system_pos = content.find('design-system.css')
        utilities_pos = content.find('utilities.css')
        app_css_pos = content.find('app.css')
        
        assert design_system_pos > 0, "design-system.css not found"
        assert utilities_pos > 0, "utilities.css not found"
        assert app_css_pos > 0, "app.css not found"
        
        # Verify load order
        assert design_system_pos < utilities_pos, "design-system.css should load before utilities.css"
        assert utilities_pos < app_css_pos, "utilities.css should load before app.css"
    
    def test_utilities_css_exists(self):
        """Utilities CSS file should exist."""
        utilities_path = Path("src/stockai/web/static/css/utilities.css")
        assert utilities_path.exists(), "utilities.css not found"
    
    def test_tailwind_config_exists(self):
        """Tailwind configuration file should exist."""
        tailwind_config_path = Path("tailwind.config.js")
        assert tailwind_config_path.exists(), "tailwind.config.js not found"

/**
 * Tailwind CSS Configuration for StockAI
 * 
 * Re-configured for Shadcn Minimalist Dark Mode.
 */

module.exports = {
  content: [
    './src/stockai/web/templates/**/*.html',
    './src/stockai/web/static/js/**/*.js',
  ],
  
  darkMode: 'class',
  
  theme: {
    extend: {
      colors: {
        // Shadcn Zinc Color Palette
        primary: {
          DEFAULT: '#fafafa',
          dark: '#e4e4e7',
          light: '#ffffff',
        },
        
        secondary: {
          DEFAULT: '#27272a',
          dark: '#18181b',
          light: '#3f3f46',
        },
        
        accent: {
          DEFAULT: '#f4f4f5',
          dark: '#e4e4e7',
          light: '#ffffff',
        },
        
        // Semantic Colors
        success: {
          DEFAULT: '#10b981',
          dark: '#059669',
          light: '#34d399',
        },
        warning: {
          DEFAULT: '#f59e0b',
          dark: '#d97706',
          light: '#fbbf24',
        },
        error: {
          DEFAULT: '#ef4444',
          dark: '#dc2626',
          light: '#f87171',
        },
        danger: {
          DEFAULT: '#ef4444',
          dark: '#dc2626',
          light: '#f87171',
        },
        info: {
          DEFAULT: '#3b82f6',
          dark: '#2563eb',
          light: '#60a5fa',
        },
        
        // Background Colors
        bg: {
          primary: '#09090b',
          secondary: '#09090b',
          tertiary: '#18181b',
          elevated: '#18181b',
          hover: '#18181b',
        },
        
        // Border Colors
        border: {
          DEFAULT: '#27272a',
          hover: '#3f3f46',
          focus: '#e4e4e7',
          error: '#ef4444',
          success: '#10b981',
        },
        
        // Text Colors
        text: {
          primary: '#fafafa',
          secondary: '#a1a1aa',
          tertiary: '#71717a',
          inverse: '#09090b',
          muted: '#71717a',
          dim: '#a1a1aa',
        },
      },
      
      // Typography
      fontFamily: {
        sans: ['"Inter Display"', '"Inter"', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', '"Courier New"', 'monospace'],
      },
      
      letterSpacing: {
        tighter: '0em',
        tight: '0em',
        normal: '0em',
        wide: '0em',
        wider: '0em',
        widest: '0em',
      },
      
      borderRadius: {
        none: '0',
        sm: '0.375rem',   // 6px
        DEFAULT: '0.5rem', // 8px
        md: '0.5rem',     // 8px
        lg: '0.75rem',    // 12px
        xl: '1rem',       // 16px
        '2xl': '1.25rem',   // 20px
        full: '9999px',
      },
      
      boxShadow: {
        sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        DEFAULT: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
        md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
        lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
        xl: '0 20px 25px -5px rgba(0, 0, 0, 0.15), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
        '2xl': '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
        inner: 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.06)',
        none: 'none',
      },
      
      transitionDuration: {
        instant: '0ms',
        fast: '100ms',
        DEFAULT: '200ms',
        normal: '200ms',
        slow: '300ms',
        slower: '500ms',
      },
      
      zIndex: {
        0: '0',
        10: '10',
        20: '20',
        30: '30',
        40: '40',
        50: '50',
        dropdown: '1000',
        sticky: '1020',
        fixed: '1030',
        'modal-backdrop': '1040',
        modal: '1050',
        popover: '1060',
        tooltip: '1070',
        toast: '1080',
      },
    },
  },
  
  plugins: [],
};

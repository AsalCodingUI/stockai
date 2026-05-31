# Design Document: UI/UX Improvement for StockAI Web Dashboard

## Overview

This design document outlines the comprehensive UI/UX improvement for the StockAI web dashboard application. The design focuses on creating a modern, accessible, and performant financial trading interface that serves Indonesian retail traders and investors.

The improvement will be implemented incrementally, maintaining compatibility with the existing FastAPI backend while modernizing the frontend experience. The design emphasizes:

- **Trust and clarity**: Financial applications require users to make high-stakes decisions, so the interface must inspire confidence through clear information hierarchy and consistent patterns
- **Performance**: Real-time data updates and fast interactions are critical for trading applications
- **Accessibility**: WCAG 2.1 AA compliance ensures the application is usable by all traders
- **Mobile-first responsive design**: Over 60% of web traffic comes from mobile devices, requiring a mobile-optimized experience
- **Incremental implementation**: Page-by-page rollout minimizes risk and allows for iterative improvements

### Current State Analysis

The existing application uses:
- **Frontend**: Jinja2 templates with Tailwind CSS (CDN), Alpine.js for interactivity
- **Styling**: Custom CSS with dark theme, neon accent colors (cyan #00d4ff, green #00ff88)
- **Charts**: Lightweight Charts and Chart.js libraries
- **Layout**: Sidebar navigation with main content area
- **Pages**: 15 pages including dashboard, portfolio, watchlist, stock analysis, sentiment, backtest, coach, journal, scan, and alerts

**Strengths to preserve**:
- Dark theme optimized for extended viewing
- Monospace font (JetBrains Mono) for financial data readability
- Existing color system with neon accents
- Real-time data update infrastructure

**Areas for improvement**:
- Inconsistent component styling across pages
- Limited mobile responsiveness
- Missing accessibility features (ARIA labels, keyboard navigation)
- No loading states or skeleton screens
- Limited interactive feedback
- No customization options

## Architecture

### Design System Architecture

The design system will be organized into layers following atomic design principles:

```
Design System
├── Foundations (Tokens)
│   ├── Colors
│   ├── Typography
│   ├── Spacing
│   ├── Shadows
│   ├── Border Radius
│   └── Animations
├── Components (Atoms)
│   ├── Button
│   ├── Input
│   ├── Badge
│   ├── Icon
│   └── Spinner
├── Patterns (Molecules)
│   ├── Card
│   ├── Form Field
│   ├── Data Table
│   ├── Chart Container
│   └── Toast Notification
├── Templates (Organisms)
│   ├── Page Layout
│   ├── Navigation
│   ├── Dashboard Grid
│   └── Modal
└── Pages (Templates + Content)
    ├── Dashboard
    ├── Portfolio
    ├── Watchlist
    └── ...
```

### Technology Stack

**Maintained from current implementation**:
- FastAPI backend (Python)
- Jinja2 templating
- Tailwind CSS for utility-first styling
- Alpine.js for reactive components
- Lightweight Charts for financial charts
- Chart.js for general data visualization

**New additions**:
- Tailwind CSS configuration file (replacing CDN for customization)
- Custom CSS variables for design tokens
- Sortable.js for drag-and-drop functionality
- Intersection Observer API for lazy loading
- Web Animations API for smooth transitions

### File Structure

```
src/stockai/web/
├── static/
│   ├── css/
│   │   ├── design-system.css      # Design tokens and foundations
│   │   ├── components.css         # Component styles
│   │   ├── utilities.css          # Custom utility classes
│   │   └── app.css                # Main application styles
│   ├── js/
│   │   ├── components/            # Reusable JS components
│   │   │   ├── toast.js
│   │   │   ├── modal.js
│   │   │   ├── chart-wrapper.js
│   │   │   └── drag-drop.js
│   │   ├── utils/                 # Utility functions
│   │   │   ├── api.js
│   │   │   ├── formatters.js
│   │   │   └── validators.js
│   │   └── app.js                 # Main application logic
│   └── icons/                     # SVG icon library
├── templates/
│   ├── components/                # Reusable template components
│   │   ├── button.html
│   │   ├── card.html
│   │   ├── table.html
│   │   └── chart.html
│   ├── layouts/
│   │   ├── base.html              # Base layout with design system
│   │   └── dashboard-layout.html  # Dashboard-specific layout
│   └── pages/                     # Page templates
│       ├── dashboard.html
│       ├── portfolio.html
│       └── ...
└── tailwind.config.js             # Tailwind configuration
```

## Components and Interfaces

### Design Tokens (CSS Custom Properties)

Design tokens will be defined as CSS custom properties for consistency and easy theming:

```css
:root {
  /* Color Palette */
  --color-primary: #00d4ff;        /* Neon cyan */
  --color-primary-dark: #0099cc;
  --color-primary-light: #33ddff;
  
  --color-secondary: #00ff88;      /* Neon green */
  --color-secondary-dark: #00cc6a;
  --color-secondary-light: #33ff9f;
  
  --color-accent: #ff9500;         /* Orange */
  --color-danger: #ff3b5c;         /* Red */
  --color-warning: #fbbf24;        /* Yellow */
  --color-success: #00ff88;        /* Green */
  
  --color-bg-primary: #0a0a0f;
  --color-bg-secondary: #111118;
  --color-bg-tertiary: #16161f;
  --color-bg-elevated: #1e1e2e;
  
  --color-border: #1e1e2e;
  --color-border-hover: #2a2a3e;
  --color-border-focus: #00d4ff;
  
  --color-text-primary: #e2e8f0;
  --color-text-secondary: #94a3b8;
  --color-text-tertiary: #64748b;
  --color-text-inverse: #0a0a0f;
  
  /* Typography */
  --font-family-base: "JetBrains Mono", "Fira Code", monospace;
  --font-family-heading: "JetBrains Mono", monospace;
  
  --font-size-xs: 0.75rem;    /* 12px */
  --font-size-sm: 0.875rem;   /* 14px */
  --font-size-base: 1rem;     /* 16px */
  --font-size-lg: 1.125rem;   /* 18px */
  --font-size-xl: 1.25rem;    /* 20px */
  --font-size-2xl: 1.5rem;    /* 24px */
  --font-size-3xl: 1.875rem;  /* 30px */
  --font-size-4xl: 2.25rem;   /* 36px */
  
  --font-weight-normal: 400;
  --font-weight-medium: 500;
  --font-weight-semibold: 600;
  --font-weight-bold: 700;
  
  --line-height-tight: 1.25;
  --line-height-normal: 1.5;
  --line-height-relaxed: 1.75;
  
  /* Spacing Scale */
  --spacing-1: 0.25rem;   /* 4px */
  --spacing-2: 0.5rem;    /* 8px */
  --spacing-3: 0.75rem;   /* 12px */
  --spacing-4: 1rem;      /* 16px */
  --spacing-5: 1.25rem;   /* 20px */
  --spacing-6: 1.5rem;    /* 24px */
  --spacing-8: 2rem;      /* 32px */
  --spacing-10: 2.5rem;   /* 40px */
  --spacing-12: 3rem;     /* 48px */
  --spacing-16: 4rem;     /* 64px */
  
  /* Border Radius */
  --radius-sm: 0.5rem;    /* 8px */
  --radius-md: 0.75rem;   /* 12px */
  --radius-lg: 1rem;      /* 16px */
  --radius-full: 9999px;
  
  /* Shadows */
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.4);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
  --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.6);
  --shadow-glow-cyan: 0 0 20px rgba(0, 212, 255, 0.3);
  --shadow-glow-green: 0 0 20px rgba(0, 255, 136, 0.3);
  
  /* Animation */
  --duration-fast: 150ms;
  --duration-normal: 250ms;
  --duration-slow: 400ms;
  
  --ease-in: cubic-bezier(0.4, 0, 1, 1);
  --ease-out: cubic-bezier(0, 0, 0.2, 1);
  --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
  
  /* Breakpoints (for JS usage) */
  --breakpoint-sm: 640px;
  --breakpoint-md: 768px;
  --breakpoint-lg: 1024px;
  --breakpoint-xl: 1280px;
}
```

### Component Library Specifications

#### Button Component

**Variants**:
- Primary: Filled with primary color, high emphasis
- Secondary: Outlined with primary color, medium emphasis
- Ghost: Transparent with hover state, low emphasis
- Danger: Filled with danger color, destructive actions

**States**: Default, Hover, Active, Focus, Disabled, Loading

**Sizes**: Small (32px height), Medium (40px height), Large (48px height)

**HTML Structure**:
```html
<button class="btn btn-primary btn-md" type="button">
  <span class="btn-icon"><!-- SVG icon --></span>
  <span class="btn-text">Button Text</span>
</button>
```

**Accessibility**:
- Minimum 44x44px touch target on mobile
- Visible focus ring (2px solid primary color, 2px offset)
- Disabled state with aria-disabled="true"
- Loading state with aria-busy="true" and spinner

#### Card Component

**Structure**: Header (optional), Body, Footer (optional)

**Variants**:
- Default: Standard card with border
- Elevated: Card with shadow for prominence
- Interactive: Hover state with transform and glow
- Stat: Specialized for displaying metrics

**HTML Structure**:
```html
<article class="card card-interactive">
  <header class="card-header">
    <h3 class="card-title">Card Title</h3>
    <button class="card-action"><!-- Action icon --></button>
  </header>
  <div class="card-body">
    <!-- Card content -->
  </div>
  <footer class="card-footer">
    <!-- Footer actions -->
  </footer>
</article>
```

**Accessibility**:
- Semantic HTML (article, header, footer)
- Heading hierarchy maintained
- Interactive cards have role="button" or proper link semantics

#### Form Input Component

**Types**: Text, Number, Email, Tel, Select, Checkbox, Radio, Textarea

**States**: Default, Focus, Error, Success, Disabled

**HTML Structure**:
```html
<div class="form-field">
  <label for="input-id" class="form-label">
    Label Text
    <span class="form-required" aria-label="required">*</span>
  </label>
  <input 
    type="text" 
    id="input-id" 
    class="form-input" 
    aria-describedby="input-help input-error"
    aria-invalid="false"
  />
  <p id="input-help" class="form-help">Helper text</p>
  <p id="input-error" class="form-error" role="alert">Error message</p>
</div>
```

**Accessibility**:
- Label associated with input via for/id
- Error messages announced via role="alert"
- aria-invalid on error state
- aria-describedby linking help text and errors

#### Data Table Component

**Features**:
- Sortable columns
- Filterable data
- Pagination
- Row selection
- Responsive (card view on mobile)

**HTML Structure**:
```html
<div class="table-container">
  <div class="table-toolbar">
    <input type="search" class="table-search" placeholder="Search..." />
    <div class="table-filters"><!-- Filter controls --></div>
  </div>
  <table class="data-table" role="table">
    <thead>
      <tr>
        <th scope="col">
          <button class="table-sort" aria-sort="none">
            Column Name
            <span class="sort-icon" aria-hidden="true">↕</span>
          </button>
        </th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td data-label="Column Name">Cell content</td>
      </tr>
    </tbody>
  </table>
  <nav class="table-pagination" aria-label="Table pagination">
    <!-- Pagination controls -->
  </nav>
</div>
```

**Mobile Responsive Strategy**:
- Below 768px: Transform to card-based layout
- Each row becomes a card with label-value pairs
- Maintain data-label attributes for mobile display

**Accessibility**:
- Proper table semantics (thead, tbody, th, td)
- scope="col" on header cells
- Sortable columns with aria-sort attribute
- Pagination with aria-label

#### Toast Notification Component

**Types**: Success, Error, Warning, Info

**Features**:
- Auto-dismiss after 4 seconds
- Manual dismiss button
- Stack multiple toasts
- Slide-in animation from top-right

**HTML Structure**:
```html
<div class="toast toast-success" role="alert" aria-live="polite" aria-atomic="true">
  <div class="toast-icon" aria-hidden="true"><!-- Icon --></div>
  <div class="toast-content">
    <p class="toast-title">Success</p>
    <p class="toast-message">Operation completed successfully</p>
  </div>
  <button class="toast-dismiss" aria-label="Dismiss notification">
    <span aria-hidden="true">×</span>
  </button>
</div>
```

**Accessibility**:
- role="alert" for immediate announcements
- aria-live="polite" for non-critical messages
- aria-atomic="true" for complete message reading
- Dismiss button with aria-label

#### Modal/Dialog Component

**Features**:
- Backdrop overlay
- Focus trap
- Escape key to close
- Scroll lock on body
- Accessible close button

**HTML Structure**:
```html
<div class="modal-backdrop" aria-hidden="true"></div>
<dialog class="modal" role="dialog" aria-labelledby="modal-title" aria-modal="true">
  <div class="modal-header">
    <h2 id="modal-title" class="modal-title">Modal Title</h2>
    <button class="modal-close" aria-label="Close dialog">
      <span aria-hidden="true">×</span>
    </button>
  </div>
  <div class="modal-body">
    <!-- Modal content -->
  </div>
  <div class="modal-footer">
    <button class="btn btn-secondary">Cancel</button>
    <button class="btn btn-primary">Confirm</button>
  </div>
</dialog>
```

**Accessibility**:
- Use native <dialog> element
- aria-labelledby pointing to title
- aria-modal="true"
- Focus trap within modal
- Return focus to trigger element on close

#### Chart Container Component

**Features**:
- Responsive sizing
- Loading skeleton
- Error state
- Time period selector
- Chart type toggle
- Export functionality

**HTML Structure**:
```html
<div class="chart-container">
  <div class="chart-header">
    <h3 class="chart-title">Chart Title</h3>
    <div class="chart-controls">
      <div class="chart-period-selector" role="tablist">
        <button role="tab" aria-selected="true">1D</button>
        <button role="tab" aria-selected="false">1W</button>
        <button role="tab" aria-selected="false">1M</button>
      </div>
      <button class="chart-export" aria-label="Export chart">
        <!-- Export icon -->
      </button>
    </div>
  </div>
  <div class="chart-body">
    <div class="chart-canvas" role="img" aria-label="Stock price chart">
      <!-- Chart rendered here -->
    </div>
  </div>
</div>
```

**Loading State**:
```html
<div class="chart-skeleton">
  <div class="skeleton-line"></div>
  <div class="skeleton-line"></div>
  <div class="skeleton-line"></div>
</div>
```

**Accessibility**:
- role="img" on chart canvas
- Descriptive aria-label
- Keyboard-accessible controls
- Tab list pattern for period selector

### Layout System

#### Responsive Grid System

**Breakpoints**:
- Mobile: < 640px (1 column)
- Tablet: 640px - 1024px (2-3 columns)
- Desktop: > 1024px (4+ columns)

**Grid Classes**:
```css
.grid-responsive {
  display: grid;
  gap: var(--spacing-4);
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}

.grid-dashboard {
  display: grid;
  gap: var(--spacing-4);
  grid-template-columns: repeat(4, 1fr);
}

@media (max-width: 1024px) {
  .grid-dashboard {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 640px) {
  .grid-dashboard {
    grid-template-columns: 1fr;
  }
}
```

#### Page Layout Structure

**Desktop Layout**:
```
┌─────────────────────────────────────────┐
│ Sidebar (240px) │ Main Content Area     │
│                 │ ┌───────────────────┐ │
│ Navigation      │ │ Header            │ │
│ Links           │ │ (Search, Status)  │ │
│                 │ └───────────────────┘ │
│                 │ ┌───────────────────┐ │
│                 │ │ Content           │ │
│                 │ │                   │ │
│                 │ │                   │ │
│                 │ └───────────────────┘ │
└─────────────────────────────────────────┘
```

**Mobile Layout**:
```
┌─────────────────────┐
│ Top Bar             │
│ (Logo, Menu, Search)│
├─────────────────────┤
│ Content             │
│                     │
│                     │
│                     │
│                     │
├─────────────────────┤
│ Bottom Navigation   │
│ (Primary Actions)   │
└─────────────────────┘
```

## Data Models

### Design System Configuration

```typescript
interface DesignTokens {
  colors: {
    primary: ColorScale;
    secondary: ColorScale;
    accent: string;
    danger: string;
    warning: string;
    success: string;
    background: {
      primary: string;
      secondary: string;
      tertiary: string;
      elevated: string;
    };
    border: {
      default: string;
      hover: string;
      focus: string;
    };
    text: {
      primary: string;
      secondary: string;
      tertiary: string;
      inverse: string;
    };
  };
  typography: {
    fontFamily: {
      base: string;
      heading: string;
    };
    fontSize: Record<string, string>;
    fontWeight: Record<string, number>;
    lineHeight: Record<string, number>;
  };
  spacing: Record<string, string>;
  borderRadius: Record<string, string>;
  shadows: Record<string, string>;
  animation: {
    duration: Record<string, string>;
    easing: Record<string, string>;
  };
  breakpoints: Record<string, string>;
}

interface ColorScale {
  default: string;
  dark: string;
  light: string;
}
```

### Component Props Interface

```typescript
interface ButtonProps {
  variant: 'primary' | 'secondary' | 'ghost' | 'danger';
  size: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  loading?: boolean;
  icon?: string;
  fullWidth?: boolean;
  type?: 'button' | 'submit' | 'reset';
  ariaLabel?: string;
  onClick?: () => void;
}

interface CardProps {
  variant: 'default' | 'elevated' | 'interactive' | 'stat';
  title?: string;
  headerAction?: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
}

interface ToastProps {
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message: string;
  duration?: number;
  dismissible?: boolean;
  onDismiss?: () => void;
}

interface ChartProps {
  title: string;
  data: ChartData;
  type: 'line' | 'candlestick' | 'bar';
  height?: number;
  showPeriodSelector?: boolean;
  showExport?: boolean;
  loading?: boolean;
  error?: string;
}
```

### User Preferences Model

```typescript
interface UserPreferences {
  theme: 'dark' | 'light';
  accentColor: 'cyan' | 'green' | 'purple' | 'orange';
  density: 'comfortable' | 'compact';
  dashboardLayout: DashboardWidget[];
  reducedMotion: boolean;
  notifications: NotificationPreferences;
}

interface DashboardWidget {
  id: string;
  type: string;
  position: { x: number; y: number };
  size: { width: number; height: number };
  config: Record<string, any>;
}

interface NotificationPreferences {
  priceAlerts: boolean;
  tradeExecutions: boolean;
  marketNews: boolean;
  systemUpdates: boolean;
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Before defining the correctness properties, I'll analyze each acceptance criterion for testability:


### Property Reflection

After analyzing all acceptance criteria, I've identified several areas where properties can be consolidated:

**Design System Validation**: Requirements 1.1-1.7 all check for presence of design system elements. These can be combined into a single comprehensive property that validates the complete design system structure.

**Component Existence**: Requirements 2.1-2.8 check for component existence. These are better tested as examples rather than separate properties.

**Responsive Breakpoints**: Requirements 3.1-3.3 test specific breakpoints. These are examples of responsive behavior rather than universal properties.

**Touch Target Size**: Requirements 3.5, 3.7, and 12.8 all relate to touch target sizing. These can be combined into one property.

**Accessibility Properties**: Requirements 4.1-4.9 cover various accessibility aspects. Some can be combined (e.g., ARIA attributes, form labels).

**Loading States**: Requirements 9.1-9.7 cover loading feedback. Several of these describe the same pattern and can be consolidated.

**Consistency Properties**: Requirements 20.1-20.8 all test consistency. These can be combined into fewer, more comprehensive properties.

**Animation Properties**: Requirements 15.1-15.8 cover animation behavior. Several can be combined.

### Correctness Properties

Property 1: Design System Completeness
*For any* design system configuration, it SHALL contain all required sections: colors (with primary, secondary, accent, success, warning, error, neutral scales), typography (font families, sizes, weights, line heights), spacing scale, border radius values, shadow levels, animation timings, and breakpoints
**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7**

Property 2: Component Design System Compliance
*For any* component in the component library, its CSS SHALL use design system tokens (CSS custom properties) rather than hard-coded values
**Validates: Requirements 2.9**

Property 3: Flexible Grid Adaptation
*For any* grid layout, when the container width changes, the grid SHALL recalculate column count to fit the available space without horizontal overflow
**Validates: Requirements 3.4**

Property 4: Touch Target Minimum Size
*For any* interactive element (button, link, input) on mobile viewports (< 640px), its clickable area SHALL be at least 44x44 pixels
**Validates: Requirements 3.5, 3.7, 12.8**

Property 5: Color Contrast Compliance
*For any* text and background color combination used in the application, the contrast ratio SHALL meet WCAG 2.1 AA standards (4.5:1 for normal text, 3:1 for large text >= 18pt)
**Validates: Requirements 4.1, 13.6**

Property 6: Keyboard Focus Visibility
*For any* interactive element, when it receives keyboard focus, it SHALL display a visible focus indicator with minimum 2px outline and sufficient contrast
**Validates: Requirements 4.2**

Property 7: Logical Tab Order
*For any* page, interactive elements SHALL have tab order that follows visual reading order (left-to-right, top-to-bottom) without unexpected jumps
**Validates: Requirements 4.3**

Property 8: ARIA Attribute Completeness
*For any* interactive component (button, link, input, modal, dialog), it SHALL have appropriate ARIA attributes (role, aria-label, aria-describedby, aria-expanded, etc.) based on its function
**Validates: Requirements 4.4**

Property 9: Image Alternative Text
*For any* image or icon element, it SHALL have either alt attribute or aria-label providing descriptive text, or aria-hidden="true" if decorative
**Validates: Requirements 4.5**

Property 10: Form Input Label Association
*For any* form input element, it SHALL have an associated label element linked via for/id attributes or aria-labelledby
**Validates: Requirements 4.6**

Property 11: Animation Flash Safety
*For any* animation or transition, if it includes flashing or strobing effects, the frequency SHALL be less than 3 flashes per second
**Validates: Requirements 4.8**

Property 12: Data Table Semantic Markup
*For any* data table, it SHALL use proper semantic HTML including <table>, <thead>, <tbody>, <th> with scope attribute, and <caption> or aria-label
**Validates: Requirements 4.9**

Property 13: Real-Time Update Without Reload
*For any* data update event, the display SHALL refresh using DOM manipulation or framework reactivity without triggering full page reload (window.location change)
**Validates: Requirements 6.1**

Property 14: Data Update Transition
*For any* data update that changes displayed content, the change SHALL include a CSS transition or animation with duration between 150ms and 400ms
**Validates: Requirements 6.2**

Property 15: Loading Indicator Visibility
*For any* asynchronous operation, while the operation is in progress, a loading indicator (spinner, skeleton, progress bar) SHALL be visible to the user
**Validates: Requirements 6.3, 9.1, 9.2, 9.3**

Property 16: Optimistic UI Update
*For any* user-initiated action (form submit, button click), the UI SHALL update immediately to reflect the expected result before server response arrives
**Validates: Requirements 6.4, 9.6**

Property 17: Price Change Visual Feedback
*For any* price value display, when the price changes, the element SHALL temporarily apply a color class (green for increase, red for decrease) with fade-out animation
**Validates: Requirements 6.5**

Property 18: Update Batching
*For any* sequence of data updates occurring within 100ms, the updates SHALL be batched into a single render cycle rather than triggering multiple re-renders
**Validates: Requirements 6.6**

Property 19: Chart Color Consistency
*For any* chart or data visualization, colors SHALL follow the defined scheme: green (#00ff88) for positive/gains, red (#ff3b5c) for negative/losses, cyan (#00d4ff) for neutral/informational
**Validates: Requirements 7.1**

Property 20: Chart Interactive Tooltip
*For any* chart, when user hovers over or touches a data point, a tooltip SHALL appear displaying the exact values for that point
**Validates: Requirements 7.3**

Property 21: Chart Zoom and Pan Support
*For any* chart displaying time-series data, the chart SHALL support zoom (via scroll wheel or pinch gesture) and pan (via drag) interactions
**Validates: Requirements 7.4, 12.6**

Property 22: Multi-Series Chart Legend
*For any* chart displaying multiple data series, each series SHALL have a distinct color and a legend SHALL be present identifying each series
**Validates: Requirements 7.5**

Property 23: Chart Responsive Sizing
*For any* chart, when its container element resizes, the chart SHALL resize to fit the new container dimensions within 250ms
**Validates: Requirements 7.6**

Property 24: Chart Loading Skeleton
*For any* chart in loading state, a skeleton placeholder SHALL be displayed with animated shimmer effect matching the approximate structure of the chart
**Validates: Requirements 7.7**

Property 25: Drag Operation Visual Feedback
*For any* drag-and-drop operation, while dragging, the system SHALL display visual feedback including a ghost element following the cursor and highlighted drop zones
**Validates: Requirements 8.2**

Property 26: Action Toast Notification
*For any* user action that completes (successfully or with error), a toast notification SHALL appear with appropriate type (success, error, warning, info) and message
**Validates: Requirements 8.3, 16.1**

Property 27: Toast Auto-Dismiss Timing
*For any* toast notification, it SHALL automatically dismiss after 4 seconds unless it is marked as persistent or user dismisses it manually
**Validates: Requirements 8.4**

Property 28: Interactive Element Hover Feedback
*For any* interactive element (button, link, card), when user hovers over it, the element SHALL show visual feedback (cursor change to pointer, background color change, or transform) within 150ms
**Validates: Requirements 8.6**

Property 29: Skeleton Structure Matching
*For any* loading skeleton, its structure (number of lines, shapes, layout) SHALL approximate the structure of the content that will replace it
**Validates: Requirements 9.1**

Property 30: Loading Button State
*For any* button that triggers an asynchronous operation, while the operation is in progress, the button SHALL be disabled (disabled attribute) and display a loading spinner
**Validates: Requirements 9.3**

Property 31: Long Operation Progress Indicator
*For any* operation that takes longer than 2 seconds, a progress indicator (progress bar or percentage) SHALL be displayed showing operation progress
**Validates: Requirements 9.4**

Property 32: Error State Retry Option
*For any* failed data load or operation, the error display SHALL include a retry button or link that attempts the operation again
**Validates: Requirements 9.5**

Property 33: Above-Fold Priority Loading
*For any* page load, resources required for above-the-fold content SHALL be loaded and rendered before below-the-fold resources
**Validates: Requirements 9.7**

Property 34: Dashboard Critical Data Performance
*For any* dashboard page load, critical data (key metrics, primary chart) SHALL be fetched and displayed within 1 second on a 3G connection
**Validates: Requirements 10.2**

Property 35: Dashboard Layout Persistence
*For any* change to dashboard widget layout (position, size, visibility), the new layout SHALL be saved to local storage and restored on next page load
**Validates: Requirements 10.4**

Property 36: Widget Resize Functionality
*For any* dashboard widget, it SHALL support resize interaction via drag handles, with minimum size constraints to maintain content readability
**Validates: Requirements 10.6**

Property 37: First Contentful Paint Performance
*For any* page load, First Contentful Paint (FCP) SHALL occur within 1.5 seconds on a 3G connection (measured via Lighthouse or WebPageTest)
**Validates: Requirements 11.1**

Property 38: Time to Interactive Performance
*For any* page load, Time to Interactive (TTI) SHALL occur within 3 seconds on a 3G connection (measured via Lighthouse or WebPageTest)
**Validates: Requirements 11.2**

Property 39: Below-Fold Lazy Loading
*For any* image or chart positioned below the initial viewport, it SHALL use lazy loading (loading="lazy" attribute or Intersection Observer) to defer loading until near viewport
**Validates: Requirements 11.3**

Property 40: Static Asset Caching
*For any* static asset (CSS, JS, images, fonts), the HTTP response SHALL include cache headers with appropriate max-age (1 year for versioned assets, shorter for unversioned)
**Validates: Requirements 11.5**

Property 41: JavaScript Bundle Size Limit
*For any* production build, the initial JavaScript bundle size SHALL be under 200KB when gzipped
**Validates: Requirements 11.6**

Property 42: Complex Layout CSS Containment
*For any* complex layout component (dashboard grid, data table, chart container), the CSS SHALL include contain property (layout, paint, or size) to optimize rendering
**Validates: Requirements 11.7**

Property 43: Large List Virtual Scrolling
*For any* list containing more than 100 items, the list SHALL implement virtual scrolling (only rendering visible items plus buffer) to maintain performance
**Validates: Requirements 11.8**

Property 44: Input Debouncing
*For any* search input or event handler that triggers expensive operations (API calls, re-renders), the handler SHALL be debounced with minimum 300ms delay
**Validates: Requirements 11.9, 17.2**

Property 45: Mobile Form Input Types
*For any* form input on mobile viewport, the input type attribute SHALL match the expected data (type="tel" for phone, type="email" for email, type="number" for numeric) to trigger appropriate mobile keyboard
**Validates: Requirements 12.3**

Property 46: Mobile Input Zoom Prevention
*For any* form input on mobile viewport, the input SHALL have font-size of at least 16px to prevent automatic zoom on focus
**Validates: Requirements 12.4**

Property 47: Theme Transition Smoothness
*For any* theme switch (dark to light or vice versa), all color properties SHALL transition smoothly using CSS transitions without flash of unstyled content
**Validates: Requirements 13.2**

Property 48: Theme Preference Persistence
*For any* theme selection by user, the preference SHALL be saved to local storage and applied on subsequent page loads
**Validates: Requirements 13.3, 19.9**

Property 49: Error Message User-Friendliness
*For any* error that occurs, the displayed error message SHALL be in plain language (avoiding technical jargon or stack traces) and suggest a corrective action
**Validates: Requirements 14.1**

Property 50: Error Type Differentiation
*For any* HTTP error response, the error message SHALL differ based on status code category: 4xx errors suggest user action corrections, 5xx errors suggest retry or contact support
**Validates: Requirements 14.2**

Property 51: Empty State Call-to-Action
*For any* empty state display (no data, no results, no items), the display SHALL include an illustrative graphic or icon and a call-to-action button or link
**Validates: Requirements 14.3**

Property 52: Context-Specific Empty States
*For any* empty state, the message SHALL be specific to the context (e.g., "No stocks in watchlist" vs "No search results" vs "No trades recorded")
**Validates: Requirements 14.4**

Property 53: Error Console Logging
*For any* error that occurs, the error details (message, stack trace, context) SHALL be logged to browser console for debugging purposes
**Validates: Requirements 14.6**

Property 54: Form Validation Error Highlighting
*For any* form field that fails validation, the field SHALL be highlighted with error styling (red border, error icon) and an error message SHALL be displayed below the field
**Validates: Requirements 14.7**

Property 55: Animation Duration Consistency
*For any* animation or transition, the duration SHALL be one of the defined values: 150ms (fast), 250ms (normal), or 400ms (slow)
**Validates: Requirements 15.1**

Property 56: Animation Easing Consistency
*For any* animation or transition, the easing function SHALL be one of the defined values: ease-out for entrances, ease-in for exits, ease-in-out for movements
**Validates: Requirements 15.2**

Property 57: Viewport Entry Animation
*For any* element that enters the viewport (via scroll or dynamic insertion), the element SHALL animate in using fade-in or slide-up animation
**Validates: Requirements 15.3**

Property 58: Layout Change Animation
*For any* layout change (element position, size, or visibility), the change SHALL be animated using CSS transitions on transform or opacity properties
**Validates: Requirements 15.4**

Property 59: Reduced Motion Respect
*For any* animation or transition, when user has prefers-reduced-motion: reduce set, non-essential animations SHALL be disabled or reduced to simple fades
**Validates: Requirements 15.5**

Property 60: Modal Animation Pattern
*For any* modal or dialog that opens, the backdrop SHALL fade in and the modal content SHALL scale up from 0.95 to 1.0 with ease-out timing
**Validates: Requirements 15.6**

Property 61: Button Micro-Interaction
*For any* button, it SHALL have micro-interactions: scale down slightly on click (transform: scale(0.98)), and show ripple or glow effect on hover
**Validates: Requirements 15.7**

Property 62: Simultaneous Animation Limit
*For any* point in time, there SHALL be no more than 5 elements animating simultaneously to prevent overwhelming users and performance issues
**Validates: Requirements 15.8**

Property 63: Toast Stack Limit
*For any* time when multiple toast notifications are queued, a maximum of 3 toasts SHALL be visible simultaneously, with older toasts dismissed as new ones appear
**Validates: Requirements 16.2**

Property 64: Toast Entrance Animation
*For any* toast notification that appears, it SHALL slide in from the top-right corner with fade animation over 250ms
**Validates: Requirements 16.3**

Property 65: Actionable Notification Support
*For any* toast notification, it SHALL support optional action buttons (e.g., "View", "Undo", "Dismiss") that trigger callbacks when clicked
**Validates: Requirements 16.5**

Property 66: Related Notification Grouping
*For any* set of related notifications (same type, same source, within 5 seconds), they SHALL be grouped into a single notification with count indicator
**Validates: Requirements 16.6**

Property 67: Critical Alert Persistence
*For any* notification marked as critical severity, it SHALL persist on screen until user explicitly acknowledges it (no auto-dismiss)
**Validates: Requirements 16.7**

Property 68: Search Result Highlighting
*For any* search result item, text matching the search query SHALL be highlighted with distinct background color or bold styling
**Validates: Requirements 17.3**

Property 69: List Filter Controls
*For any* list view with filterable data, filter controls SHALL be present above or beside the list, showing available filter options
**Validates: Requirements 17.6**

Property 70: Multiple Filter Combination
*For any* list with multiple active filters, the filters SHALL be combined with AND logic (item must match all filters to be shown)
**Validates: Requirements 17.7**

Property 71: Active Filter Clear Option
*For any* list view with one or more active filters, a "Clear all filters" button SHALL be visible and clicking it SHALL remove all filters
**Validates: Requirements 17.8**

Property 72: Complex Feature Help Tooltip
*For any* UI element representing a complex feature or unfamiliar concept, a help icon or tooltip SHALL be available providing explanation
**Validates: Requirements 18.1**

Property 73: First-Time Feature Introduction
*For any* feature accessed for the first time (tracked via local storage), a brief introduction modal or tooltip SHALL appear explaining the feature
**Validates: Requirements 18.3**

Property 74: Empty State Help Link
*For any* empty state display, it SHALL include a link to relevant help documentation or tutorial
**Validates: Requirements 18.6**

Property 75: Table and Chart Export
*For any* data table or chart, an export button SHALL be available offering format options (CSV for tables, PNG/PDF for charts)
**Validates: Requirements 19.1**

Property 76: Export Progress Indication
*For any* export operation, while the export is generating, a progress indicator SHALL be displayed
**Validates: Requirements 19.2**

Property 77: Share Functionality
*For any* view that can be shared (chart, analysis, portfolio), a share button SHALL be available that generates a shareable URL
**Validates: Requirements 19.3**

Property 78: Clipboard Copy Support
*For any* data display (table cell, metric value, code snippet), a copy button SHALL be available that copies the data to clipboard with formatting
**Validates: Requirements 19.4**

Property 79: Print Layout Optimization
*For any* page, when printed (or print preview), the layout SHALL be optimized: hiding navigation, adjusting colors for print, ensuring content fits page width
**Validates: Requirements 19.5**

Property 80: Export Metadata Inclusion
*For any* exported file (CSV, PDF, PNG), metadata SHALL be included: export date/time, applied filters, data source, and user identifier
**Validates: Requirements 19.6**

Property 81: Page Header Consistency
*For any* page in the application, the header structure SHALL be consistent: logo/title on left, search in center, status/user info on right
**Validates: Requirements 20.1**

Property 82: Content Type Card Consistency
*For any* similar content type (stock cards, trade cards, alert cards), the card layout SHALL be consistent: same header structure, same action placement, same spacing
**Validates: Requirements 20.2**

Property 83: Button Placement Consistency
*For any* form or dialog, primary action button SHALL be on the right, secondary/cancel button SHALL be on the left, with consistent spacing
**Validates: Requirements 20.3**

Property 84: Terminology Consistency
*For any* label, button text, or message, the terminology SHALL match the defined glossary (e.g., always "Watchlist" not "Watch List" or "Favorites")
**Validates: Requirements 20.4**

Property 85: Icon Set Consistency
*For any* icon usage, the icon SHALL come from the defined icon library (same style, same size scale) rather than mixed icon sets
**Validates: Requirements 20.5**

Property 86: Spacing Consistency
*For any* page layout, spacing between elements SHALL use design system spacing scale values (4px, 8px, 12px, 16px, 24px, 32px, 48px, 64px)
**Validates: Requirements 20.6**

Property 87: Data Format Consistency
*For any* data type display (currency, percentage, date, time), the format SHALL be consistent across the application (e.g., always "Rp 1.234.567" for Indonesian Rupiah)
**Validates: Requirements 20.7**

Property 88: Status Color Consistency
*For any* status indicator (badge, dot, border), the color SHALL follow the defined scheme: green for positive/active, red for negative/error, yellow for warning, gray for inactive
**Validates: Requirements 20.8**

## Error Handling

### Error Categories and Handling Strategies

**Network Errors**:
- Display offline indicator in header
- Queue user actions for retry when connection restored
- Show cached data with staleness indicator
- Provide manual retry button

**API Errors**:
- 4xx Client Errors: Show user-friendly message suggesting correction (e.g., "Invalid stock symbol. Please check and try again.")
- 5xx Server Errors: Show generic error with retry option (e.g., "Service temporarily unavailable. Please try again.")
- Timeout Errors: Show timeout message with retry option

**Validation Errors**:
- Highlight invalid fields with red border
- Display specific error message below field
- Prevent form submission until errors resolved
- Show error count in submit button if multiple errors

**Data Loading Errors**:
- Show error state in place of content
- Include error icon and message
- Provide retry button
- Log error details to console

**Chart Rendering Errors**:
- Show error state in chart container
- Display fallback message: "Unable to load chart data"
- Provide retry button
- Fall back to table view if available

### Error Logging

All errors will be logged to browser console with structured format:

```javascript
console.error('[StockAI Error]', {
  type: 'API_ERROR',
  endpoint: '/api/stocks/BBCA',
  status: 500,
  message: 'Internal Server Error',
  timestamp: new Date().toISOString(),
  userAction: 'Viewing stock detail',
  context: { stockSymbol: 'BBCA' }
});
```

### Error Recovery Patterns

**Optimistic UI Rollback**:
- When optimistic update fails, revert UI to previous state
- Show toast notification explaining failure
- Offer retry option

**Graceful Degradation**:
- If advanced chart library fails, fall back to simple chart
- If drag-drop fails, provide alternative button-based reordering
- If real-time updates fail, fall back to manual refresh

**Partial Failure Handling**:
- If dashboard loads but one widget fails, show error in that widget only
- Allow user to continue using other widgets
- Provide per-widget retry

## Testing Strategy

### Dual Testing Approach

The UI/UX improvement will be validated through both unit testing and property-based testing:

**Unit Tests**: Focus on specific examples, edge cases, and integration points
- Component rendering with different props
- User interaction flows (click, type, drag)
- Edge cases (empty states, error states, loading states)
- Integration between components
- Browser API interactions (localStorage, clipboard, etc.)

**Property-Based Tests**: Verify universal properties across all inputs
- Design system token validation
- Accessibility compliance (contrast ratios, ARIA attributes)
- Responsive behavior across viewport sizes
- Performance metrics (FCP, TTI, bundle size)
- Consistency checks (spacing, colors, terminology)

### Testing Tools and Frameworks

**Unit Testing**:
- **Framework**: Jest or Vitest for JavaScript testing
- **DOM Testing**: Testing Library for component interaction testing
- **Mocking**: MSW (Mock Service Worker) for API mocking
- **Coverage**: Aim for 80%+ coverage of component logic

**Property-Based Testing**:
- **Framework**: fast-check for JavaScript property-based testing
- **Configuration**: Minimum 100 iterations per property test
- **Tagging**: Each test tagged with feature name and property number

**Accessibility Testing**:
- **Automated**: axe-core for automated accessibility testing
- **Manual**: Screen reader testing (NVDA, JAWS, VoiceOver)
- **Contrast**: Color contrast analyzer for WCAG compliance

**Visual Regression Testing**:
- **Tool**: Percy or Chromatic for visual diff testing
- **Coverage**: Key pages and components
- **Breakpoints**: Test at mobile, tablet, and desktop sizes

**Performance Testing**:
- **Tool**: Lighthouse CI for automated performance testing
- **Metrics**: FCP, TTI, LCP, CLS, bundle size
- **Thresholds**: FCP < 1.5s, TTI < 3s, bundle < 200KB gzipped

### Test Organization

```
tests/
├── unit/
│   ├── components/
│   │   ├── Button.test.js
│   │   ├── Card.test.js
│   │   ├── DataTable.test.js
│   │   └── ...
│   ├── utils/
│   │   ├── formatters.test.js
│   │   └── validators.test.js
│   └── integration/
│       ├── dashboard.test.js
│       └── portfolio.test.js
├── properties/
│   ├── design-system.property.test.js
│   ├── accessibility.property.test.js
│   ├── responsive.property.test.js
│   ├── performance.property.test.js
│   └── consistency.property.test.js
├── visual/
│   ├── dashboard.visual.test.js
│   ├── portfolio.visual.test.js
│   └── ...
└── e2e/
    ├── user-flows.test.js
    └── critical-paths.test.js
```

### Property Test Example

```javascript
// Feature: ui-ux-improvement, Property 4: Touch Target Minimum Size
import fc from 'fast-check';
import { getComputedStyle } from './test-utils';

describe('Property 4: Touch Target Minimum Size', () => {
  it('ensures all interactive elements on mobile have minimum 44x44px touch targets', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('button', 'a', 'input[type="button"]', 'input[type="submit"]'),
        (selector) => {
          // Set mobile viewport
          window.innerWidth = 375;
          
          // Get all interactive elements of this type
          const elements = document.querySelectorAll(selector);
          
          // Check each element
          elements.forEach(element => {
            const styles = getComputedStyle(element);
            const width = parseFloat(styles.width);
            const height = parseFloat(styles.height);
            
            // Assert minimum touch target size
            expect(width).toBeGreaterThanOrEqual(44);
            expect(height).toBeGreaterThanOrEqual(44);
          });
        }
      ),
      { numRuns: 100 }
    );
  });
});
```

### Test Execution Strategy

**Development**:
- Run unit tests on file save (watch mode)
- Run property tests before commit (pre-commit hook)
- Run accessibility tests on component changes

**CI/CD Pipeline**:
1. Lint and type check
2. Run all unit tests
3. Run all property tests (100 iterations each)
4. Run accessibility tests
5. Run visual regression tests
6. Run performance tests (Lighthouse)
7. Generate coverage report
8. Fail build if coverage < 80% or any test fails

**Pre-Release**:
- Full test suite execution
- Manual accessibility testing with screen readers
- Cross-browser testing (Chrome, Firefox, Safari, Edge)
- Mobile device testing (iOS Safari, Android Chrome)
- Performance testing on 3G connection

### Acceptance Criteria

Tests must pass the following criteria before deployment:

- ✅ All unit tests passing
- ✅ All property tests passing (100 iterations each)
- ✅ Code coverage ≥ 80%
- ✅ No accessibility violations (axe-core)
- ✅ Lighthouse score ≥ 90 for Performance, Accessibility, Best Practices
- ✅ FCP < 1.5s, TTI < 3s on 3G
- ✅ Bundle size < 200KB gzipped
- ✅ No visual regressions
- ✅ Manual screen reader testing passed
- ✅ Cross-browser compatibility verified


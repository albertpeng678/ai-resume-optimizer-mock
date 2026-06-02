# Design System — AI Resume Scanner

## 1. NNgroup Research Findings

### High-Guidance UI Principles
Sources: NNgroup Design-Pattern Guidelines (2024), Progressive Disclosure (2022), Reduce Cognitive Load in Forms (2025)

| Principle | Application |
|-----------|-------------|
| **Progressive Disclosure** | Defer secondary info to subsidiary screens; show 5 dimension cards one-at-a-time via SSE streaming, not all at once |
| **Structure** (1 of 4 cognitive load principles) | Logical grouping: nav → upload zone → result cards → staggered reveal |
| **Transparency** | Show remaining weekly uses prominently (badge in header), loading states for each card |
| **Clarity** | Each card = one dimension with clear label, star rating, and sectioned content |
| **Support** | Inline hint text on upload zone, error states with clear recovery actions |
| **Wayfinding / Signposts** | Progress indicator (● ● ● ○ ○) shows where user is in the 5-card flow |
| **Card UI Pattern** (NNgroup 2016) | Self-contained containers, grouped by dimension, scannable at a glance |

### Cross-Device Layout Patterns
Sources: NNgroup Breakpoints (2024), Luke Wroblewski Multi-Device Patterns

| Device | Breakpoint | Layout Strategy |
|--------|-----------|-----------------|
| Mobile | < 640px | Single column stack, full-width cards, bottom nav CTA |
| Tablet | 640-1024px | 2-column card grid, sidebar nav |
| Desktop | > 1024px | Centered max-width container, 5 cards in single column (streaming reveal) |

Design approach: **Mobile-first** (Luke Wroblewski). Start with one-thumb, one-eyeball constraints, then enhance for larger screens.

---

## 2. Color Palette — Navy Blue

| Token | Hex | Usage |
|-------|-----|-------|
| `--navy-900` | `#0a1628` | Primary background (nav, hero) |
| `--navy-800` | `#0f1f3a` | Card header, secondary bg |
| `--navy-700` | `#1a2d4a` | Button hover, active states |
| `--navy-600` | `#2a4060` | Interactive elements, links |
| `--navy-500` | `#4a6a8a` | Secondary text, borders |
| `--navy-100` | `#e8edf3` | Light bg, dividers |
| `--navy-50` | `#f4f7fa` | Page background |
| `--accent` | `#3b82f6` | Blue accent (buttons, highlights) |
| `--accent-hover` | `#2563eb` | Accent hover |
| `--success` | `#22c55e` | Positive indicators |
| `--warning` | `#eab308` | Limit warnings |
| `--text` | `#1a1a2e` | Primary text |
| `--text-secondary` | `#6b7280` | Secondary text |
| `--white` | `#ffffff` | Card background |
| `--border` | `#e5e7eb` | Borders |

**Why Navy Blue only**: Single-hue system reduces cognitive load, creates professional/trustworthy feel, works across all device sizes without color clutter.

---

## 3. Typography

- **Font**: `system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`
- **Scale**: 0.75rem / 0.875rem / 1rem / 1.25rem / 1.5rem / 2rem
- **Weights**: 400 (regular), 500 (medium), 600 (semibold), 700 (bold)
- **Locale**: Traditional Chinese (zh-TW) throughout

---

## 4. Component Design

### Navigation Bar
- Mobile: hamburger + brand + usage badge
- Tablet/Desktop: brand + user email + logout + usage badge
- Background: `--navy-900`

### Upload Zone
- Dashed border (`--navy-500`), white bg
- Drag-and-drop with visual feedback on hover (border becomes solid `--navy-600`)
- Selected file: show filename + size + "Start Analysis" button (`--accent`)

### Result Card
- White bg, `--border` border, 8px radius
- Header: dimension name (left) + star rating (right, in `--accent`)
- Body sections:
  -  Conclusion: left border accent, light bg
  -  Suggestions: bullet list
  -  Quote / Optimized / Logic: labeled blocks with distinct left border colors
- Non-interactive (display only)

### Progress Indicator
- 5 dots: filled (done) / animated (streaming) / empty (pending)
- Placed between loading state and card area

---

## 5. Responsive Layout

### Breakpoints
```
Mobile:   @media (max-width: 639px)
Tablet:   @media (min-width: 640px) and (max-width: 1023px)
Desktop:  @media (min-width: 1024px)
```

### Layout Changes
| Element | Mobile | Tablet | Desktop |
|---------|--------|--------|---------|
| Nav | Hamburger left, brand center, badge right | Brand left, email + badge right | Same as tablet |
| Upload zone | Full width, compact padding | Max 600px centered | Max 720px centered |
| Result cards | Full width, single column | 2-column grid | Max 720px centered, single column (streaming) |
| Progress dots | Below upload zone | Same | Same |
| Logged-out hero | Compact (2rem padding) | Standard (4rem padding) | Standard |
| Google login | Full-width btn | Inline btn | Inline btn |

---

## 6. Interaction States

### Button States
- **Default**: `--accent` bg, white text
- **Hover**: `--accent-hover` bg
- **Disabled**: gray bg, reduced opacity
- **Loading**: spinner animation on button

### Upload Zone States
- **Default**: dashed `--navy-500` border, neutral text
- **Drag Over**: solid `--accent` border, light blue bg
- **File Selected**: show file info, enable CTA button
- **Error**: red border, error message below

### Card Streaming States
- **Loading**: skeleton placeholder with pulse animation
- **Complete**: fade-in with staggered delay
- **Error**: red indicator with retry option

---

## 7. Accessibility

- All interactive elements must have `:focus-visible` ring styles
- Color contrast: all text meets WCAG AA (4.5:1 for normal, 3:1 for large)
- Upload zone supports keyboard (Enter/Space to open file picker)
- Streaming cards announce via aria-live region
- Touch targets: minimum 44x44px on mobile

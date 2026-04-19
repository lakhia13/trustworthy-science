# Responsive Design Patterns Used

This document describes the CSS and responsive patterns implemented across the Trustworthy Science frontend.

## 1. CSS `clamp()` Function

The `clamp()` function is the main responsive tool. Syntax: `clamp(min, preferred, max)`

### Examples Used in Codebase

```css
/* Font sizes - scale smoothly with viewport */
fontSize: 'clamp(20px, 6vw, 26px)'    /* Title: min 20px, scale with 6% viewport width, max 26px */
fontSize: 'clamp(10px, 2vw, 12px)'    /* Body: min 10px, scale with 2% viewport width, max 12px */
fontSize: 'clamp(11px, 2vw, 13px)'    /* Labels: min 11px, scale with 2% viewport width, max 13px */

/* Spacing - responsive padding/margins */
padding: 'clamp(8px, 2vw, 12px) clamp(10px, 2vw, 14px)'  /* Vertical × Horizontal */
gap: 'clamp(12px, 3vw, 20px)'         /* Grid/flex gap scales with viewport */
marginBottom: 'clamp(24px, 5vw, 32px)' /* Margins scale responsively */
```

### How It Works

When viewport is 100px wide with `fontSize: clamp(10px, 2vw, 14px)`:
- 2vw = 2% of 100px = 2px
- Preferred value (2px) is between min (10px) and max (14px)
- Browser picks the largest of min/preferred: `max(10px, 2px)` = 10px ✓

When viewport is 700px wide:
- 2vw = 2% of 700px = 14px
- Preferred value (14px) is between min (10px) and max (14px)
- Browser picks the smallest of preferred/max: `min(14px, 14px)` = 14px ✓

When viewport is 1200px wide:
- 2vw = 2% of 1200px = 24px
- Preferred value (24px) exceeds max (14px)
- Browser picks the smallest: `min(24px, 14px)` = 14px ✓

## 2. CSS `max()` Function

Used for minimum values with scaling. Syntax: `max(min, preferred)`

### Examples

```css
padding: 'max(16px, 2vw)'  /* At least 16px, but scale up with viewport width */
```

This ensures minimum readability on very small screens while allowing growth.

## 3. Responsive Grid Layout

### Deep Research Left Panel Grid

```typescript
// Fixed grid (old) - breaks on small screens
gridTemplateColumns: 'minmax(300px, 380px) 1fr'  ❌ Forces left panel to fixed size

// Auto-fit grid (new) - wraps responsively
gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))'  ✅
```

How `repeat(auto-fit, minmax(300px, 1fr))` works:
- Each column has minimum 300px and flexible growth (1fr)
- `auto-fit` automatically fits as many columns as fit in the container
- When container < 600px: collapses to 1 column
- When container > 600px: allows 2+ columns
- Each column grows equally with remaining space

### Benefits
- No media query breakpoints needed for basic layout
- Automatically adapts to any screen size
- Smoother transitions as viewport resizes

## 4. Media Queries

Used for targeted behavior at specific breakpoints.

### Breakpoint Structure (Mobile-First)

```css
/* Base styles (mobile/small devices) */
.responsive-grid {
  gap: clamp(12px, 3vw, 20px);  /* Flexible by default */
}

/* Tablet & larger - override as needed */
@media (max-width: 768px) {
  .responsive-grid {
    grid-template-columns: 1fr;  /* Force single column */
  }
  
  .deep-research-left-panel {
    position: sticky;           /* Stick to top when scrolling */
    top: 80px;
    z-index: 20;
    background: rgba(6, 8, 15, 0.95);
    backdrop-filter: blur(12px);
  }
}

/* Small phones */
@media (max-width: 480px) {
  .deep-research-container {
    padding: 12px 16px 100px;   /* Smaller padding */
  }
  
  .responsive-grid {
    gap: 12px;                   /* Tighter spacing */
  }
}

/* Hide elements on small screens */
@media (max-width: 640px) {
  .mini-paper-row-title {
    display: none;              /* Save space */
  }
}
```

### Current Breakpoints

| Breakpoint | Intent | Changes |
|---|---|---|
| Base | Mobile first | Use clamp() everywhere |
| 768px | Tablet mode | Single column, sticky panel |
| 480px | Small phone | Extra padding reduction |
| 640px | Text overflow | Hide non-essential labels |

## 5. Flexible Layouts

### Flex with Wrapping

```typescript
style={{
  display: 'flex',
  flexWrap: 'wrap',           // Items wrap to next line
  gap: 'clamp(8px, 2vw, 14px)' // Responsive spacing
}}
```

### Flex Basis and Growth

```typescript
style={{
  flex: 1,                     // Each button takes equal space
  minWidth: '0',              // Allow items to shrink below content
}}
```

## 6. Text Wrapping Control

### Prevent Button Text Wrapping

```typescript
style={{
  whiteSpace: 'nowrap',       // Prevent text from breaking
  overflow: 'hidden',
  textOverflow: 'ellipsis',
}}
```

### Limit Text Lines

```typescript
style={{
  display: '-webkit-box',
  WebkitLineClamp: 3,        // Max 3 lines
  WebkitBoxOrient: 'vertical',
  overflow: 'hidden',
}}
```

## 7. Popover Positioning

### Fixed Position with Overflow Handling

```typescript
style={{
  position: 'fixed',
  bottom: '32px',             // Safe distance from screen edge
  right: '32px',
  maxHeight: '85vh',         // Don't exceed viewport height
  overflow: 'auto',          // Make scrollable if needed
  zIndex: 200,               // Above other content
}}
```

Why 32px margins:
- Mobile devices often have bezels/notches (typically 20-40px)
- 32px provides visual breathing room
- Ensures popover content is always visible

## 8. Touch-Friendly Sizing

### Minimum Touch Target Size

```typescript
// WCAG AA accessibility standard: 44×44px minimum
// Our buttons typically use:
padding: 'clamp(10px, 2vw, 14px)'  // Height: ~34-48px depending on font size
// With icon + text, easily exceeds 44px
```

## 9. Dynamic Font Sizing Example

```typescript
// Desktop: 26px
// Tablet (900px viewport): 26px (6vw = 54px, clamped to max 26px)
// Tablet (500px viewport): ~23px (6vw = 30px, between min 20 and max 26)
// Mobile (375px viewport): 20px (6vw = 22.5px, but clamped to min 20px)
fontSize: 'clamp(20px, 6vw, 26px)'
```

## 10. Performance Considerations

### Layout Thrashing Prevention

- Use `clamp()` instead of many media queries
- Reduces reflow calculations
- Browser handles responsive scaling natively

### CSS Containment

```typescript
// Could be added to high-level containers for performance
style={{
  contain: 'layout style paint',  // Isolates layout calculations
}}
```

## Common Responsive Patterns Summary

| Pattern | Use Case | Benefits |
|---|---|---|
| `clamp()` for sizing | Typography, spacing | Smooth scaling, fewer breakpoints |
| `max()` for minimums | Padding, margins | Ensures readability at all sizes |
| `repeat(auto-fit)` | Grid layouts | Automatic wrapping, no breakpoint needed |
| Media queries | Dramatic layout changes | Precise control when needed |
| `flexWrap` | Buttons, toolbars | Natural reflow on small screens |
| Sticky positioning | Side panels | Keep UI accessible while scrolling |

## Testing Formula

For any new responsive component, ask:
1. ✓ Does it work at 320px (smallest phone)?
2. ✓ Does it work at 768px (tablet)?
3. ✓ Does it work at 1920px (large desktop)?
4. ✓ Does text remain readable at all sizes?
5. ✓ Are touch targets >= 44px on mobile?
6. ✓ Does it avoid horizontal scrolling?
7. ✓ Are there any layout shifts as viewport resizes?

## Browser Support

All techniques used are supported in:
- ✓ Chrome 79+
- ✓ Firefox 75+
- ✓ Safari 13+
- ✓ Edge 79+
- ✓ iOS Safari 13+
- ✓ Android Chrome 79+

## Further Reading

- [MDN: clamp()](https://developer.mozilla.org/en-US/docs/Web/CSS/clamp)
- [MDN: CSS Grid auto-fit](https://developer.mozilla.org/en-US/docs/Web/CSS/repeat#auto-fit)
- [W3C: WCAG Touch Target Size](https://www.w3.org/WAI/WCAG21/Understanding/target-size.html)
- [Modern CSS for Dynamic Component Sizing](https://web.dev/responsive-web-design-basics/)

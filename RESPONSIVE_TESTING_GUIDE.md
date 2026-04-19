# Responsive Design Testing Guide

## Browser DevTools Testing

### Quick Viewport Tests
You can test the responsive design immediately using your browser's DevTools:

#### Chrome/Edge DevTools
1. Open DevTools: `F12` or `Ctrl+Shift+I` (Windows/Linux) / `Cmd+Option+I` (Mac)
2. Click the device toggle button or press `Ctrl+Shift+M`
3. Select from preset devices or enter custom dimensions:
   - **iPhone 12**: 390 × 844px
   - **iPhone SE**: 375 × 667px
   - **iPad**: 768 × 1024px
   - **Desktop**: 1920 × 1080px

#### Firefox DevTools
1. Open DevTools: `F12` or `Ctrl+Shift+I`
2. Click "Responsive Design Mode" or press `Ctrl+Shift+M`
3. Select devices from dropdown or enter custom dimensions

### Specific Breakpoints to Test

| Breakpoint | Device Type | Test Focus |
|---|---|---|
| **< 320px** | Very small phones | Text wrapping, button sizing |
| **320-480px** | Small phones | Full vertical stack, sticky panel |
| **480-768px** | Tablets/Large phones | Sticky left panel, grid layout |
| **768px+** | Desktop/Large tablets | Two-column grid, hover states |

## What to Look For

### Deep Research Page

#### Desktop (> 768px)
- ✓ Two-column layout visible (config panel on left, results on right)
- ✓ Grid gap looks proportional (~20px)
- ✓ Title is large (~26px) and readable
- ✓ All buttons visible without wrapping

#### Tablet (768px - 480px)
- ✓ Grid collapses to single column
- ✓ Left panel becomes sticky at top with semi-transparent backdrop
- ✓ When scrolling down, left panel stays fixed
- ✓ Padding is reduced but still comfortable
- ✓ Font sizes scale down smoothly

#### Mobile (< 480px)
- ✓ Further reduced padding and gaps
- ✓ All interactive elements are touch-friendly (min 44x44px)
- ✓ Text is still readable (min font size maintained via clamp)
- ✓ No horizontal scrolling
- ✓ Buttons don't wrap text unexpectedly

### Literature Review Viewer

#### All Viewports
- ✓ Toolbar items stack/wrap appropriately
- ✓ Button text doesn't break mid-word (`whiteSpace: 'nowrap'`)
- ✓ Icons and labels stay together
- ✓ Copy/Export buttons remain functional

#### Citation Popover (References Card)
- ✓ Positioned correctly in viewport without overflow
- ✓ On mobile: doesn't go off-screen to the right (right: 32px)
- ✓ On mobile: doesn't go off-screen to the bottom (bottom: 32px)
- ✓ "Open in new tab" button works and opens in new window
- ✓ DOI button works and opens https://doi.org/{DOI}

## Performance Checklist

- ✓ No layout shift on navigation
- ✓ Animations are smooth on viewport changes
- ✓ No console errors or warnings
- ✓ Page loads quickly on simulated slow connection
- ✓ Sticky panel doesn't cause jank when scrolling

## Accessibility Testing

- ✓ All buttons are keyboard accessible (Tab key)
- ✓ Focus states are visible
- ✓ Color contrast meets WCAG AA standards
- ✓ Touch targets are minimum 44x44px on mobile
- ✓ Form inputs have proper labels

## Network Throttling Test

To test on slow connections:
1. Open DevTools → Network tab
2. Set throttle to "Slow 3G"
3. Navigate through Deep Research workflow
4. Verify:
   - Page is usable even if slow
   - Loading indicators are clear
   - Error states are handled gracefully

## Actual Device Testing

### iOS Testing
- Test on iPhone 12/13/14/15 (various orientations)
- Test on iPad Air/Pro
- Check for notch/safe area issues
- Test Portrait and Landscape

### Android Testing
- Test on Samsung Galaxy S21/S23
- Test on Google Pixel 6/7
- Test on various screen sizes (5", 6.5", 7")
- Check keyboard interaction

### Common Issues to Watch For
- Text overlapping buttons on certain viewport sizes
- Horizontal scrollbar appearing unexpectedly
- Touch targets too small for fingers
- Modal/popover appearing off-screen
- Sticky elements not sticking properly

## Automated Testing Commands

```bash
# Build the frontend (should complete with no errors)
cd /Users/jiteshgadage/Documents/Github/trustworthy-science/frontend
npm run build

# Check for TypeScript errors
npx tsc --noEmit

# Run in development mode with hot reload
npm run dev
# Then open http://localhost:5173 in your browser
```

## Chrome Lighthouse Audit

1. Open DevTools → Lighthouse tab
2. Select:
   - Mode: Navigation
   - Device: Mobile / Desktop (test both)
3. Generate report
4. Check:
   - Performance (target: > 90)
   - Accessibility (target: > 90)
   - Best Practices (target: > 90)
   - SEO (target: > 90)

## Note on CSS Units

The page uses modern CSS units:
- `clamp()`: Responsive sizing between min and max
- `max()`: Minimum value with responsive scaling
- `repeat(auto-fit, ...)`: Automatic column wrapping in grid

These are well-supported in modern browsers:
- ✓ Chrome 79+
- ✓ Firefox 75+
- ✓ Safari 13+
- ✓ Edge 79+

Older browsers will fall back to default values (may not be responsive).

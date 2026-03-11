# CHORE-74 QA Bug-Bash Checklist
**Created:** 2026-03-11 01:28 EDT  
**Scope:** Chore completion flow - Edge cases & UX regressions  
**Branch:** `chore/CHORE-74-qa-harness`

---

## Test Environment
- [ ] Backend running on localhost:8000
- [ ] Frontend running on localhost:5173
- [ ] Database seeded with test data
- [ ] Test user authenticated with valid token

---

## 1. Chore Creation Flow

### 1.1 Input Validation Edge Cases
- [ ] **Empty title** → Should reject with clear error
  - Repro: Submit form with empty title field
  - Expected: Validation error "Title is required"
  - Severity: P1 (blocks creation)

- [ ] **Title with special characters** → Should sanitize/escape
  - Repro: Create chore with title `<script>alert('xss')</script>`
  - Expected: Sanitized display, no XSS
  - Severity: P0 (security)

- [ ] **Unicode/emoji in title** → Should preserve
  - Repro: Create chore "Fix bug 🐛 in auth"
  - Expected: Emoji renders correctly
  - Severity: P2 (UX polish)

- [ ] **Extremely long title** (>255 chars) → Should truncate or reject
  - Repro: Submit 300-character title
  - Expected: Validation error or UI truncation
  - Severity: P2 (edge case)

### 1.2 Completion State Transitions
- [ ] **Rapid toggle** → Prevent race conditions
  - Repro: Click "Mark Complete" 5 times rapidly
  - Expected: Single state change, no duplicate API calls
  - Severity: P1 (data integrity)

- [ ] **Complete while offline** → Graceful degradation
  - Repro: Disconnect network, mark complete
  - Expected: Queue action or show error, retry on reconnect
  - Severity: P2 (offline UX)

- [ ] **Undo completion** → Should restore previous state
  - Repro: Mark complete → Undo
  - Expected: Status reverts, timestamps preserved
  - Severity: P1 (core feature)

---

## 2. Chore List Display

### 2.1 Filtering & Sorting
- [ ] **Filter: Active only** → Hide completed
  - Repro: Toggle "Show completed" off
  - Expected: Completed chores hidden
  - Severity: P1 (core feature)

- [ ] **Sort by due date** → Overdue items first
  - Repro: Create chores with past/future due dates
  - Expected: Past dates show first with warning indicator
  - Severity: P2 (UX)

- [ ] **Search with no results** → Helpful empty state
  - Repro: Search for nonsense string
  - Expected: "No chores found" message with clear CTA
  - Severity: P2 (UX)

### 2.2 Pagination Edge Cases
- [ ] **Single item** → No pagination controls
  - Repro: Delete all but 1 chore
  - Expected: No prev/next buttons
  - Severity: P3 (visual noise)

- [ ] **Exactly page size** → Correct page count
  - Repro: Create exactly 10 chores (if page size = 10)
  - Expected: Shows "Page 1 of 1", no next button
  - Severity: P2 (off-by-one)

- [ ] **Last page with 1 item** → Correct display
  - Repro: Navigate to last page with single item
  - Expected: Page renders correctly, prev button works
  - Severity: P2 (edge case)

---

## 3. Completion Timestamp & Metadata

### 3.1 Timestamp Accuracy
- [ ] **Completed timestamp** → Matches action time
  - Repro: Mark complete, check DB timestamp
  - Expected: Within 1 second of action
  - Severity: P1 (data accuracy)

- [ ] **Timezone handling** → User's local timezone
  - Repro: Complete chore, verify displayed time
  - Expected: Shows user's local time, not UTC
  - Severity: P2 (UX)

- [ ] **Date rollover** → Correct across midnight
  - Repro: Complete chore at 23:59, view at 00:01
  - Expected: Displays correct date
  - Severity: P2 (edge case)

### 3.2 Metadata Persistence
- [ ] **Completed by user** → Tracks actor
  - Repro: Mark complete, check metadata
  - Expected: Stores user_id of completer
  - Severity: P1 (audit trail)

- [ ] **Completion notes** → Persists optional comment
  - Repro: Add completion note, reload
  - Expected: Note persists and displays
  - Severity: P2 (feature)

---

## 4. API & Backend

### 4.1 Error Handling
- [ ] **Invalid chore ID** → 404 response
  - Repro: PATCH /chores/99999/complete
  - Expected: 404 with error message
  - Severity: P1 (error handling)

- [ ] **Unauthorized completion** → 403 response
  - Repro: Complete another user's chore
  - Expected: 403 Forbidden
  - Severity: P0 (security)

- [ ] **Database constraint violation** → Graceful error
  - Repro: Force duplicate completion (simulate race)
  - Expected: Clear error, no 500
  - Severity: P1 (stability)

### 4.2 Performance
- [ ] **Bulk completion** → No N+1 queries
  - Repro: Select 50 chores, mark all complete
  - Expected: Single batch query, <500ms
  - Severity: P2 (performance)

- [ ] **Large payload** → Handles 1000+ chores
  - Repro: Fetch list with 1000 items
  - Expected: Pagination prevents full load, <2s response
  - Severity: P2 (scalability)

---

## 5. UI/UX Regressions

### 5.1 Visual States
- [ ] **Loading spinner** → Shows during async action
  - Repro: Slow network, mark complete
  - Expected: Button shows loading state
  - Severity: P2 (UX feedback)

- [ ] **Optimistic update** → Immediate UI change
  - Repro: Mark complete (fast network)
  - Expected: Checkbox updates before API response
  - Severity: P2 (perceived performance)

- [ ] **Error recovery** → Reverts on failure
  - Repro: Force API error, mark complete
  - Expected: UI reverts to uncompleted state
  - Severity: P1 (correctness)

### 5.2 Accessibility
- [ ] **Keyboard navigation** → Tab through list
  - Repro: Use Tab/Enter to complete chores
  - Expected: All actions keyboard-accessible
  - Severity: P1 (a11y)

- [ ] **Screen reader** → Announces completion
  - Repro: Use NVDA/VoiceOver, mark complete
  - Expected: "Chore marked complete" announcement
  - Severity: P1 (a11y)

- [ ] **Focus management** → Returns after modal
  - Repro: Open completion modal, submit
  - Expected: Focus returns to chore item
  - Severity: P2 (a11y)

---

## 6. Mobile/Responsive

### 6.1 Touch Targets
- [ ] **Minimum tap size** → 44x44px
  - Repro: Inspect checkbox on mobile
  - Expected: Touch target ≥44px
  - Severity: P2 (mobile UX)

- [ ] **Swipe gestures** → Swipe to complete
  - Repro: Swipe chore right on mobile
  - Expected: Reveals complete action
  - Severity: P3 (enhancement)

### 6.2 Layout
- [ ] **Small screens** → No horizontal scroll
  - Repro: View on 320px width
  - Expected: Content wraps, no overflow
  - Severity: P2 (responsive)

- [ ] **Tablet portrait** → Optimal layout
  - Repro: View on iPad portrait (768px)
  - Expected: List readable, actions visible
  - Severity: P2 (responsive)

---

## Severity Definitions
- **P0:** Security vulnerability or data loss
- **P1:** Blocks core functionality or causes incorrect behavior
- **P2:** Degrades UX or affects edge cases
- **P3:** Minor polish or enhancement

---

## Test Execution Log

### Run 1: [DATE/TIME]
**Tester:** [NAME]  
**Environment:** [local/staging/prod]  
**Commit:** [HASH]

| Test ID | Status | Notes |
|---------|--------|-------|
| 1.1.1   | ⬜ PENDING | |
| 1.1.2   | ⬜ PENDING | |
| ...     | ...    | ... |

**Summary:**
- Total: X
- Passed: Y
- Failed: Z
- Blocked: W

**Critical Issues:**
1. [Issue description with repro steps]
2. [Issue description with repro steps]

---

## Sign-Off
- [ ] All P0/P1 issues resolved
- [ ] Regression test suite updated
- [ ] Documentation updated
- [ ] Ready for release

**QA Lead:** ___________  
**Date:** ___________

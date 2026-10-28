# Desktop interface, version 2.2

## Direction

Use a minimal, functional desktop layout with strong number hierarchy, a quiet light background and a dark teal balance panel. The UI/UX Pro Max search identified Minimalism & Swiss Style as suitable for tools and dashboards. Its landing-page structure and remote font recommendations do not apply to this Windows utility. A supplementary product-category query produced no verified match; desktop structure follows general interface guidance.

Implementation remains Python Tkinter with themed native ttk controls. No new runtime dependency or network-loaded font is required. Text uses the installed Microsoft YaHei UI family; color tokens live in `desktop_ui.py`.

## Hierarchy

1. Header identifies the app and shows textual connection state.
2. Left column presents the recorded balance, update time, supporting metrics and refresh action.
3. Login form groups visible field labels, manually entered CAPTCHA, opt-in credential storage and nearby validation feedback.
4. Right column contains separate automatic refresh and automatic offline controls. Offline actions use warning copy and destructive styling.
5. Task status shows the scheduler countdown; the footer reports network results and errors.

No invented package total or progress percentage is shown. The app cannot derive a reliable allowance percentage from the available response.

## Interaction and accessibility

- One primary refresh action; login and CAPTCHA actions are secondary, offline is distinct.
- Buttons disable while requests run, with an indeterminate progress indicator in reserved space.
- Native keyboard traversal, visible focus, pasteable password fields, Enter in the CAPTCHA field, and Ctrl+R to refresh.
- Empty login fields show a nearby message and receive focus without sending a request.
- A single scrolling body keeps controls reachable in shorter windows; focused controls scroll into view.
- Status uses explicit text, so color is not its only signal.
- No ornamental animation, external web assets or telemetry.

## Validation

Check both 1040×850 and 900×620 logical-pixel windows, native screenshot rendering, readable contrast pairs, long result messages, form validation, loading-state layout stability, and existing encrypted-storage / timer regression tests. Preview data must be synthetic and remain outside Git.

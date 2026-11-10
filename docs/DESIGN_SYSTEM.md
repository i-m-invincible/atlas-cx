# Atlas CX UI and UX Specification

Organic design system · Version 1.0 · 8 November 2026

Atlas CX brings customer context, support requests, activity, knowledge, and follow-up work into one workspace. This specification defines its public landing page, staff application, and customer demo portal. It is a design handoff, not an implemented product or a report of completed usability testing.

Use this document with **Atlas_CX_Product_and_Engineering_Specification.md**, reviewed for scope, workflow, permissions, and intelligence behavior. The companion **Atlas_CX_Wireframe_Atlas.pdf** provides annotated static wireframes for the landing page and all nine requested screens at 1440, 1024, 700, and 390 px. They show layout and reading order, not screenshots of a working application. Bracketed names and empty metric marks in wireframes are placeholders, not customer records or business results.

## 1 Authority and scope

The full original Organic prompt appears unchanged in Appendix A and is the final visual authority. Preserve its exact colors, font bindings, composition principles, motion timing, and control radius. The specific internal-application requirements in the brief determine how expressively those patterns are used: editorial fields and irregular forms on the landing page; straight reading alignment, predictable controls, and restrained surfaces inside the product. Do not copy decorative landing-page treatments into operational tables.

Product behavior and permission boundaries remain governed by the product specification. This document refines navigation grouping and presentation without adding integrations, changing states, altering analytics formulas, or giving additional access. Accessibility requirements constrain which token combinations and decorative arrangements may be used; they do not require changing the supplied palette.

### 1.1 Three connected surfaces

| Surface | Purpose | Organic expression |
| --- | --- | --- |
| Public landing page | Explain the problem, intended workflow, scope, and demo access | Broad clay/moss fields, editorial serif headings, asymmetry, quiet irregular shapes, faint paper grain |
| Staff application | Understand and complete work | Sand ground, paper work surfaces, brown text, moss controls, ruled rows, modest asymmetric control corners |
| Customer portal | Submit and follow a personal request | Simple paper layout, welcoming serif title, plain status language, minimal navigation |

The requested enterprise style means clear hierarchy, dependable interaction, and dense but readable information. It does not imply SSO, external channel integrations, production certifications, or an enterprise customer base.

### 1.2 Non-negotiable scope boundaries

- Inbox messages are delivered in the authenticated portal. Manually logged email/phone requests retain their origin label but do not create a connected channel.
- Internal notes, health, operational targets, staff tasks, customer events, and staff knowledge never appear in the customer portal.
- Portal users see only cases they personally requested, even when another contact belongs to the same customer account.
- Case states are New, Open, Awaiting customer, Resolved, and Closed. “Awaiting customer” is the default display label for pending_customer; configured labels must preserve the meaning.
- Health is rules-based, with evidence coverage and freshness. Never use “churn probability,” “AI confidence,” or predictive risk claims for it.
- The assistant searches approved staff knowledge. It produces a draft or source excerpts and cannot send messages, change records, or execute customer actions.
- No product screenshot, customer testimonial, usage count, time-saving claim, logo wall, or performance statistic is invented.

## 2 Color, surface, and contrast rules

### 2.1 Authoritative palette

| Token | Exact value | Assigned use |
| --- | --- | --- |
| --dp-color-ground | #eee6d6 | Page canvas and outer application shell |
| --dp-color-surface | #f5eddf | Reading surfaces, forms, tables, inverse text on dark fields |
| --dp-color-ink | #29251d | Primary text, important icons, dark focus outline on pale surfaces |
| --dp-color-primary | #35422d | Primary actions, selected navigation, moss fields, success labels |
| --dp-color-field | #694737 | Clay editorial fields, warning/error text and symbols on pale surfaces |
| --dp-color-art-accent | #ad7d62 | Decorative terracotta shapes; occasional non-text accent |
| --dp-color-surface-muted | #ddd5c3 | Quiet bands, nonessential row separators, inactive decorative areas |
| --dp-color-highlight | #b9b28b | Selected-row backgrounds, attention bands, small decorative forms |
| --dp-color-ink-muted | #443b2f | Secondary text, metadata, table labels, meaningful control borders |

Do not introduce extra semantic reds, greens, purples, gradients, or arbitrary opacity-adjusted text colors. State meaning combines text, shape, and a symbol. Clay can express both warning and error because their explicit labels and icons distinguish them.

### 2.2 Computed contrast pairs

Ratios below were calculated from the exact supplied sRGB values using WCAG relative luminance. Values are rounded to two decimals for display; do not round a failing value upward to approve it. Normal text requires at least 4.5:1; qualifying large text at least 3:1. Required UI boundaries and state graphics need 3:1 against adjacent colors where the relevant criterion applies. [A1, A2]

| Foreground / background | Ratio | Decision |
| --- | --- | --- |
| Ink / ground | 12.29:1 | Body, labels, headings |
| Ink / surface | 13.12:1 | Body, tables, forms |
| Muted ink / ground | 8.85:1 | Secondary reading |
| Muted ink / surface | 9.44:1 | Metadata and placeholder text |
| Surface / moss | 9.18:1 | Primary action labels and moss-field reading |
| Surface / clay | 7.06:1 | Clay-field reading and actions with adequate boundaries |
| Ink / highlight | 7.12:1 | Selected rows and attention text |
| Moss / muted surface | 7.30:1 | Selected navigation and useful iconography |
| Surface / terracotta | 3.07:1 | Not permitted for normal text; decorative use preferred |
| Ink / terracotta | 4.28:1 | Fails normal text; do not place compact labels on it |
| Muted surface / surface | 1.26:1 | Decorative divider only; not a required input boundary |
| Moss / clay | 1.30:1 | Do not use adjacent unoutlined moss controls on clay |

A primary moss action on clay uses a paper-colored outer border so the control is identifiable; its label stays paper. A paper action with moss text is an equally valid inverse variant. Light labels on dark sections use the surface token, not white. Never put a low-opacity grain or decorative overlay between the foreground and its tested background.

### 2.3 Focus, selection, and disabled appearance

On pale ground/surface/muted/highlight, use a 2 px ink outline at 3 px offset. On moss/clay, use a 2 px paper outline at 3 px offset. For mixed or image-backed surroundings, add a solid opposite-tone 2 px backing halo so the outer visible ring retains contrast. Focus is outside the control and must not be clipped by a rounded parent, scroll container, or irregular section mask.

Selected navigation uses a moss leading rule and a muted-surface fill, plus aria-current. Selected rows use highlight fill and an inset 2 px moss outline; a checkmark and accessible selected state reinforce meaning. Hover is not selection. Pressed is not success. Focus remains visible in every state.

Unavailable actions remain readable: muted-surface fill, muted-ink label, no hover fill, and an inline reason when the restriction is meaningful. Do not reduce opacity on an entire control. Hide controls for permissions the user never has; disable an otherwise permitted action when a recoverable precondition is missing, with explanatory text.

### 2.4 Surface and decoration budget

Landing page: one continuous faint paper grain behind large fields; maximum three decorative forms in one composition. Shapes occupy empty space, stay still, and never obscure text. No repeated blob-card grid. Use asymmetrical section corners only at the broad field boundary. A shape’s rotation is at most 4 degrees; text and controls stay upright. Grain must be decorative, noninteractive, and excluded from accessibility output.

Staff app: no grain behind tables, chart plots, long reading, or inputs. A faint shell grain is optional and must not change measured contrast. Decorative forms are limited to a quiet onboarding/empty-state illustration; they are never part of a status symbol. Use one paper work surface with rules, not a collection of floating cards. No deep shadows; overlays may use a single subtle separation shadow, with a visible border as the primary edge.

## 3 Typography, spacing, and geometry

### 3.1 Font bindings and delivery

Bind Source Serif 4 to “Organic Source Serif”; bind Instrument Sans to “Organic Instrument Sans.” Use self-hosted, licensed WOFF2 files in the future application with font-display swap and a tested fallback. Serif fallback is Georgia; sans fallback is a system sans. Reserve the correct line height before fonts load. Do not substitute a different brand font because it looks similar.

Use Source Serif 4 medium weight, 500, for public statements and staff page titles. Use Instrument Sans 400 for reading, 500 for labels, and 600 for active controls/table headings. Avoid faux bold, all-caps paragraphs, and very light weights. Use tabular numerals in data columns and time values. Do not use serif numerals for operational metrics; large serif step numbers belong only on the landing page.

| Role | 1440 / 1024 / 700 / 390 px font size | Line height and rule |
| --- | --- | --- |
| Landing hero | 64 / 52 / 44 / 38 px | 1.06; tracking -0.025em; maximum 13–16 characters per short line where copy permits |
| Landing section heading | 42 / 36 / 34 / 30 px | 1.12; tracking -0.015em |
| Staff or portal page title | 32 / 30 / 28 / 28 px | 1.18; no truncation of meaningful title |
| Panel heading | 18 px throughout | Instrument Sans 600; 1.4 |
| Reading/body | 16 px throughout | 1.8 for explanatory prose and knowledge; compact context may use 1.5 |
| Small reading | 15 px throughout | 1.6; summaries and helper copy |
| Control/table | 14 px throughout | 1.4; input text becomes 16 px on touch/mobile layouts |
| Caption | 13 px throughout | 1.5; nonessential clarification only |
| Metadata | 12 px throughout | 1.5; timestamps/version labels only, never the only form instruction |

Maintain prose widths of 55–70 characters, assistant/knowledge reading at 65 characters maximum, and conversation messages at 70 characters maximum. Do not reduce text below the table size to fit additional columns. User text enlargement and custom text spacing must not clip labels or conceal actions.

### 3.2 Spacing and component geometry

Use a 4 px base spacing scale: 4, 8, 12, 16, 24, 32, 48, 64, 96. Preserve the authoritative content gap of 24 px. Dense row internals may use 8 or 12 px; page sections use 24 or 32 px; landing groups use 64–96 px.

Controls preserve the exact authoritative asymmetric radius: 27px 19px 29px 16px / 22px 26px 19px 29px. Apply it to action buttons and pills with sufficient internal padding, not to the hit-area or text alignment. Inputs use a restrained 8 px corner radius, table work surfaces 12 px, popovers 12 px. These are local application geometry decisions, not replacements for the authoritative action radius.

Default control height is 40 px desktop; touch layouts use 44 px. Primary landing and portal form actions are 48 px. Icon-only buttons use a 40 × 40 px desktop box and 44 × 44 px touch box with a 20 px icon. Table rows are at least 48 px; multi-line rows grow naturally. Compact metadata does not shrink the surrounding hit area. Maintain at least 8 px between adjacent standalone touch controls.

Use 1 px hairlines. Meaningful input boundaries use muted ink; quiet dividers can use muted surface because grouping and labels do not rely on those lines alone. Icons are simple 1.5–2 px strokes with distinct shapes and accessible names. No sparkles, glowing AI mark, animated orb, or decorative AI avatar.

### 3.3 Motion

Color/background/border changes use the authoritative 240ms ease. Pointer press may scale a primary button to 0.98 inside its unchanged hit box; it must not move surrounding content. Shapes, sections, lists, and metric values do not animate into place. No count-up numbers, parallax, autoplay demonstrations, shimmer skeletons, or automatic carousels.

For prefers-reduced-motion, remove interaction transitions and transforms completely. Keyboard activation does not need a scale effect. Loading is conveyed through text, aria-busy, and optional static progress marks rather than relying on rotation.

## 4 Global structure and responsive contract

### 4.1 Navigation grouping

| Staff navigation label | Routes and content | Relationship to product specification |
| --- | --- | --- |
| Overview | /app/overview | Same operational summary |
| Customers | /app/customers and /app/customers/:id | Customer 360 is a detail page, not a separate nav item |
| Support | /app/support/inbox, /app/support/cases, /app/support/cases/:id | Groups Inbox and Cases; both views remain available |
| Analytics | /app/analytics/activity and /app/analytics/service | Requested Activity Analytics plus operational service metrics |
| Knowledge | /app/knowledge/library and /app/knowledge/assistant | Groups approved library and knowledge assistant |
| Follow-ups | /app/follow-ups/tasks and /app/follow-ups/feedback | Groups Tasks and Feedback |
| Settings | /app/settings/:section | Permission-aware workspace administration |

These are frontend routes; API paths remain those in the product contract. The public landing route is /. Staff sign-in and portal sign-in are separate destinations with clear audience labels. The demo portal lives under /portal and never inherits staff navigation. No global cross-entity command search is introduced: search controls belong to the current list or library.

Staff shell reading order: skip link, workspace/header controls, primary navigation, page heading, local tabs, filters, main content, supplementary context, feedback/status messages. DOM order follows this reading order. Do not visually reorder a context panel ahead of its related case. A single page H1 is followed by properly nested section headings.

### 4.2 Exact breakpoint behavior

| Width | Staff shell | Content dimensions | Information behavior |
| --- | --- | --- | --- |
| 1440 px | 224 px labelled sidebar; 64 px top bar | Content region 1216 px; 32 px side gutters; 1152 px usable | Wide tables; inbox three panes; context panels visible where specified |
| 1024 px | No persistent sidebar; labelled Menu button opens drawer; 64 px top bar | 24 px side gutters; 976 px usable | Two-column work where it fits; inbox list + conversation, context via separate view |
| 700 px | Same drawer shell; 60 px top bar | 20 px side gutters; 660 px usable | Single main column; list/detail routes; filters in disclosure/dialog; no miniature three-pane inbox |
| 390 px | 56 px top bar with Menu, title/workspace, account | 16 px side gutters; 358 px usable | One task per view; stacked forms and row summaries; full-width primary form actions |

Persistent navigation applies only at widths of at least 1200 px. Wide content layout begins above 1000 px; at 1000 px and below, tighten splits and use the narrower layout. At 700 px and below, stack editorial sections and main reading. At 480 px and below, use phone spacing. These rules govern in-between widths; they are not independent mockups that leave gaps.

Component minimums can trigger stacking earlier: a two-pane inbox needs 280 px for the list, a 16 px gap, and at least 440 px for the conversation; below 736 px usable content, use sequential routes. An answer/source split needs at least 480 px for the answer, 24 px gap, and 280 px for sources; below 784 px usable content, stack sources after the answer. Never squeeze these regions just to retain a breakpoint label.

Landing maximum content width is 1280 px: at 1440, 80 px margins; at 1024, 40 px; at 700, 24 px; at 390, 20 px. Landing uses a 12-column grid on wide layouts, 8 at 1024, and one reading column at 700/390. Facts/scope statements may retain two columns until 390 if each remains readable. Footer links stay in two columns.

The staff drawer is a modal navigation surface: width 288 px or viewport minus 32 px, whichever is smaller. It has a visible Close button, heading, active link, workspace label, and account links. Escape closes it and focus returns to Menu. Selecting a destination closes it and places focus at the destination H1 after loading.

### 4.3 Scroll and navigation behavior

Use page scrolling for normal screens. On wide inbox only, the case list and conversation may scroll independently with labelled regions; preserve a minimum of 320 px vertical conversation space. At short heights, 200% zoom, or width 700 and below, remove that multi-scroll layout and use normal page flow. Sticky bars never cover a focused control; set scroll offsets and verify both top and bottom occlusion.

At narrow widths, selecting a case or customer changes to a full detail route. A visible “Back to inbox” or “Back to customers” restores filters, sort, cursor position, and focus to the invoking record. Context becomes a Details tab or inline disclosure on that route, not an inaccessible off-screen panel. A modal filter panel is allowed; a full edit form on mobile is a page.

Use “Load more” cursor pagination with visible progress rather than inventing a total page count. Load more keeps focus on its control and announces the number of added records. No infinite-scroll-only navigation. URLs preserve non-sensitive filter state; never put message bodies, email addresses, secrets, or assistant questions in URLs.

### 4.4 Wireframe notation

The atlas uses real palette tokens and labelled regions. Fine copy is schematic where a viewport is shown at reduced size; refer to this specification for actual text and sizes. The four viewport widths are explicit on each page. Top-of-page views may continue below the frame and are labelled accordingly. A wireframe is not evidence that browser reflow, keyboard behavior, or assistive-technology output has been tested.

## 5 Shared components and interaction states

### 5.1 Component inventory

| ID | Component | Variants and required behavior |
| --- | --- | --- |
| C01 | Application/portal shell | Labelled desktop nav, drawer nav, skip link, active route, account menu; distinct portal identity |
| C02 | Button | Moss primary, outlined secondary, text action, clay destructive; icon+text or named icon-only; default/hover/focus/pressed/busy/disabled |
| C03 | Text and numeric field | Persistent label, required/optional marker, helper, invalid message, read-only; visible clear action only for search |
| C04 | Select/combobox | Native select when practical; searchable combobox only for long customer/member lists; accessible empty result and chosen value |
| C05 | Checkbox/radio/switch | Full labelled hit area; mixed state only when meaningful; switch only for an immediately applied binary setting with recoverable failure |
| C06 | Tabs and disclosures | Tabs for peer views; disclosure for optional detail; distinct selected/open state; no hover-only expansion |
| C07 | Table/list | Semantic headers, linked primary cell, sort button with aria-sort, row menu, Load more; narrow view uses labelled record summaries |
| C08 | Filter bar | Search, relevant selects, Apply when needed, Clear filters, active-filter summary, removable tokens with named remove buttons |
| C09 | Status label | Text plus optional symbol, no color-only meaning; New/Open/Awaiting customer/Resolved/Closed; health and indexing use separate vocabularies |
| C10 | Context panel | Definition list, related links, status explanation; visible wide panel, Details view narrow |
| C11 | Message and composer | Public reply/internal note tabs, author/time, separate drafts, clear submit label, safe Markdown/text, error retention |
| C12 | Timeline | Ordered events with source/kind and timestamp; expand details using a button; not a decorative connected-dot chart |
| C13 | Dialog/drawer | Title, visible close, correct focus entry/return, modal trap only when modal, no nested dialogs |
| C14 | Alert/status | Inline validation, persistent error banner, polite success/status; toast only as redundant confirmation |
| C15 | Skeleton/empty state | Static same-shape placeholders; specific next action; distinguish no records from no matches and unavailable data |
| C16 | Chart with data table | Direct labels, named axes/unit, sample count, filters, accessible equivalent table; no invented series |
| C17 | Health explanation | Band, score or Unknown, coverage, freshness, component rows, linked input evidence |
| C18 | Knowledge article/source | Status, version, active/previous relation, excerpt and heading, citation link; revoked content suppressed |
| C19 | Assistant result | Question, queued/running/generated/sources-only/abstained/failed, source list, review instruction, explicit Use draft |
| C20 | CSV import review | Choose file, preview, row errors, create/update counts from server, commit/cancel, persistent result |
| C21 | Unsaved changes prompt | Keep editing or Discard changes; do not suggest drafts are saved remotely |
| C22 | Rating group | Five labelled radio choices, comment, Submit feedback; no star-only inaccessible control |
| C23 | Configuration/version review | Draft/current/published markers, changed-field summary, impact statement, explicit Publish |

### 5.2 Universal states and exact copy

| Condition | Presentation and copy | Interaction |
| --- | --- | --- |
| Initial fetch | Static placeholders in stable regions; “Loading customers…” or equivalent | Region aria-busy; preserve page heading; no fake numbers |
| Refresh with prior data | Keep old content; small “Updating…” label; show prior Updated time | Do not announce every polling cycle; never blank the whole page |
| Empty collection | “No customers yet.” / “Add a customer to start keeping their requests and activity together.” | Add customer if permitted; otherwise “Ask a workspace administrator to add a customer.” |
| No filter matches | “No customers match these filters.” | Clear filters; retain search text until user clears it |
| Fetch error | “We couldn’t load customers. Try again.” | Retry same request; keep filters; technical request ID behind Details |
| Save pending | Button label “Saving…” or “Sending…”; region busy | Block duplicate submission; preserve current values |
| Save success | “Customer updated.” / “Reply posted to the portal.” | Inline confirmation plus polite status announcement; move focus only when navigation requires it |
| Save failure | “Your changes weren’t saved. Review the error and try again.” | Preserve values; focus summary for validation; no false success toast |
| Version conflict | “This case changed while you were editing. Your draft is still here.” | Review latest; keep draft; explicit reapply/resubmit after comparison |
| Session expired | “Your session expired. Sign in to continue.” | Sign-in destination; keep unsent text only in the same tab’s memory while possible; do not promise recovery after closing it |
| Forbidden operation | “You don’t have permission to make this change.” | No retry loop; relevant owner/admin guidance |
| Missing/inaccessible record | “This request isn’t available.” | Return to accessible list; do not reveal another account’s existence |
| Rate limit | “Too many requests. Try again in [server-provided interval].” | Re-enable according to Retry-After; interval must be real |
| Stale data | “Last updated [time]. This information may be out of date.” | Keep timestamp and context; do not present a current positive indicator |

Place success status in a persistent, stable location within the relevant screen until the next action or navigation. Optional toast lasts at least eight seconds, pauses while hovered/focused, and is never the sole confirmation. Announce errors once; repeated background failures do not flood live regions. Avoid moving focus for routine successful refreshes.

### 5.3 Keyboard behavior

Native links use Enter; buttons use Enter/Space. Tab follows reading order; never assign positive tabindex. Menus follow the menu pattern only if they are actual action menus; ordinary navigation stays a list of links. Tabs use Left/Right, Home/End, and Enter/Space with manual activation when loading a new panel would be slow. A focused tab is visibly different from an active tab.

Searchable comboboxes support arrow selection, Enter to commit, Escape to dismiss without destroying the current value, and a labelled clear control. Tables remain semantic tables with ordinary focusable links/buttons, not ARIA grids with invented spreadsheet navigation. No keyboard shortcut is required to complete a task. If future shortcuts are added, avoid unmodifiable single-character shortcuts.

Textareas use Enter for a newline. Public replies are sent only by the visible Send reply button; do not bind bare Enter. Optional Ctrl/Cmd+Enter is deferred until it has an explicit discoverable preference. Escape never discards a message draft silently.

Dialogs move focus to a meaningful heading or first field, trap focus, make the background inert, and return focus to the opener. Escape closes unless unsaved changes require the same confirmation used by the Close action. Place focus on the safe choice in destructive confirmation. Nonmodal context panels do not trap focus. [A3]

## 6 Public landing page

**Job:** understand the proposed product, follow a concrete support workflow, and find an honest route into the demo. **Primary action:** “Open demo sign-in.” Before a deployed demo exists, replace this action with “Read the product specification”; do not leave a dead demo button or fake signup flow. The secondary action is “See the workflow,” an in-page anchor.

### 6.1 Wireframe and reading order

| Order | Region | Wide-layout specification and content |
| --- | --- | --- |
| L01 | Quiet header | Wordmark left; Product, Workflow, Use cases anchors; Staff sign-in at right when available. 80 px high; no mega-menu. |
| L02 | Editorial hero | 5-column heading/action block; 7-column still arrangement of paper, moss, clay, and terracotta forms. H1: “Keep customer context close to the work.” Body: “Atlas CX brings customer records, support requests, activity, and approved knowledge into one workspace.” No invented social proof. |
| L03 | Scope tray | Broad paper sheet overlapping the hero base by 24 px only on wide screens. Three textual facts: “One customer history”; “A shared support workflow”; “Answers linked to sources.” Label these as product capabilities, not measurable results. Unequal corner curves; contents aligned to grid. |
| L04 | Problem and approach | One continuous clay field. Left heading: “A request rarely comes with the whole story.” Right: three short problems paired with intended responses: scattered context → customer timeline; unclear ownership → assigned cases; policy search → approved knowledge. Paper text. |
| L05 | Connected capabilities | Open ruled lists on sand, not nine cards. Group “Understand the customer,” “Handle the request,” and “Learn from the work.” List Customer 360/activity/health; inbox/cases/knowledge; feedback/tasks/analytics. Each group explains a relationship, not a slogan. |
| L06 | Support workflow | Continuous moss basin with four large serif step numbers and light rules: Request arrives; Agent reviews context; Reply uses approved knowledge; Resolution leads to follow-up. A labelled schematic case occupies the supporting area. No autoplay. |
| L07 | Product view | When real screenshots exist, show a legible inbox crop and one customer-context detail with captions. Until then show the schematic labelled “Design preview”; never label it a screenshot. No fabricated charts in the preview. |
| L08 | Industry applications | Five broad ruled rows: SaaS, Services, E-commerce, Education, Subscriptions. Each has one example request and example configured field. Explicit copy: “The same case workflow, configured for different work.” Do not imply live integrations. |
| L09 | Closing action | Quiet serif invitation: “Follow a request from intake to resolution.” Demo sign-in/specification action and explanation of provisioned access. One still organic form in unused space. |
| L10 | Minimal footer | Muted-surface/stone field; product name, product scope, accessibility/contact links only if those pages/channels exist. Link groups in two columns; no invented company address or legal certification. |

The decorative hero artwork is an abstract arrangement about connected work; earth colors do not imply sustainability. Optional later photography must depict real materials or places, use mild sepia/desaturation, have recorded usage rights, and carry meaningful alt text only if informative. Stock office portraits and testimonial quotations are not required.

### 6.2 Responsive specification

| 1440 | 1024 | 700 | 390 |
| --- | --- | --- | --- |
| 1280 px content; 5/7 hero split; heading 64 px; tray overlaps 24 px; workflow uses two aligned columns | 944 px content; 45/55 hero split; heading 52 px; fewer/smaller shapes; overlap reduced to 16 px | 652 px content; copy first then artwork; hero 44 px; tray in normal flow; all clay/moss content stacked in reading order; no rotated text | 350 px content; hero 38 px; compact artwork after actions; scope tray one column; industry identity/example/action stacked; two-column footer |

At 1024 the header anchors may remain if they fit; at 700 and below collapse to a labelled Menu disclosure. “See the workflow” scroll respects reduced motion and places focus at the target heading when activated by keyboard. For unsupported demo access, explain “Demo access is provisioned for a guided walkthrough”; do not create an unimplemented contact form.

### 6.3 States and acceptance

Fonts loading use reserved sizes and fallback fonts without invisible text. Missing screenshot assets remove the screenshot region or show the clearly labelled schematic; no broken-image placeholder. Navigation focus remains visible on every field. The page must be useful with decorative assets disabled. Success for the CTA is arrival at a real sign-in/specification destination, not a celebratory animation.

## 7 Overview

**Job:** decide what needs attention now. **Primary action:** “Open unassigned cases.” **Do not show:** fabricated revenue, churn forecasts, growth percentages, or a grid of unrelated KPI cards.

### 7.1 Wireframe and layout

Page heading “Overview” is followed by a plain workspace/timezone line and “Updated [time].” A single ruled summary strip contains four labelled operational values from the server: Unassigned, Overdue, My open tasks, and Recent low ratings. Each label and value is one named link to the corresponding filtered list. Unavailable values show “Unavailable”; empty known counts show 0. No decorative sparklines.

Below, use a two-column work surface at 1440: 744 px attention list, 24 px gutter, 384 px supporting column. Attention rows show case reference/subject, customer, reason for attention, owner, and next action. Supporting content contains “My next tasks” followed by “Recent feedback,” as ruled lists. This is an operational worktable rather than separate raised cards.

Default overview scope is current workspace; “My” applies only to the task list and its summary value. Recent low ratings means ratings 1–2 in the last seven days, labelled with that period; this is a filtered view, not a new analytics formula. If the server cannot supply a metric, do not synthesize it from a partial page of results.

### 7.2 Responsive specification

| 1440 | 1024 | 700 | 390 |
| --- | --- | --- | --- |
| Four-value strip, 744/384 work split | Four-value strip, attention 60% / tasks 40% after 24 px gap | Summary values 2×2; attention list followed by tasks and feedback | Summary values 2×2 with wrapped labels; each attention row stacks subject/customer, reason, owner/action |

### 7.3 States and actions

Loading holds each region’s height with static row placeholders. Empty attention: “No cases need attention right now.” It does not claim all customers are satisfied. Empty tasks: “You have no open follow-up tasks.” Partial error: keep working regions and show “We couldn’t load recent feedback. Retry.” Refresh preserves row focus. An overdue link opens Support/Cases with the exact filter and visible reason. Viewer sees the same permitted information but no mutation actions.

## 8 Customers

**Job:** find the right record and see who owns the relationship. **Primary action:** “Add customer.” Manager/admin secondary action: “Import CSV.”

### 8.1 Wireframe and layout

Header: Customers, short count only if server-provided, primary and secondary actions. Filter bar: labelled “Search customers,” lifecycle, owner, health, and More filters containing tag/archive options. Active filters and Clear filters sit below, not inside search placeholder text.

Desktop table columns, in order: Customer (28%); Type (10%); Owner (16%); Lifecycle (12%); Health (14%); Last activity (16%); Actions (4%). Percentages are initial allocation within the table; widths may grow for real content. Customer name is a link; the whole row is not a hidden button. Include external ID in secondary text when useful. Health reads “Watch · [score]” or “Unknown,” with “Stale” when appropriate. “No recorded activity” replaces a fabricated date. Sorting is limited to Name and Created as supported by the contract; Last activity and Health are not clickable fake sort controls.

The add/edit form uses a normal detail page: name, type on create, lifecycle, owner, external ID, tags, activity tracking settings in a labelled optional section. Do not expose implementation names such as activity_expected as labels. “Expect product activity” and “Tracking began” include helper text about missing events. A contact form is separate; adding a customer does not silently create portal access.

CSV flow: choose a file → preview → commit → result. Preview shows row number, proposed create/update, errors, and normalized fields. Commit stays disabled while errors exist, with “Fix the rows listed below before importing.” Counts come from validation. Never show “Import complete” before server commit. Closing after validation may discard staging, with clear copy.

### 8.2 Responsive specification

| 1440 | 1024 | 700 | 390 |
| --- | --- | --- | --- |
| Full seven-column table; inline search and three filters | Name, Owner, Lifecycle, Health, Actions; Type and last activity available through row details; search then filter row | Labelled record list: name/type, owner/lifecycle, health/activity; Filters opens modal panel; actions beside heading when fit | Name first, owner and lifecycle on next line, health/activity below; Add customer full-width if needed; Import in labelled secondary action menu |

Switching table/list representation must not duplicate records in the accessibility tree. Do not lose fields entirely at smaller widths: include them in expanded details or Customer 360. CSV error tables can scroll horizontally within a named region because their column relationships matter; provide a row-error summary above it.

### 8.3 States and copy

Empty: “No customers yet.” / “Add a customer to connect their requests, activity, and follow-ups.” No matches: “No customers match these filters.” Duplicate identity: “This external ID is already in use in this workspace. Review the existing customer.” Only link the existing record when authorized. Save success: “Customer added.” Archiving requires explaining unresolved cases/tasks and uses the existing product rules. There is no generic Delete customer action.

## 9 Customer 360

**Job:** understand one customer’s history and decide the next useful action. **Primary action:** “Create case”; secondary “Create follow-up.”

### 9.1 Wireframe and layout

Top: Back to customers; customer name; type/lifecycle; owner; actions. Keep account identity separate from portal contact identity. The summary includes external ID, tags, and contact count when available, with no invented spend or subscription value.

Use a 744 px reading/work region and 384 px context region, separated by 24 px. Work tabs: Timeline, Cases, Activity, Follow-ups. Timeline is default, with filters for messages, state changes, events, tasks, and feedback. Entries include an explicit kind, time, actor/source, and linked record. Do not merge two unrelated events into a generated story.

Context region: Health explanation first, then Contacts and ownership. Health displays band, score or Unknown, coverage, as-of time, and stale label if needed. Expand component rows for Activity, Service, Feedback, showing window and counts. “No feedback recorded” stays distinct from positive feedback. Customer notes are not a new arbitrary CRM feature; use case notes or supported fields.

Contact detail shows name and permitted contact information, plus portal access state for admins. Portal provisioning appears as an explicit administrative action, not “Send invite” when no email is sent. Use “Create setup link,” with “Share this link through a verified channel.”

### 9.2 Responsive specification

| 1440 | 1024 | 700 | 390 |
| --- | --- | --- | --- |
| 744/384 layout; tabs and health visible together | Main 60%, context 40%; long contact values wrap; heading/actions may use two rows | Summary, compact health strip and expandable explanation, tabs, content; contacts in a labelled disclosure | Identity and actions stacked; tab labels wrap as ordinary view links if they cannot fit; health explanation in normal flow; one primary action per line |

No sticky right panel below 1024. A “View health details” button expands in place and retains focus; collapse returns focus to its trigger. Timeline filtering uses the URL and preserves customer identity. On narrow layouts, details opened from an entry have a clear Back link.

### 9.3 States and copy

No activity: “No activity has been recorded for this customer.” Add “Check tracking setup before interpreting inactivity” when tracking is expected. Unknown health: “Not enough information to calculate health yet.” Stale: “This score was last calculated [time].” Timeline empty: “No recorded activity yet. New cases, messages, and events will appear here.” A missing customer returns the generic unavailable-record state. Completing a follow-up confirms the task update without changing the health score immediately.

## 10 Support Inbox and case detail

**Job:** respond with the right context, keep private notes private, and progress the case reliably. **Primary action:** context-dependent Send reply, Ask customer, or Resolve case.

### 10.1 Wide wireframe

Support heading with local tabs Inbox and Cases. Inbox views: Unassigned, Mine, Awaiting customer, Recently resolved. Search is scoped to cases using supported fields; it does not imply full mailbox search.

At 1440, inside the 1152 px usable width: list 280 px, gap 16 px, conversation 560 px, gap 16 px, context 280 px. The list shows reference/subject, customer, unread marker with accessible “Unread,” priority, and last update. Rows may grow to 80–104 px. The conversation header shows subject, case number, status, and a named More actions control. Public messages are on paper; internal notes have a muted band with a “Staff only” heading. No chat bubbles that imply live chat delivery.

Composer tabs are “Public reply” and “Internal note.” The public tab carries “Visible to the customer in the portal”; the note tab carries “Staff only.” Keep separate in-memory drafts when switching. Public action is “Send reply”; private action is “Add note.” A separate “Ask customer” action opens a form requiring a public question; do not hide a state transition inside Send reply.

Context contains customer link, assignee/team, priority, category, custom fields, and target status. Targets use “Response due [time],” “Resolution overdue,” or “Resolution clock paused,” with explanatory details. Priority change explains: “Priority changes the order of work. The original target stays the same.” Assignment uses eligible active members and preserves team constraints.

### 10.2 Case actions and dependent views

| Action | Surface and required information | Result |
| --- | --- | --- |
| Claim case | Named button; visible current owner/version | Server-confirmed assignment; conflict banner on a race |
| Ask customer | Desktop dialog, narrow full page; public message required | Message posted and state becomes Awaiting customer together |
| Resolve case | Desktop dialog up to 640 px; mobile full page; resolution code, public summary, required configured fields | “Resolution posted.” New resolved cycle appears; no silent close |
| Reopen case | Reason for staff, public message for portal | New active cycle; earlier resolution remains in history |
| Close case | Manager/admin confirmation with reason | Explain: “Closed cases cannot be reopened. A new related request can be created.” |
| Use knowledge | Opens Assistant route with authorized case link and explicit return path | No customer text sent automatically; draft copies only after Use draft |
| View history | Read-only route/tab | State changes and safe audit history, staff only |

Cases tab is a full operational table: reference/subject, customer, state, priority, assignee/team, target state, updated time. It shares case detail and filters with Inbox. It is not a second case model. Do not add bulk resolve, merge, attachments, email-delivery checks, or typing indicators.

### 10.3 Responsive specification

| 1440 | 1024 | 700 | 390 |
| --- | --- | --- | --- |
| 280/560/280 panes with 16 px gaps | 280 px list + 16 px gap + 680 px conversation; context through Details tab on selected case | List route, then single case route with Conversation/Details/History views; filters in modal | Same sequential routes; full-width composer; two draft-mode tabs; actions stack; no horizontally squeezed panes |

At 1024, Details replaces the conversation content temporarily rather than covering it with a persistent sidebar. At 700/390, Back to inbox restores list position. Composer stays in normal page flow when the on-screen keyboard is open; do not pin it over the last message. At wide widths a sticky composer may be used only with tested scroll padding and sufficient conversation height.

### 10.4 States and copy

No selection: “Choose a case to read the conversation.” Empty Unassigned: “No unassigned cases.” Send pending: “Posting reply…”; success: “Reply posted to the portal.” Do not say “Email sent.” Failed send preserves the exact draft. A case changed elsewhere: “This case has changed. Review the latest version before posting.” Resolved case: composer replaced by “This case is resolved” with Reopen case if permitted. Closed case: “This case is closed. Create a related case if more help is needed.”

## 11 Activity Analytics

**Job:** inspect recorded activity and service performance with understandable definitions. **Primary action:** apply report filters. Export appears only for manager/admin.

### 11.1 Wireframe and layout

Analytics title, local tabs Activity and Service, then a shared scope band: period, timezone, category/team where supported, Apply filters, Reset. State whether a filter is “Current team” or “Current category.” Show Updated time and “Today is partial” where applicable. View-specific unsupported filters are absent, not ignored.

Activity view in MVP emphasizes the supported evidence: event records reached through customer activity, plus the service trends already defined in the contract. A workspace-wide product-event chart is **not** implied by the current API. Its initial screen contains a labelled customer picker, then that customer’s event list with event-name/date filters and a link to Customer 360. An optional future aggregate event chart is not part of this handoff. This preserves the requested Activity Analytics screen without inventing an unsupported endpoint.

Service view uses one ruled measure band for current backlog/unassigned/overdue, clearly marked “Now,” followed by period metrics and category trends. Use a full-width category-volume bar chart and an aligned data table. Time trends may use one or two directly labelled series; units and observation window are visible. A definitions disclosure explains response time, active resolution time, rating sample, and seven-day reopen eligibility. Counts and rates come from the documented backend formulas.

Health distribution includes Unknown, Missing, and Stale rather than silently excluding them from presentation. No gauge, doughnut collection, 3D chart, dual axes, forecast line, or gradient fill. Moss is the main series; clay is the comparison; markers/direct labels and line patterns distinguish series without depending on color contrast between moss and clay.

### 11.2 Responsive specification

| 1440 | 1024 | 700 | 390 |
| --- | --- | --- | --- |
| Filters on one or two deliberate rows; full-width plot/table; optional 2-column definition/detail area | Wrap filters at semantic boundaries; plot stays full width | Filter disclosure; one chart at a time with data table; definitions below | Customer event records stack; category bar labels wrap; default to accessible data rows when chart text cannot remain 14 px; View chart still available if useful |

Do not horizontally shrink chart labels to fit a phone. Long category charts become vertical lists of horizontal bars with direct values. Data tables may use a named horizontal-scroll region for exact comparison, with the primary category column visible and no page-wide overflow. A chart tooltip supplements, never replaces, the accessible data table.

### 11.3 States and copy

No event customer selected: “Choose a customer to inspect recorded activity.” No events: “No events in this period.” A failed request says “Activity couldn’t be loaded,” not “No activity.” No ratings: “No ratings submitted in this period”; percentage is an em dash and sample count 0. Unanswered cases do not get a response time of zero. On refresh, keep old results with Updating; on changed filters, label old results until new scope is ready or use a scoped loading panel. Do not mix old chart values with new filter labels.

## 12 Knowledge and RAG

**Job:** maintain approved knowledge and obtain an answer tied to sources. **Local tabs:** Library and Assistant. Viewer can read approved library only; agent can ask; manager/admin can author/publish.

### 12.1 Library wireframe

Knowledge heading, tabs, search field, status filter, and “Add article” for manager/admin. Library rows show title, active revision, publication/indexing state, updated time, and named actions. Selecting an article opens its readable active text; manager/admin also sees revision history and draft controls. New article form accepts title plus pasted text or TXT/Markdown upload, with format/size guidance from the product contract. Do not offer PDF, website, or drive-connector controls.

Publishing review states “The current article stays available until the new version is ready.” Draft, Queued, Indexing, Ready, Failed, and Archived are distinct states. Retry appears for a failed eligible revision. Archive explains removal from new answers and prior source access. Showing “Published” only after the active pointer changes prevents a misleading success state.

### 12.2 Assistant wireframe

At 1440, 744 px reading column and 384 px source column. Heading “Ask your knowledge library.” Helper: “Answers use approved workspace articles. Review the sources before sending a reply.” A labelled multiline question field and “Find an answer” action come first. An optional “Returning to case [reference]” link appears when launched from Support; no private case transcript is included automatically.

Results show the original question, mode label, answer or explanation, and numbered citation links. Source rows show title, revision, heading, and excerpt. Source inspection opens an authorized reading view; on narrow screens it opens below the answer or as a dedicated source page. “Use draft” is available only with a case return context and a generated draft; it copies into that case’s unsent public composer. “Helpful / Not helpful” records answer feedback for the requester.

### 12.3 Exact assistant state model

| State | Display | Available action |
| --- | --- | --- |
| Idle | “Ask a question about your approved knowledge.” | Find an answer |
| Queued | “Waiting to search your knowledge…” | Continue other work; no fake progress percentage |
| Running | “Finding relevant sources…” then “Preparing a draft…” only if those stages are actually reported | No duplicate-submit action |
| Delayed | “Still waiting. You can leave this page and return.” after the specified delay | Return to request later |
| Generated | “Draft answer” plus citations and review reminder | Use draft in linked case; inspect sources; rate helpfulness |
| Sources only | “Source excerpts” / “A generated answer isn’t available. These articles may help.” | Read sources; no generated-draft claim |
| Abstained | “I couldn’t find enough information in the approved knowledge.” | Edit question; open Library |
| Conflicting material | “The available sources do not give a consistent answer.” only when the result supports this | Inspect sources; manager reviews articles |
| Sources changed | “A source changed after this answer was prepared. Ask again to use the current version.” | Ask again; suppress old answer/excerpts as specified |
| Failed/timeout | “We couldn’t prepare an answer. Your question is still here.” | New explicit attempt; no automatic repeated generation |

Do not show unverified confidence percentages, “verified answer” badges, typing simulations, or streaming fragments that later lose their citations. If the backend exposes only queued/running, use those coarse stages instead of inventing progress. Render complete validated results.

### 12.4 Responsive specification

| 1440 | 1024 | 700 | 390 |
| --- | --- | --- | --- |
| Answer 744 px; sources 384 px; library full table | Answer 60%, source 40% if both keep minimum reading width; otherwise sources below | Question, result, sources in one column; library as labelled rows | Same order; question textarea at least 144 px tall; full-width action; source excerpts wrap and expand in place |

Library empty: “No approved articles yet.” Manager action: Add article. Agent helper: “Ask a manager to publish an article.” Assistant loading does not prevent navigating back to Support. Private question history is not shown to other staff, even administrators, through a shared history screen.

## 13 Feedback and Follow-ups

**Job:** turn a customer concern into assigned, completed work. **Local tabs:** Tasks and Feedback. Primary action on Tasks: “Create follow-up.”

### 13.1 Wireframe and layout

Tasks filter row: My tasks / All tasks, state, due status (Any / Overdue), customer, and case when in context. Table columns: Task, Customer/case, Owner, Due, State, Actions. Due values show an absolute date/time plus “Overdue” when applicable. Text makes the distinction clear; clay tint alone is insufficient. Default sort is Due, with Created as an alternative. Do not offer a due-date-range filter until the API supports it.

Task detail includes title, description, customer, related case, assignee, due date/time/timezone, current state, and feedback link when generated from a rating. Completion requires the labelled field “What was done?” and “Complete follow-up.” No instant checklist tick that discards completion evidence. Cancellation uses an explicit action; completed task reopening is supported and recorded through the contract.

Feedback tab uses ruled rows: rating text such as “2 of 5 · Dissatisfied,” comment, customer/case, resolution cycle, submitted time, and a related follow-up link if one exists. Do not present customer comments as public testimonials. Low ratings create a task according to the existing product rule; UI confirms that task only after the server supplies it. A rating does not automatically reopen a case.

### 13.2 Responsive specification

| 1440 | 1024 | 700 | 390 |
| --- | --- | --- | --- |
| Full task table; selecting a task opens a normal detail page; feedback comments use wide ruled rows | Collapse related case under customer; wrap filter row | Task/feedback record lists; filter panel; form one column | Owner, due and state under task title; completion form full page; no unlabeled icon-only completion action |

### 13.3 States and copy

Empty My tasks: “You have no open follow-ups.” Empty All tasks: “No follow-ups yet. Create one from a customer or case.” Empty feedback: “No resolution ratings have been submitted.” Completion success: “Follow-up completed.” Missing completion note: “Describe what was done before completing this follow-up.” Failed completion preserves the note and state. Viewer can inspect permitted records but cannot create or complete tasks.

## 14 Settings

**Job:** configure the workspace without silently changing existing work. **Primary action:** depends on section, labelled Save changes or Publish configuration.

### 14.1 Sections and wireframe

At 1440, within the app content use a 208 px settings list, 24 px gap, and an up-to-800 px form/record region. Sections: Workspace, Members, Teams, Case configuration, Event tracking, Health rules, AI availability. Audit and job failure views are manager/admin operational subsections. Viewer/agent see only permitted information; a hidden nav link is not the permission boundary.

| Section | Required surface and copy |
| --- | --- |
| Workspace | Name, timezone, fallback feedback manager. Explain that timezone changes display/report boundaries, not stored UTC timestamps. |
| Members | Member list with role and active/pending status; Add member; Create setup link; role/access changes. Explain last-admin and replacement-owner constraints before submission. |
| Teams | Team name and members. Warn about active case assignment constraints using visible affected-record links. |
| Case configuration | Draft/current version identity, categories/routing, priority targets, typed fields, state labels, preview of portal-visible creation form. Publish review: “New cases use this version. Existing cases keep their current configuration.” |
| Event tracking | Event definitions, allowed properties, activity meaning, credentials. Secret reveal is a one-time surface with Copy key and explicit “You won’t be able to view this key again.” No keys in screenshots or ordinary list rows. |
| Health rules | Enabled components, weights, fixed formula explanations, missing-data conditions and future-snapshot impact. Do not offer arbitrary formula scripting. |
| AI availability | Generation available/disabled; source search/indexing states; readable explanation. Show model/version diagnostics only under Details, where operationally useful. No fake Connect provider buttons. |
| Audit/jobs | Safe change history and queued/running/failed work; retry only for eligible failures. No raw prompt, token, or payload display. |

Form labels stay above fields. Required fields are stated in text; optional ones use “Optional” where ambiguity exists. Save action appears at the end of a section; avoid a global sticky save bar that could obscure fields. Multi-step publishing review is inline or a full page rather than nested dialogs.

### 14.2 Responsive specification

| 1440 | 1024 | 700 | 390 |
| --- | --- | --- | --- |
| 208 px settings navigation + main form; two-column fields only for genuinely related short inputs | Settings navigation 184 px and main form; most fields one column | Settings index page → section page with Back to settings; no narrow nested sidebar | Same sequential pattern; controls at least 44 px; token reveal in wrapping monospaced region with explicit Copy control |

### 14.3 States and copy

No changes: Save is disabled with no unnecessary status message. Unsaved changes: text “Unsaved changes” beside section heading; leaving opens Keep editing / Discard changes. Publishing pending: “Publishing configuration…”; success: “Configuration published for new cases.” Indexing is not configuration publication and uses its own state. Member deactivation conflicts list the records requiring reassignment. Unauthorized settings sections have neither visible controls nor fetched secrets.

One-time secrets and setup URLs never enter screenshots, analytics, URLs, persistent frontend caches, or toast text. Copy success says “Copied” without echoing the secret. Setup-link creation says “Setup link created,” never “Invitation emailed.”

## 15 Public Demo Portal

**Job:** let a provisioned customer contact request help and follow their own requests. “Public” describes its customer-facing purpose; it does not remove authentication or create open registration. Staff and portal accounts have distinct sign-in labels.

### 15.1 Portal screen family

| View | Wireframe and behavior |
| --- | --- |
| Sign-in | Product/workspace name, “Customer portal,” email/password, Show password, Sign in. Explain provisioned access. No social sign-in or reset-email promise unless actually implemented. |
| Requests | Header with Requests, New request, account menu. H1 “Your requests.” Filter by state/search. Rows show subject/reference, public state, and submitted time; no internal owner, target, health, or company-wide counts. Do not expose a generic last-updated timestamp that might reveal private-note activity. |
| New request | H1 “How can we help?” Category, subject, description, then portal-editable fields from current configuration. Primary “Submit request.” Helper: “Describe the issue and what you expected to happen.” No attachments in MVP. |
| Request detail | Back to your requests, reference/subject/status, public message timeline, reply form or state-appropriate action, public configured values under Details. |
| Resolution feedback | “Did this resolve your request?” followed by five radio labels from Very dissatisfied to Very satisfied, optional comment, Submit feedback. Available only for the latest eligible resolved cycle. |
| Reopen | “What still needs attention?” public message and Reopen request. Explain that the support team will see the message. |
| Profile/account | Current contact identity and sign-out; account changes limited to supported authentication capabilities. No editing of arbitrary CRM customer fields. |

### 15.2 Layout and responsive specification

Wide portal content is capped at 960 px and centered. Request detail/form reading is capped at 760 px. Header is 72 px wide-screen and 56–60 px narrow. No staff sidebar. Paper work surface with a modest irregular outer corner provides identity; all form fields align to a straight vertical edge.

| 1440 | 1024 | 700 | 390 |
| --- | --- | --- | --- |
| Centered 960 px requests; 760 px detail/form; header links visible | Centered content within 32 px gutters; same simple nav | 20 px gutters; request rows become labelled summaries; form one column | 16 px gutters; 358 px content; New request and account remain named; form inputs 16 px and primary submit full width |

Portal state explanations: New — “Your request has been received”; Open — “The team is working on your request”; Awaiting customer — “The team needs more information from you”; Resolved — “The team has provided a resolution”; Closed — “This request is closed.” Configured state labels may appear, but the underlying explanation must retain the correct meaning.

### 15.3 States, privacy, and demo honesty

Submission success shows the real reference and a link to the created request: “Request submitted.” Do not promise an email receipt or response deadline not configured for customer display. Empty requests: “You haven’t submitted a request yet.” Missing request: “This request isn’t available.” No hint identifies another customer’s request.

Sending a public reply displays “Posting reply…” and preserves the message on failure. For a resolved request show Reopen request and eligible feedback; do not leave an active ordinary reply composer. For closed requests show “Create a related request”; feedback creation and replies are unavailable. Historical feedback remains readable.

Synthetic demos display a quiet persistent banner: “Demo workspace. Use fictional information.” The banner must not imply a sandbox is automatically isolated per visitor if the deployment uses provisioned access. The landing page’s demo CTA leads to this sign-in only when the deployment supports it. No shared public administrator credentials.

## 16 Cross-screen flow and copy contract

| Flow | Start → destination | Preserved context and focus |
| --- | --- | --- |
| Find a customer | Customers → Customer 360 | List filters/cursor stored; focus detail H1; Back restores invoking name link |
| Triage request | Overview attention row → Support case | Filter reason shown; focus case title, not composer automatically |
| Use knowledge | Case → Assistant → case composer | Authorized case reference only; separate unsent drafts preserved; after Use draft focus composer and announce “Draft added. Review before sending.” |
| Inspect source | Assistant citation → source reading | Source title/revision/heading visible; Back returns to citation; expired source suppresses text |
| Complete follow-up | Feedback/customer/case → task detail | Related record link and completion note retained through validation; Back restores entry |
| Publish configuration | Settings draft → review → published | Diff summary and impact statement; success updates current version visibly |
| Portal support | New request → detail → resolved → feedback/reopen | One request identity; no implicit access to other contacts’ cases |

Write button labels as specific verbs: Add customer, Create case, Send reply, Add note, Ask customer, Resolve case, Create follow-up, Publish article, Find an answer. Avoid “Proceed,” “Submit” without context, “Unlock insights,” “Supercharge,” “AI magic,” and “Everything you need.” Keep errors in plain language with a useful action; implementation diagnostics belong behind Details and must be safe.

Use sentence case. Use “customer” for the CRM entity, “contact” for the person linked to it, “case” for staff operations, and “request” in the portal. Explain the mapping in developer documentation, not in customer-facing copy. Use “Updated” for refresh time and “Calculated” for a health snapshot. Never use “live” for periodically refreshed or daily-calculated information.

Display dates unambiguously, such as “8 Nov 2026, 14:30 IST,” using the workspace timezone. Relative labels may supplement but not replace an accessible absolute value. Do not hard-code IST for non-Indian workspaces. Durations include units. A missing value is “Not recorded,” “Unknown,” or “Unavailable,” chosen by cause; 0 is reserved for an actual measured zero.

## 17 Accessibility specification

### 17.1 Required behavior

Target WCAG 2.2 AA. These are design and implementation acceptance requirements, not a claim that the unbuilt product is certified or tested. The project deliberately uses 40–48 px targets, exceeding the general 24 CSS px minimum where applicable; spacing exceptions are not a shortcut for dense controls. [A4]

- All main tasks work by keyboard with visible focus. No drag-only reordering, hover-only controls, or gesture-only action.
- Every input has a persistent associated label. Required, invalid, and helper information is programmatically associated. Validation summary links to fields; focus moves to summary after failed submission, then the user can choose the field.
- Success/loading updates use a polite live region; important form errors use an assertive announcement when necessary. Do not announce clocks, every poll, or each typed search character.
- Focused controls and their rings remain entirely visible as a project requirement, including under sticky bars. WCAG’s AA minimum is not entirely obscured; this design intentionally sets a stronger visibility target. [A5]
- At 200% text zoom and narrow equivalent widths, navigation/forms reflow. Also test the 320 CSS px reflow requirement at suitable zoom; the requested 390 px screenshot alone does not demonstrate it. Only inherently two-dimensional tables/charts may use an isolated scroll region with an equivalent readable view. [A6]
- At 400% browser zoom on a 1280 px viewport, essential reading and controls remain usable without page-wide two-direction scrolling. Review text-spacing overrides: 1.5 line-height, 2× paragraph spacing, 0.12em letter spacing, and 0.16em word spacing without clipping. [A6, A7]
- Password fields allow paste and password managers. Show password is labelled and stateful. No cognitive puzzle or memory test is added to authentication. Expired-session handling explains the next action without blaming the user.
- State is conveyed through words and, when helpful, a distinct symbol; color is supplementary. Charts have accessible tables; ratings have labelled radios; unread state has text for assistive technology.
- Informative images have meaningful alt text. Decorative forms/grain have empty alternative text or are hidden from assistive technology. Do not repeat adjacent captions in alt text.
- Forced-colors/high-contrast mode retains input borders, selected state, focus, and buttons through system-color behavior; decorative fills may disappear safely. Do not rely solely on background images.
- Touch and pointer users can complete the same flows. Hover content must also appear on focus and be dismissible; necessary help remains visible without a tooltip.
- Destructive or consequential actions require a clear explanation and confirmation where appropriate. There is no automatic submission when a select value changes in a form awaiting Save.

### 17.2 Manual verification tasks

Test with keyboard alone, NVDA with a supported desktop browser, VoiceOver with Safari where available, touch on a narrow viewport/device, reduced-motion preference, and forced-colors/high-contrast mode. Confirm every state, not just the default screenshot. Use automated checks to assist; do not treat a clean automated scan as full accessibility proof.

Complete: find and open a customer; submit a portal request; claim it; add a private note; post a public reply; inspect a source; resolve; submit feedback; complete a task; recover from validation; recover from a version conflict; navigate a modal; and sign out. Record actual results later. No user testing has been conducted for this specification.

## 18 Visual and interaction acceptance checklist

Use these checks in design review and later browser verification. A check is pending until evidence exists; this planning deliverable does not mark future implementation checks as passed.

| ID | Acceptance check | Evidence required |
| --- | --- | --- |
| V01 | All nine colors exactly match the authoritative tokens | Token audit and rendered sampled fills |
| V02 | Source Serif 4 and Instrument Sans use correct bindings/weights, with readable fallback | Font inspection plus blocked-font test |
| V03 | Appendix A remains unchanged and governs visual decisions | Exact source comparison |
| V04 | Landing hero is asymmetrical and editorial, with upright readable text | 1440/1024 review |
| V05 | Clay/moss groups remain continuous at narrow widths | 700/390 review |
| V06 | Staff screens use ruled work surfaces rather than generic KPI-card grids | Overview/inbox/analytics review |
| V07 | No purple gradients, glass, glow, excessive shadows, or gratuitous motion | All-screen visual review |
| V08 | Terracotta does not carry normal-size text or labels | Component/color audit |
| V09 | Text, necessary boundaries, and focus satisfy tested contrast rules in all states | Unrounded contrast calculations and rendered state checks |
| V10 | No page-level horizontal overflow at all four requested widths | 1440, 1024, 700, 390 px screenshots and scroll-width check |
| V11 | 320 CSS px reflow and 200%/400% zoom remain usable | Additional browser tests |
| V12 | Focus is visible, ordered, and not covered; drawer/dialog returns focus correctly | Recorded keyboard walkthrough |
| V13 | Target sizes and spacing remain usable in compact rows and mobile forms | Box measurement and touch review |
| V14 | Reduced motion removes transitions/press transforms; no essential motion | Preference-on test |
| V15 | Public reply and internal note remain unmistakable in every viewport/state | Composer state matrix and portal privacy test |
| V16 | Inbox collapses to sequential routes at 700/390 | Back-navigation and focus restoration test |
| V17 | Loading/empty/no-match/error/success/conflict states are designed for every screen | State screenshots with readable copy |
| V18 | Forms preserve values on failures and identify required/invalid fields | Submit/retry test with assistive technology |
| V19 | Health shows missing evidence, coverage, as-of and stale states correctly | Known fixture snapshots and UI comparison |
| V20 | Analytics shows real values, denominators, units, periods, partial/current labels | Backend fixture comparisons and accessible data tables |
| V21 | Assistant distinguishes draft, sources-only, abstained, failed, and sources-changed | Mode fixtures and source-revocation test |
| V22 | Use draft never sends a reply or exposes staff-only source links in public content automatically | End-to-end case flow |
| V23 | Portal excludes all internal context and another contact’s requests | Role/ownership tests plus response inspection |
| V24 | No fabricated results, testimonials, screenshots, or integrations | Content audit against implemented scope |
| V25 | UI contains only working actions; unavailable capabilities have honest copy | Link/action inventory |
| V26 | Long names, long words, multiline labels, and localization-friendly dates do not clip | Stress-content screenshots |
| V27 | Secrets/setup links are absent from screenshots, logs, and persistent caches | Security review of administrative states |
| V28 | Final review distinguishes static design validation from working-app validation | Release evidence record |

## 19 Design handoff and verification record

Deliverables: this written specification and the static wireframe atlas. The atlas is a visual reference; component semantics, responsive dimensions, and state behavior are normative in the written rules. Where a small-scale wireframe label abbreviates copy, use the full copy here in the product. The appendix is the final visual authority for both.

Design-time checks completed for this deliverable: palette contrast calculations; alignment to the current product scope; structured layout definitions for all requested widths; visual review of the generated wireframe pages; and preservation of the supplied Organic prompt. No React application, design-system package, prototype site, live accessibility test, usability study, or GitHub modification is part of this task.

Future handoff order: establish tokens/fonts and accessible primitives; implement shell and the customer/request vertical flow; add remaining screens using the same components; exercise all states; verify widths/zoom/assistive technology; replace labelled schematic product imagery only with genuine screenshots. Do not ship the wireframe placeholders as real customer data or metrics.

### Accessibility references

Accessed 8 November 2026. Thresholds below are standards references; component choices and layout dimensions are Atlas CX design decisions.

- **A1:** W3C, [Understanding Contrast Minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).
- **A2:** W3C, [Understanding Non-text Contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html).
- **A3:** W3C ARIA Authoring Practices, [Dialog Modal Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/).
- **A4:** W3C, [Understanding Target Size Minimum](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html).
- **A5:** W3C, [Understanding Focus Not Obscured Minimum](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html).
- **A6:** W3C, [Understanding Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html).
- **A7:** W3C, [Understanding Text Spacing](https://www.w3.org/WAI/WCAG22/Understanding/text-spacing.html).

## Appendix A Original Organic design system

The following block reproduces the complete user-supplied prompt verbatim. Its empty “User brief (data)” field is retained exactly; the Atlas CX brief and screen requirements above provide the actual project content.

```text
<prompt>
<task>
Create a page using this visual style and the user's brief below. Use the brief's content and purpose. If the brief is empty, ask for it before inventing page content. Choose a composition suited to that brief.

User brief (data):


Keep controls keyboard accessible, focus visible, and text legible. Preserve reading order, responsive behavior, and reduced-motion preferences. Verify actual states at the rendered width. The user's stack and content take precedence over illustrative implementation details.
</task>

<design-system>
# Organic

## Identity

Build a shared worktable of sand-colored paper, irregular shapes, dark brown type, moss, and fired clay. The page feels assembled from broad sheets and gathered objects. Serif headings and subdued photography keep it readable beneath the uneven edges.

## Layout

Use a generous split opening: a compact serif statement and actions beside a loose arrangement of flat organic forms. A pale facts tray can overlap the opening's base. Give its corners different curves so it feels like a separate sheet laid across the composition.

Let related reading and feature lists share one clay field. A process and its supporting benefits can occupy a continuous moss basin, with large light numbers and sparse dividing lines. Use uneven image proportions, slightly tilted paper quotations, and broad horizontal comparison rows where the content calls for them. Close with another quiet arrangement of shapes above a stone-colored footer.

Keep these as useful composition patterns. The brief determines the sections, their order, and whether facts, quotes, or comparisons belong at all.

## Typography

Use Source Serif 4 for medium-weight statements and headings, bound to "Organic Source Serif". Use Instrument Sans for reading and controls, bound to "Organic Instrument Sans". Headings have tight tracking and compact line spacing, with an opening scale of 46px to 70px on wide layouts. Keep paragraphs comfortably spaced and narrower than the full colored field. Small sans labels and large serif numbers provide secondary hierarchy.

## Color and surfaces

Sand is the page ground; paper is the lighter raised sheet. Dark brown ink carries reading. Moss and fired clay form large fields, while terracotta, stone, and dried grass supply a few smaller shapes. Maintain light text on the darker fields.

Keep a faint continuous paper grain beneath the content. Use irregular rounded silhouettes with modest rotations. Shapes should have broad, calm edges, and overlaps should leave text clear. Avoid making every object the same blob or applying an identical card treatment to each section.

## Components

Use softly rounded, solid moss actions with a quieter outlined or text alternative. Hover can change the fill; press can compress slightly. Keep visible focus outside the control edge.

Features sit in open lists with small drawn symbols. Numbered steps use large figures and simple separators. Optional comparison rows divide identity, details, and action across a shared width. A featured row can stay moss while selection adds a distinct inset outline. Disclosures use clear ruled rows and visible open states.

## Images

Choose photographs of real materials, objects, or places. Apply a mild sepia cast and reduce saturation so they sit with the earth palette. Scene images can fill irregular crops; isolated objects need enough space to retain their silhouette. Slight image rotation is useful when the surrounding reading remains upright. Supply meaningful alternative text and keep decorative forms hidden from assistive technology.

## Motion

Use the brief interaction timing for color changes and a small pressed scale. Keep the page arrangement and organic forms still. Respect reduced motion by removing transitions and transforms from interactive feedback.

## Responsive behavior

At 1000px, tighten the major splits and spacing. At 700px, stack the opening, reading sections, images, steps, quotes, and comparison contents. Facts can remain in two columns. Remove quotation rotations to give small-screen reading a straight edge, while restrained image tilts can remain. Preserve the clay and moss groups as continuous fields, and keep footer links in two columns.

## Design limits

Avoid glossy gradients, glass, bright synthetic greens, excessive leaves, and deep floating shadows. Uneven edges must not compromise alignment or hit areas. Use the customer's real subject and claims; earth colors do not imply environmental credentials.

## Authoritative tokens

| CSS variable | Value |
| --- | --- |
| --dp-color-ground | #eee6d6 |
| --dp-color-surface | #f5eddf |
| --dp-color-ink | #29251d |
| --dp-color-primary | #35422d |
| --dp-color-field | #694737 |
| --dp-color-art-accent | #ad7d62 |
| --dp-color-surface-muted | #ddd5c3 |
| --dp-color-highlight | #b9b28b |
| --dp-color-ink-muted | #443b2f |
| --dp-typography-display | "Organic Source Serif", Georgia, serif |
| --dp-typography-reading | "Organic Instrument Sans", sans-serif |
| --dp-typography-body | 16px |
| --dp-typography-reading-small | 15px |
| --dp-typography-control | 14px |
| --dp-typography-caption | 13px |
| --dp-typography-metadata | 12px |
| --dp-typography-reading-leading | 1.8 |
| --dp-spacing-content-gap | 24px |
| --dp-radius-control | 27px 19px 29px 16px / 22px 26px 19px 29px |
| --dp-border-hairline | 1px |
| --dp-motion-interaction | 240ms ease |
</design-system>
</prompt>
```



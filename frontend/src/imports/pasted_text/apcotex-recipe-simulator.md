Design a multi-screen enterprise SaaS web application called "Apcotex R&D Recipe 
Simulator" — an internal tool that helps chemical R&D scientists cut new product 
development from ~3 months and 40–50 lab trials down to a handful of targeted 
experiments, using AI recommendations built on historical experiment data.

=== BRAND THEME (Apcotex) ===
Brand mood: clean industrial, corporate, premium, trustworthy, modern. Strong 
structure, generous white space, minimal layout, professional chemistry/ 
manufacturing feel.

Color palette (use strictly):
- Deep Blue #1F5FA8 — primary brand, headings, active nav, outline buttons
- Teal/Aqua #1FB7B5 — primary CTAs, key interactive elements, progress indicators
- Brand Red #D93A2F — ACCENT ONLY: alerts, critical CTAs, winner highlights, 
  important badges (use sparingly, never as a fill for large areas)
- Dark Text #1F2937 — body copy
- Background #F7FAFC — app background
- Border Gray #E5E7EB — card borders, dividers, table grid lines

Usage rules (non-negotiable):
- Blue + teal carry the majority of the UI
- Red appears only for highlights, alerts, and the single most important CTA on 
  a screen
- Backgrounds stay white or light gray (#F7FAFC); no colored fills behind cards
- Deep blue for headings, dark gray for body text
- Hero banners and top page sections use a blue-to-teal linear gradient 
  (135°, #1F5FA8 → #1FB7B5)
- Hover = slightly darker shade of the same color (do not switch hue on hover)

Component direction:
- Navbar: white background, dark text, deep-blue active state with a 2px teal 
  underline on the active item
- Primary button: solid teal #1FB7B5, white text
- Secondary button: white fill, deep-blue border and text (outline style)
- Destructive / critical button: solid red #D93A2F, white text (used rarely — 
  e.g., "Reject Recipe", "Abort Run")
- Cards: white background, 1px #E5E7EB border, soft shadow 0 1px 3px 
  rgba(31,95,168,0.06), 8px radius
- Footer: deep blue #1F5FA8 with white text
- Data tables: white rows, #F7FAFC header row, thin #E5E7EB grid, deep-blue 
  column headers
- Chips/badges: light tinted backgrounds of blue or teal at ~10% opacity with 
  solid-color text; red chip only for "Winner" / "Critical"

Typography: Inter (or similar neutral sans). Headings in deep blue #1F5FA8, body 
in #1F2937. Tabular numerals for all data cells. No emojis, no gradients outside 
hero sections, no playful illustrations — this is lab software, not consumer SaaS.

Use realistic placeholder data throughout: tensile strength in MPa, temps in °C, 
pH 6.5–8.5, viscosity in cP, etc. No lorem ipsum.

=== GLOBAL LAYOUT ===
Left sidebar nav (collapsed icons + labels): Dashboard, Literature Review, Recipe 
Simulator, Experiments, Products, Settings. Active item: deep-blue text with 
teal left border accent.
Top bar: Apcotex logo (left), global search (center), notifications bell, user 
avatar (right). White background, thin bottom border.

=== SCREEN 1: DASHBOARD ===
- Hero strip at top with blue-to-teal gradient background, white heading text: 
  "Welcome back — accelerate your next formulation"
- 3 metric tiles (white cards): "Trials Saved This Quarter: 127", "Avg Time to 
  Recipe: 18 days (↓ from 90)", "Model Accuracy: 84%". Numbers in deep blue, 
  delta indicators in teal (positive).
- 2 large action cards side-by-side: "New Literature Review" and "New Recipe 
  Prediction", each with icon (outline style, deep blue), one-line description, 
  and teal Start CTA
- Recent Projects table: Project Name | Type | Status (tinted chip) | Owner | 
  Last Updated

=== SCREEN 2: LITERATURE REVIEW (Part 1) ===
- Input card: "Compound / Product Name" text field with deep-blue focus ring
- "Research Sources" multi-select chips pre-filled: Google Scholar, PubMed, 
  Patents.google, ChemSpider, ScienceDirect, Rubber World, SpecialChem
- "Start AI Research" teal primary button
- Progress state: animated teal checkmarks per source ("Scanning Google Scholar… 
  24 papers found")
- Results: AI summary card at top with a subtle teal left border ("Key findings 
  across 47 papers…") + expandable table: Source | Title | Key Insight | 
  Relevance Score (teal progress bar) | Link
- CTAs: "Export Report (PDF)" (outline blue) and "Use Findings in Recipe 
  Simulator" (teal primary)

=== SCREEN 3: RECIPE SIMULATOR — STEP 1 of 4: Upload Competition Data ===
- Top stepper (deep-blue active step, teal completed steps, gray upcoming): 
  (1) Upload Competitor Data → (2) Define Target Spec → (3) AI Recommendations → 
  (4) Compare with Trials
- Drag-and-drop zone with dashed deep-blue border: "Drop competitor datasheets 
  (.xlsx, .pdf, .csv)"
- Uploaded files list with parse status chips (Parsing… teal / Parsed ✓ teal / 
  Failed red)
- Auto-detected competitors as removable blue-tinted chips: BASF, Synthomer, 
  Trinseo, Zeon, JSR
- "Continue" teal button, disabled gray until ≥1 file parsed

=== SCREEN 4: RECIPE SIMULATOR — STEP 2 of 4: Define Target Specification ===
*** Hero screen — highest design fidelity ***
- Excel-like spreadsheet component, full-width, thin #E5E7EB grid
- Columns: Product Feature | BASF | Comp 2 | Comp 3 | Apcotex Product A (nearest) 
  | Apcotex Product B (nearest) | **Desired Product Feature** (this column gets 
  a subtle teal tint #1FB7B5 at 8% opacity plus a 2px teal left border to signal 
  "this is where you type")
- Rows (10): Tensile Strength (MPa), Elongation at Break (%), Temp Max (°C), 
  Viscosity (cP), pH, Solid Content (%), Particle Size (nm), Tg (°C), Bond 
  Strength (N/mm), Shelf Life (months)
- Competitor + internal columns: read-only, light gray fill, pre-populated with 
  plausible numbers
- Desired column: editable cells with placeholder unit hints and min–max ranges 
  in light gray
- Right side panel: "Importance Weighting" — one teal slider per property (0–100) 
  so the scientist can tell the model "tensile strength matters 2x more than 
  viscosity"
- Bottom-right: "Run AI Prediction" teal primary CTA with a small sparkle icon

=== SCREEN 5: RECIPE SIMULATOR — STEP 3 of 4: AI Recommendations ===
- Hero strip with blue-to-teal gradient: "3 Recommended Recipes Ready to Trial" 
  + overall model confidence % in large white numerals
- Three ranked recipe cards side-by-side (#1, #2, #3). The #1 card has a thin 
  red top border and a red "Top Pick" badge (only use of red on this screen). 
  Each card shows:
  • Auto-generated recipe name (e.g., "ZEN-02-New", "APX-TG-441", 
    "BR-HighTemp-07")
  • Match score badge in teal (e.g., 94%, 89%, 82%)
  • Mini bar chart: Predicted (teal) vs Desired (deep blue) for top 4 properties
  • Key ingredients preview (pH, Water Qty, Temp, Monomer A/B, Surfactant, 
    Initiator)
  • Collapsible "Why this recipe?" — SHAP-style horizontal bar attribution in 
    teal/blue showing which ingredient drives which property
  • "Send to Lab" teal button
- Below cards: ranked table of all candidate recipes PR#1–PR#38, sortable: 
  Rank | Recipe ID | Match Score (teal progress bar) | Key Differentiator | 
  Actions
- Right sidebar: "Prediction Insights" — feature importance horizontal bar chart 
  (deep blue bars) + confidence distribution histogram (teal)

=== SCREEN 6: RECIPE SIMULATOR — STEP 4 of 4: Compare with Lab Trials ===
- Layout mirrors the user's existing validation sheet but polished
- Frozen left columns with teal-tinted header: Recco 1–5 (the AI's original 
  recommendations)
- Scrollable right columns with gray header: Lab Exp #6 through Lab Exp #33+ 
  (actual trials run)
- Rows: Exp F #1 through Exp F #10 (measured properties)
- Winner highlight: the winning lab experiment column gets a red "Winner" pill 
  above it and a thin red top border — this is the primary use of red on the 
  screen
- Partial match: amber-style highlight rendered instead as a teal dashed border 
  (keep to brand palette)
- Bottom strip metric card: "Top 3 AI recommendations included 2 of 3 lab 
  winners — Model Accuracy: 87%" with the 87% in deep blue
- CTA: "Feed Results Back to Model" teal primary (continuous learning loop)

=== SCREEN 7: RECIPE DETAIL (Modal or Full Page) ===
- Header: Recipe name in deep blue + teal score badge + "Approve for Trial" 
  (teal) / "Reject" (red outline) buttons
- Tabs with deep-blue active underline: Composition | Predicted Properties | 
  Process Parameters | History
- Composition tab: full ingredient table with pH, Water Qty, Temp columns plus 
  Yes/No/X toggle cells for ~8 additional ingredients (matches the user's 
  existing PR sheet), rows PR#1–PR#38. Yes = teal chip, No = gray chip, 
  X = blue chip.
- Predicted Properties tab: radar/spider chart overlaying This Recipe (teal), 
  Desired Target (deep blue dashed), Nearest Competitor (gray)
- History tab: vertical timeline with teal dots marking model iterations

=== REQUIRED STATES ===
Include for each screen: loading skeletons (shimmer on #F7FAFC), empty states 
with simple outline icons in deep blue, error toasts (red), success toasts 
(teal), hover states on all interactive cells (2-shade-darker same hue).

=== AUDIENCE NOTE ===
This mockup is for chemical R&D leadership at Apcotex, a specialty polymers 
company. It must feel like a serious scientific instrument — consistent with 
the Apcotex corporate brand (clean industrial, premium, trustworthy). No 
emojis, no decorative gradients outside the specified hero strips, no marketing 
fluff. Think "lab software" not "consumer SaaS."
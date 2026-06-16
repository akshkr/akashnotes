export const meta = {
  name: 'curriculum-analysis',
  description: 'Analyze the COURSE TABLE OF CONTENTS (curriculum shape) — coverage, phase balance, ordering, redundancy, capstone coherence, currency — then a constraint gate + ranked report with a no-renumber swap-map',
  whenToUse: 'To improve the curriculum at the structural level (index.md + lesson headers), not line-by-line lesson content. Protects the two invariants and the no-renumber / repurpose-in-place rule.',
  phases: [
    { title: 'Analyze', detail: '6 curriculum lenses read index.md + lesson headers in parallel' },
    { title: 'Constrain', detail: 'gatekeeper rules each proposed change against invariants + no-renumber' },
    { title: 'Synthesize', detail: 'ranked curriculum report + concrete swap-map (returned as text)' },
  ],
}

// ---------------------------------------------------------------------------
// Shared framing: the project intent + the constraints every change must respect.
// ---------------------------------------------------------------------------
const INTENT = `
PROJECT: a 100-day course that converts EXPERIENCED SOFTWARE ENGINEERS into AI
engineers who BUILD PRODUCTION LLM APPS — explicitly NOT ML researchers. The core
device is translating each AI concept into something a SWE already knows.

TWO INVARIANTS (load-bearing — every proposed change must respect them):
  1. Keep it a SIMPLE, job-focused course (SWE-translated, copy-runnable code).
  2. The reader has LITTLE/NO ML background (no unexplained jargon/theory).

HARD STRUCTURAL CONSTRAINT (CLAUDE.md §7): the 100-day numbering is load-bearing.
Do NOT propose renumbering or merging days. To add a topic, REPURPOSE a thin or
redundant day IN PLACE (keep its number; update only that day + neighbours' footers
+ index.md). Renumbering cascades across all files and is rejected by default.

Authoritative map + facts: index.md (TOC), REFERENCE.md (models/pricing/day map),
GLOSSARY.md (terms + SWE analogies), CLAUDE.md (rules), IMPROVEMENT_PLAN.md (open
gaps + an existing swap-map). Read these as needed — they are the source of truth.
`

// ---------------------------------------------------------------------------
// SCHEMAS
// ---------------------------------------------------------------------------
const OBS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['lens', 'summary', 'observations'],
  properties: {
    lens: { type: 'string' },
    summary: { type: 'string', description: '2-3 sentence headline for this lens' },
    observations: {
      type: 'array',
      maxItems: 12,
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['focus', 'days', 'severity', 'observation', 'proposedChange', 'invariantRisk', 'blastRadius'],
        properties: {
          focus: { type: 'string', description: 'short label, e.g. "phase balance" or "gap: agent memory"' },
          days: { type: 'string', description: 'day(s)/phase(s) involved, e.g. "P6 / Days 74-82" or "D30,D32 vs D35"' },
          severity: { type: 'string', enum: ['low', 'medium', 'high'] },
          observation: { type: 'string', description: 'what is structurally off, concretely' },
          proposedChange: { type: 'string', description: 'the curriculum change; prefer repurpose-in-place, no renumber' },
          invariantRisk: { type: 'string', description: 'does the change risk invariant 1 or 2? "none" if not' },
          blastRadius: { type: 'string', enum: ['in-place', 'neighbours', 'cross-phase', 'renumber'], description: 'how far the change reaches' },
        },
      },
    },
  },
}

const GATE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['rulings'],
  properties: {
    rulings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['id', 'verdict', 'reason'],
        properties: {
          id: { type: 'string', description: 'the observation id being ruled on' },
          verdict: { type: 'string', enum: ['keep', 'revise', 'drop'] },
          reason: { type: 'string' },
          saferChange: { type: 'string', description: 'if revise: a version that respects invariants + no-renumber' },
        },
      },
    },
  },
}

// ---------------------------------------------------------------------------
// PHASE 1 — six curriculum lenses (read-only, parallel).
// ---------------------------------------------------------------------------
phase('Analyze')
const LENSES = [
  {
    key: 'coverage-gap',
    prompt:
      `Read index.md (the TOC). Compare the topic coverage against what an AI engineer ` +
      `BUILDING PRODUCTION LLM APPS needs on the job today. Flag MISSING topics (e.g. agent ` +
      `memory, context engineering, retrieval evaluation, structured-output reliability, ` +
      `reranking depth, PII/privacy, eval-set construction) and OVER-covered topics relative ` +
      `to job relevance. Cross-check IMPROVEMENT_PLAN.md's existing gap list. For each gap, ` +
      `propose which existing thin/redundant day could be repurposed to cover it (no renumber).`,
  },
  {
    key: 'phase-balance',
    prompt:
      `Compute days-per-phase (run: for d in Phase_*/; do echo "$(find "$d" -name '*.md'|wc -l) $d"; done). ` +
      `Weigh each phase's day-count against its importance to the job-focused intent. Flag ` +
      `imbalances — e.g. a thin phase on a central topic, or a heavy phase on a less ` +
      `job-relevant / ML-research-flavored topic. Propose rebalancing via in-place repurposing, ` +
      `not renumbering.`,
  },
  {
    key: 'dependency-order',
    prompt:
      `From index.md + GLOSSARY.md, build a rough concept-dependency view of the 100 days. ` +
      `Flag ORDERING problems: a concept/skill used before the day that teaches it (forward ` +
      `references), setup taught after code that needs it, or difficulty cliffs between adjacent ` +
      `days. Propose minimal in-place fixes (pointers, a setup callout, reordering within a phase).`,
  },
  {
    key: 'redundancy',
    prompt:
      `Identify day-level REDUNDANCY: topics split across two days as padding (look for "_part" ` +
      `folders and "Part 1/Part 2"), and near-duplicate days. Run: ls -d Phase_*/Day_*_part* ; ` +
      `grep -rl "Part 1\\|Part 2" Phase_*/*/*.md . Cross-check the known clusters in ` +
      `IMPROVEMENT_PLAN.md (066/067, 069-071, 090/092, 044-046, 051-055). For each, propose ` +
      `collapsing/merging-in-place to free a slot for a gap topic — keep the day NUMBER.`,
  },
  {
    key: 'capstone-coherence',
    prompt:
      `The 5 portfolio capstones are Days 18, 34, 48, 73, 97. Read each capstone's index.md ` +
      `entry (and skim the files if needed). Assess: does each phase's content visibly BUILD ` +
      `toward its capstone, and do the 5 capstones form one coherent portfolio narrative (per ` +
      `the "Portfolio thread N of 5" framing)? Flag phases whose days don't feed their capstone, ` +
      `or capstones that don't connect.`,
  },
  {
    key: 'currency',
    prompt:
      `Assess whether the TOPIC SET is current for AI engineering as of 2026. Use web search to ` +
      `sanity-check (e.g. current agent patterns, MCP, memory, structured outputs, eval tooling). ` +
      `Flag topics that are dated/missing vs current practice. IMPORTANT: attach an "as of 2026, ` +
      `verify" caveat to any fast-moving claim; do NOT propose chasing hype that breaks the ` +
      `simple/no-ML-background invariants.`,
  },
]

const lensResults = await parallel(
  LENSES.map((lens) => () =>
    agent(`${INTENT}\n\nYou are the ${lens.key} curriculum lens.\n${lens.prompt}`, {
      phase: 'Analyze',
      label: `lens:${lens.key}`,
      agentType: 'Explore',
      schema: OBS_SCHEMA,
    }),
  ),
)

const observations = lensResults
  .filter(Boolean)
  .flatMap((r) => (r.observations || []).map((o) => ({ ...o, lens: r.lens })))
  .map((o, i) => ({ ...o, id: `obs-${i}` }))
const lensSummaries = lensResults.filter(Boolean).map((r) => ({ lens: r.lens, summary: r.summary }))
log(`Collected ${observations.length} curriculum observations across ${lensResults.filter(Boolean).length} lenses.`)

// ---------------------------------------------------------------------------
// PHASE 2 — constraint gatekeeper: rule each proposed change against the
// invariants + the no-renumber rule. One agent over all observations.
// ---------------------------------------------------------------------------
phase('Constrain')
const gate = await agent(
  `${INTENT}\n\nYou are the CONSTRAINT GATEKEEPER. Below are proposed curriculum changes. ` +
    `For EACH, rule:\n` +
    `  keep   = sound and respects all constraints\n` +
    `  revise = good idea but needs a safer form (give saferChange) — e.g. blastRadius "renumber" ` +
    `must become an in-place repurpose; an invariant-risking change must be softened\n` +
    `  drop   = violates an invariant, requires renumbering with no in-place alternative, or is ` +
    `hype/speculative\n` +
    `Be strict: any proposal with blastRadius "renumber" is at least a "revise" unless it can't be ` +
    `salvaged (then "drop"). Return one ruling per observation id.\n\nPROPOSED CHANGES:\n` +
    JSON.stringify(observations, null, 2),
  { phase: 'Constrain', label: 'constraint-gate', agentType: 'Explore', schema: GATE_SCHEMA },
)
const rulings = (gate && gate.rulings) || []
const byId = {}
for (const o of observations) byId[o.id] = o
const vetted = rulings
  .filter((r) => r.verdict !== 'drop' && byId[r.id])
  .map((r) => ({ ...byId[r.id], verdict: r.verdict, finalChange: r.saferChange || byId[r.id].proposedChange, gateReason: r.reason }))
log(`Gatekeeper kept ${vetted.length} of ${observations.length} proposals.`)

// ---------------------------------------------------------------------------
// PHASE 3 — synthesize the curriculum report (returned as text; caller writes it).
// ---------------------------------------------------------------------------
phase('Synthesize')
const report = await agent(
  `${INTENT}\n\nYou are the curriculum synthesis lead. Produce a report as your final response ` +
    `(output ONLY markdown, no preamble, do NOT use the Write tool). Begin with ` +
    `"# Curriculum Analysis".\n\n` +
    `LENS HEADLINES:\n${JSON.stringify(lensSummaries, null, 2)}\n\n` +
    `VETTED PROPOSALS (passed the constraint gate):\n${JSON.stringify(vetted, null, 2)}\n\n` +
    `The report must contain:\n` +
    `1. A 5-line executive summary of the curriculum's structural health.\n` +
    `2. Findings grouped by theme: Coverage gaps, Phase balance, Ordering, Redundancy, ` +
    `Capstone coherence, Currency — ranked HIGH first, each with the affected days and the change.\n` +
    `3. A concrete **SWAP-MAP table**: | Repurpose (redundant/thin day, keep its number) | Into (gap topic) | Why |. ` +
    `Reconcile with IMPROVEMENT_PLAN.md's existing swap-map (extend, don't contradict).\n` +
    `4. A short "Sequenced recommendation" — what to do first (quick, in-place) vs later (needs author sign-off).\n` +
    `5. A "Coverage / what we did NOT check" note.\n` +
    `Every recommendation must keep the 100-day numbering and respect both invariants.`,
  { phase: 'Synthesize', label: 'synthesize-curriculum', agentType: 'Explore' },
)

return {
  lenses: lensResults.filter(Boolean).length,
  observations: observations.length,
  vetted: vetted.length,
  report, // caller writes this to CURRICULUM_REPORT.md
}

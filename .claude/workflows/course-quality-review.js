export const meta = {
  name: 'course-quality-review',
  description: 'Multi-agent analysis of the AI-engineering course: fan-out lenses → adversarial debate → arc audit → ranked report (optional auto-apply)',
  whenToUse: 'Review course lessons for quality/correctness while protecting the two invariants (simple SWE-migration course; low ML-background ceiling).',
  phases: [
    { title: 'Discover',   detail: 'enumerate the lesson files to review' },
    { title: 'Analyze',    detail: '4 independent lenses read each lesson in parallel' },
    { title: 'Debate',     detail: 'SWE-empathy vs rigor advocate per finding, judge + invariant gatekeeper rules' },
    { title: 'Arc Audit',  detail: 'whole-sequence checks: difficulty curve, prerequisite order, analogy coverage' },
    { title: 'Synthesize', detail: 'dedup, rank by impact, write ANALYSIS_REPORT.md' },
    { title: 'Apply',      detail: 'optional: apply approved fixes (one agent per file) then re-run the snippet checker' },
  ],
}

// ---------------------------------------------------------------------------
// CONFIG (via `args`)
//   args undefined                         -> review all 100 lessons
//   args = ["Phase_x/.../a.md", "..."]     -> review exactly those files
//   args = { paths?, limit?, apply?, debateSeverity? }
//     paths          : explicit file list (skips discovery)
//     limit          : cap number of lessons (great for a pilot run)
//     apply          : true => run the Apply phase and edit files in place
//     debateSeverity : "high" | "medium" | "low" — minimum severity that gets
//                      the full 2-advocate+judge debate. Lower findings get a
//                      single judge pass. Default "low" (debate everything).
// ---------------------------------------------------------------------------
const cfg = Array.isArray(args) ? { paths: args } : (args || {})
const APPLY = cfg.apply === true
const DEBATE_MIN = cfg.debateSeverity || 'low'
const SEV_RANK = { low: 0, medium: 1, high: 2 }

// ---------------------------------------------------------------------------
// THE RUBRIC — the two invariants, made concrete. Every agent scores against
// this exact text so "quality" means the same thing to all of them.
// ---------------------------------------------------------------------------
const RUBRIC = `
This is a 100-day course that helps EXPERIENCED SOFTWARE ENGINEERS become AI
engineers (building production LLM apps — NOT ML research). Judge everything
against these two load-bearing invariants:

INVARIANT 1 — It is a SIMPLE, job-focused SWE-migration course.
  - Every lesson should translate the AI concept into something a SWE already
    knows (the "Coming from Software Engineering?" analogy device).
  - It teaches a job-useful, buildable skill — not theory for its own sake.
  - Code must be copy-runnable against CURRENT SDKs (learners paste it directly).

INVARIANT 2 — The reader has LITTLE/NO ML background.
  - No unexplained ML jargon (gradient, softmax, logits, attention internals,
    backprop…). If a term is used it must be defined or replaced with plain words.
  - Each lesson starts from a concept the reader already knows and builds up.
  - A working SWE with zero ML could follow it start to finish without getting lost.

GATEKEEPER RULE: an "improvement" that makes a lesson MORE correct but also more
ML-theoretical, jargon-heavy, or harder for a non-ML SWE is a REGRESSION. Reject
it. Correctness and simplicity must both hold.

Authoritative facts (model IDs, pricing, library versions, day map) live in
REFERENCE.md — treat it as the source of truth and flag any lesson that drifts.
`

// ---------------------------------------------------------------------------
// SCHEMAS
// ---------------------------------------------------------------------------
const FINDINGS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      maxItems: 8, // most important issues only — avoid nit-flooding
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['lens', 'file', 'severity', 'issue', 'suggestedFix', 'invariantRisk'],
        properties: {
          lens: { type: 'string' },
          file: { type: 'string' },
          line: { type: 'string', description: 'line number or range, or "n/a"' },
          severity: { type: 'string', enum: ['low', 'medium', 'high'] },
          issue: { type: 'string', description: 'what is wrong, concretely' },
          suggestedFix: { type: 'string', description: 'the specific change to make' },
          invariantRisk: {
            type: 'string',
            description: 'does the FIX risk breaking invariant 1 or 2? "none" if not',
          },
        },
      },
    },
  },
}

// One judge per lesson rules on ALL that lesson's findings in a single call.
// It argues both the SWE-empathy and rigor sides internally before ruling —
// preserving the adversarial framing without spawning 3 agents per finding
// (which blew past the 1000-agent cap on the first run).
const LESSON_DEBATE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['verdicts'],
  properties: {
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['id', 'verdict', 'reason', 'breaksInvariant'],
        properties: {
          id: { type: 'string', description: 'the finding id being ruled on' },
          verdict: { type: 'string', enum: ['keep', 'drop', 'revise'] },
          reason: { type: 'string', description: 'why, noting both advocate views considered' },
          breaksInvariant: {
            type: 'string',
            description: '"none", "1", "2", or "1&2" — which invariant the fix would break',
          },
          finalFix: {
            type: 'string',
            description: 'the fix to apply; for "revise", the safer simpler version',
          },
        },
      },
    },
  },
}

const ARC_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['audit', 'observations'],
  properties: {
    audit: { type: 'string' },
    observations: {
      type: 'array',
      maxItems: 12,
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['days', 'observation', 'severity'],
        properties: {
          days: { type: 'string', description: 'e.g. "27" or "26-27" or "44-46"' },
          observation: { type: 'string' },
          severity: { type: 'string', enum: ['low', 'medium', 'high'] },
        },
      },
    },
  },
}

// ---------------------------------------------------------------------------
// PHASE 1 — DISCOVER
// ---------------------------------------------------------------------------
phase('Discover')
let lessons
if (cfg.paths && cfg.paths.length) {
  lessons = cfg.paths
  log(`Using ${lessons.length} explicitly-provided lesson path(s).`)
} else {
  const disc = await agent(
    `List every course lesson markdown file in this repo. Run:\n` +
      `  find Phase_* -name "*.md" -type f | sort\n` +
      `Return the paths as a JSON array under "lessons". ` +
      (cfg.limit ? `Return only the FIRST ${cfg.limit} after sorting.` : `Return all of them.`),
    {
      phase: 'Discover',
      label: 'discover-lessons',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['lessons'],
        properties: { lessons: { type: 'array', items: { type: 'string' } } },
      },
    },
  )
  lessons = (disc && disc.lessons) || []
}
if (cfg.limit) lessons = lessons.slice(0, cfg.limit)
log(`Reviewing ${lessons.length} lesson(s).`)
if (!lessons.length) return { error: 'No lessons found to review.' }

// ---------------------------------------------------------------------------
// The 4 analysis lenses. Each is deliberately blind to the others so they
// surface different problems.
// ---------------------------------------------------------------------------
const LENSES = [
  {
    key: 'beginner-sim',
    prompt: (f) =>
      `You are a working software engineer with ZERO machine-learning background. ` +
      `Read the lesson at ${f} top to bottom as a first-time learner. Flag the EXACT ` +
      `places where you'd get lost: undefined ML jargon, a leap that assumes ML knowledge, ` +
      `a missing or weak SWE analogy, or a difficulty spike. For each, the suggestedFix ` +
      `must make it simpler WITHOUT removing the real skill being taught.`,
  },
  {
    key: 'code-correctness',
    prompt: (f) =>
      `You are a code-correctness reviewer. Read every code block in ${f}. Check imports, ` +
      `SDK call signatures, model IDs, pricing, and library APIs against CURRENT reality. ` +
      `Do NOT trust your training memory for fast-moving SDKs — if unsure, WebFetch the ` +
      `provider's current docs, and cross-check model IDs/prices/library notes against ` +
      `REFERENCE.md (read it). Learners copy this code verbatim, so a wrong import or a ` +
      `stale/fabricated API call is a HIGH-severity finding. Flag anything not copy-runnable today.`,
  },
  {
    key: 'pedagogy',
    prompt: (f) =>
      `You are a curriculum/pedagogy reviewer. Check ${f} for: the standard lesson ` +
      `structure (Coming-from-SWE callout → prose+diagram → code with script_id → Summary ` +
      `→ Quick Reference → Exercises with collapsible solutions → Checkpoint → What's Next), ` +
      `the strength of the SWE analogy, clarity, and whether length fits the ~400-650 line ` +
      `band (capstones exempt). Suggest fixes that improve clarity without adding ML theory.`,
  },
  {
    key: 'redundancy-xref',
    prompt: (f) =>
      `You are a consistency reviewer for ${f}. Verify: every "Day N" reference and the ` +
      `"What's Next" footer point to the correct day per REFERENCE.md's day map (read it); ` +
      `code blocks keep balanced fences and intact script_id grouping; and the lesson does ` +
      `not substantially duplicate a neighbouring day. Flag broken cross-refs and redundancy.`,
  },
]

// ---------------------------------------------------------------------------
// PHASES 2 — ANALYZE + DEBATE, pipelined per lesson.
// A lesson's findings get debated the moment its analysis is done — no global
// barrier, so fast lessons don't wait on slow ones.
// ---------------------------------------------------------------------------
const perLesson = await pipeline(
  lessons,

  // Stage A: 4 lenses read the lesson in parallel, findings merged.
  async (file) => {
    const lensResults = await parallel(
      LENSES.map((lens) => () =>
        agent(`${RUBRIC}\n\n${lens.prompt(file)}`, {
          phase: 'Analyze',
          label: `analyze:${lens.key}:${file.split('/').pop()}`,
          schema: FINDINGS_SCHEMA,
          agentType: 'Explore', // read-only: analysis must NOT edit files
        }),
      ),
    )
    const findings = lensResults
      .filter(Boolean)
      .flatMap((r) => r.findings || [])
      .map((f, i) => ({ ...f, id: `${file}#${i}` }))
    return { file, findings }
  },

  // Stage B: ONE judge per lesson rules on all its findings (keep/revise/drop).
  // The judge internally argues the SWE-empathy vs rigor sides per finding, then
  // applies the gatekeeper. One agent per lesson keeps total fan-out bounded.
  async ({ file, findings }) => {
    if (!findings.length) return { file, kept: [] }

    const ruling = await agent(
      `${RUBRIC}\n\nYou are the JUDGE and INVARIANT GATEKEEPER for ${file}. Below are ` +
        `proposed changes from four independent reviewers. For EACH one, briefly weigh both ` +
        `sides — the SWE-empathy view (does this keep the lesson simple and useful for a ` +
        `non-ML SWE?) and the rigor view (is the current content genuinely wrong/misleading?) ` +
        `— then rule:\n` +
        `  keep   = apply the fix as-is\n` +
        `  revise = apply a simpler/safer version (put it in finalFix)\n` +
        `  drop   = reject (speculative, debatable, or it breaks an invariant)\n` +
        `Apply the GATEKEEPER RULE strictly: a fix that makes the lesson more ML-theoretical, ` +
        `jargon-heavy, or harder for a non-ML SWE is a REGRESSION — drop or revise it. ` +
        `Return one verdict object per finding, keyed by its id.\n\nFINDINGS:\n` +
        JSON.stringify(findings, null, 2),
      { phase: 'Debate', label: `judge:${file.split('/').pop()}`, schema: LESSON_DEBATE_SCHEMA, agentType: 'Explore' },
    )

    if (!ruling || !ruling.verdicts) return { file, kept: [] }
    const byId = {}
    for (const f of findings) byId[f.id] = f
    const kept = ruling.verdicts
      .filter((v) => v.verdict !== 'drop' && byId[v.id])
      .map((v) => ({
        ...byId[v.id],
        verdict: v.verdict,
        finalFix: v.finalFix || byId[v.id].suggestedFix,
        judgeReason: v.reason,
        breaksInvariant: v.breaksInvariant,
      }))
    return { file, kept }
  },
)

const approved = perLesson.filter(Boolean).flatMap((r) => r.kept)
log(`Debate complete: ${approved.length} approved change(s) across ${lessons.length} lesson(s).`)

// ---------------------------------------------------------------------------
// PHASE 3 — ARC AUDIT (whole-sequence checks no single-lesson agent can do).
// Runs concurrently; each agent reads across the full lesson set.
// ---------------------------------------------------------------------------
phase('Arc Audit')
const ARC_AUDITS = [
  {
    key: 'difficulty-curve',
    prompt:
      `Read the course index (index.md) and skim lessons as needed. Map the DIFFICULTY ` +
      `CURVE across the 100-day sequence and flag spikes — places where one day is a cliff ` +
      `after the previous (e.g. a sudden jump into infra or ML internals). Remember the ` +
      `reader is a SWE with no ML background.`,
  },
  {
    key: 'prerequisite-order',
    prompt:
      `Build a rough concept-dependency check from index.md (and GLOSSARY.md). Flag FORWARD ` +
      `REFERENCES: any day that uses a term/skill before the day that first teaches it. ` +
      `Forward references are a top reason beginners get lost.`,
  },
  {
    key: 'analogy-coverage',
    prompt:
      `Survey the "Coming from Software Engineering?" analogy across lessons (grep for the ` +
      `callout). Report days where the analogy is MISSING or WEAK/forced. This device is the ` +
      `course's core value; gaps in it are high-value to fix.`,
  },
  {
    key: 'jargon-density',
    prompt:
      `Sample lessons and estimate UNDEFINED ML-jargon density (terms used but not defined ` +
      `inline or in GLOSSARY.md). Identify the worst offenders — these break the ` +
      `low-ML-background invariant.`,
  },
]
const arc = await parallel(
  ARC_AUDITS.map((a) => () =>
    agent(`${RUBRIC}\n\n${a.prompt}`, { phase: 'Arc Audit', label: `arc:${a.key}`, schema: ARC_SCHEMA, agentType: 'Explore' }),
  ),
)
const arcResults = arc.filter(Boolean)

// ---------------------------------------------------------------------------
// PHASE 4 — SYNTHESIZE: dedup, rank, produce the report. NOTE: workflow
// subagents are blocked from writing files, so the synthesis agent RETURNS the
// report markdown as its text; the workflow returns it and the caller (main
// loop) writes ANALYSIS_REPORT.md to disk.
// ---------------------------------------------------------------------------
phase('Synthesize')
const report = await agent(
  `${RUBRIC}\n\nYou are the synthesis lead. Produce a prioritized review report as your ` +
    `final response — output ONLY the report markdown, no preamble, and do NOT use the Write ` +
    `tool (file writes are blocked; your returned text IS the report).\n\n` +
    `APPROVED PER-LESSON CHANGES (already passed adversarial debate + gatekeeper):\n` +
    JSON.stringify(approved, null, 2) +
    `\n\nWHOLE-ARC AUDITS:\n` +
    JSON.stringify(arcResults, null, 2) +
    `\n\nThe report must:\n` +
    `1. Open with a 5-line executive summary (how many lessons reviewed, top themes).\n` +
    `2. Group findings into themes (Correctness, Simplicity/jargon, Pedagogy/structure, ` +
    `Cross-reference, Arc/sequencing) and DEDUPLICATE near-identical items.\n` +
    `3. Rank within each theme by impact (HIGH first), each with file:line and the exact fix.\n` +
    `4. Have a "Quick wins" section (safe, mechanical, low-risk) vs "Needs author sign-off" ` +
    `(anything touching the day map, redundant-day repurposing, or provider choices — these ` +
    `are product decisions per CLAUDE.md).\n` +
    `5. End with a "Coverage / what we did NOT check" note so gaps are visible.\n` +
    `Keep recommendations true to the two invariants. Begin the report with "# Prioritized Review Report".`,
  { phase: 'Synthesize', label: 'synthesize-report', agentType: 'Explore' },
)
log('Synthesis complete — report returned to caller for writing to ANALYSIS_REPORT.md.')

// ---------------------------------------------------------------------------
// PHASE 5 — APPLY (opt-in via args.apply). One agent per file, so no two agents
// ever touch the same file (no worktree isolation needed). Then re-run the checker.
// ---------------------------------------------------------------------------
if (!APPLY) {
  return {
    reviewed: lessons.length,
    approvedChanges: approved.length,
    arcAudits: arcResults.length,
    applied: false,
    report, // caller writes this markdown to ANALYSIS_REPORT.md
    approvedDetail: approved, // structured findings, for an apply pass
    note: 'Analysis only. Caller: write `report` to ANALYSIS_REPORT.md. Re-run with args {apply:true} to apply.',
  }
}

phase('Apply')
const byFile = {}
for (const f of approved) (byFile[f.file] ||= []).push(f)
const files = Object.keys(byFile)

const applied = await parallel(
  files.map((file) => () =>
    agent(
      `${RUBRIC}\n\nApply ONLY these pre-approved changes to ${file} using the Edit tool. ` +
        `Do not make any other change. Preserve fence balance, script_id grouping, and the ` +
        `lesson structure. After editing, confirm what you changed.\n\nCHANGES:\n` +
        JSON.stringify(byFile[file], null, 2),
      { phase: 'Apply', label: `apply:${file.split('/').pop()}` },
    ),
  ),
)

// Verify nothing broke the renderer contract.
const check = await agent(
  `Run the snippet checker and report the result verbatim:\n` +
    `  python3 tools/check_snippets.py --strict\n` +
    `State clearly whether it passed (0 errors) or which files failed.`,
  { phase: 'Apply', label: 'verify-checker' },
)

return {
  reviewed: lessons.length,
  approvedChanges: approved.length,
  filesEdited: files.length,
  applied: true,
  appliedReports: applied.filter(Boolean),
  checkerResult: check,
}

export const meta = {
  name: 'apply-findings',
  description: 'Apply pre-reviewed, gatekept course-quality findings to lesson files — one agent per file, then run the snippet checker',
  whenToUse: 'After course-quality-review has produced .apply_findings.json (Batch-5 sign-off items already excluded). Applies the remaining findings in place.',
  phases: [
    { title: 'Apply', detail: 'one agent per lesson applies that file’s findings' },
    { title: 'Verify', detail: 'run tools/check_snippets.py --strict' },
  ],
}

// args = { files?: [lessonPath, ...], findingsPath?, fileListPath? }
// If files is omitted, a discover agent reads fileListPath (default .apply_filelist.json).
const cfg = args || {}
const FINDINGS = cfg.findingsPath || '.apply_findings.json'
const FILELIST = cfg.fileListPath || '.apply_filelist.json'

let FILES = cfg.files || []
if (!FILES.length) {
  const disc = await agent(
    `Read the JSON file ${FILELIST} (it is an array of lesson file paths) and return it. ` +
      `Run: python3 -c "import json;print(open('${FILELIST}').read())"  and return the array under "files".`,
    {
      label: 'discover-filelist',
      agentType: 'Explore',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['files'],
        properties: { files: { type: 'array', items: { type: 'string' } } },
      },
    },
  )
  FILES = (disc && disc.files) || []
}
if (!FILES.length) return { error: 'No files to process (args.files empty and fileListPath unreadable).' }

const RUBRIC = `
This course teaches EXPERIENCED SOFTWARE ENGINEERS to become AI engineers. Two
invariants are load-bearing and must survive every edit:
  1. Keep it a SIMPLE, job-focused course — SWE-translated, copy-runnable code.
  2. The reader has LITTLE/NO ML background — no unexplained jargon.
A change that adds ML theory or breaks copy-runnability is a regression. Also:
preserve code-fence balance (every \`\`\` opens and closes), keep blocks sharing a
\`script_id\` grouped and runnable, and keep the lesson's section structure intact.
`

phase('Apply')
const results = await pipeline(
  FILES,

  // Stage A: apply this file's findings.
  async (file) => {
    const out = await agent(
      `${RUBRIC}\n\nYou are applying PRE-APPROVED, already-debated review findings to a single ` +
        `lesson file. Do this carefully:\n\n` +
        `1. Run this to load just this file's findings:\n` +
        `   python3 -c "import json; d=json.load(open('${FINDINGS}')); ` +
        `print(json.dumps([f for f in d if '${file}' in (f.get('file') or '')], indent=2))"\n` +
        `2. Read ${file}.\n` +
        `3. For EACH finding, apply its \`finalFix\` to the file with the Edit tool. The fix text ` +
        `tells you the exact change; locate it by the \`issue\`/line context.\n` +
        `   - SKIP a finding (do not force it) if: the described text no longer matches, the fix ` +
        `is vague/ambiguous, it would break fence balance or script_id grouping, it adds ML theory/` +
        `jargon, or it conflicts with another finding. When two findings touch the same lines, apply ` +
        `the single best converged edit, not both.\n` +
        `   - Keep edits minimal and faithful — do not rewrite surrounding prose beyond the fix.\n` +
        `4. Do NOT edit any file other than ${file}. Do NOT run git.\n\n` +
        `Return a compact summary: counts of applied vs skipped, and a one-line reason for each skip.`,
      { phase: 'Apply', label: `apply:${file.split('/').pop()}` },
    )
    return { file, summary: out }
  },
)

const applied = results.filter(Boolean)
log(`Apply pass done across ${applied.length} file(s).`)

phase('Verify')
const check = await agent(
  `Run the course snippet checker and report output verbatim:\n` +
    `  python3 tools/check_snippets.py --strict\n` +
    `State clearly: did it pass (0 errors, 0 warnings)? If not, list each failing file and the message. ` +
    `Do not edit anything; just report.`,
  { phase: 'Verify', label: 'verify-checker' },
)

return {
  filesProcessed: applied.length,
  checkerResult: check,
  perFile: applied.map((r) => ({ file: r.file, summary: r.summary })),
}

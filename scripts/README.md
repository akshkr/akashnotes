# WordPress Publishing Script

Publishes the 100-day AI curriculum to WordPress via REST API.

## Setup

### 1. Python dependencies

```bash
cd scripts
pip install -r requirements.txt
```

### 2. WordPress: Create Application Password

1. Go to **Users → Profile**
2. Scroll to **Application Passwords**
3. Enter a name (e.g., "Publish Script") and click **Add New**
4. Copy the generated password

### 3. WordPress: Install plugins

**For Mermaid diagrams** (if using `--mermaid shortcode` mode):
- [WP Mermaid](https://wordpress.org/plugins/flavor/) — renders `[mermaid]` shortcodes

**For code highlighting** (pick one):
- [Highlight.js](https://wordpress.org/plugins/flavor/) — auto-highlights `<code class="language-python">`
- [Enlighter](https://wordpress.org/plugins/flavor/) — full-featured
- [Prismatic](https://wordpress.org/plugins/flavor/) — lightweight

### 4. Optional: Mermaid CLI (for pre-rendering diagrams to images/SVG)

```bash
npm install -g @mermaid-js/mermaid-cli
```

## Usage

### Publish all files as drafts

```bash
python publish_to_wordpress.py \
  --url https://yourblog.com \
  --user your_username \
  --password "xxxx xxxx xxxx xxxx"
```

### Publish immediately

```bash
python publish_to_wordpress.py \
  --url https://yourblog.com \
  --user your_username \
  --password "xxxx xxxx xxxx xxxx" \
  --publish
```

### Publish a single file

```bash
python publish_to_wordpress.py \
  --url https://yourblog.com \
  --user your_username \
  --password "xxxx xxxx xxxx xxxx" \
  --single "Phase_1_LLM_Foundations/Day_002_transformer_intuition/transformer_intuition.md"
```

### Pre-render mermaid diagrams to images

```bash
python publish_to_wordpress.py \
  --url https://yourblog.com \
  --user your_username \
  --password "xxxx xxxx xxxx xxxx" \
  --mermaid image
```

### Dry run (preview without publishing)

```bash
python publish_to_wordpress.py \
  --url https://yourblog.com \
  --user your_username \
  --password "xxxx xxxx xxxx xxxx" \
  --dry-run
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `--url` | WordPress site URL | required |
| `--user` | WordPress username | required |
| `--password` | Application Password | required |
| `--path` | Path to notes directory | `/Users/akash/Personal/notes` |
| `--publish` | Publish immediately instead of drafts | off |
| `--mermaid` | Mermaid mode: `shortcode`, `image`, or `svg` | `shortcode` |
| `--category` | Top-level WordPress category | `AI Curriculum` |
| `--delay` | Seconds between posts (rate limiting) | `1.0` |
| `--single` | Publish one specific file only | — |
| `--dry-run` | Preview without publishing | off |

## How it works

1. Walks `Phase_*/Day_*/` directories in order
2. For each `.md` file:
   - Extracts the `# Day N: Title` as the post title
   - Converts mermaid blocks to shortcodes (or pre-renders to SVG/PNG)
   - Converts code blocks to `<pre><code class="language-X">` for plugin highlighting
   - Converts "Coming from SWE?" callouts to styled HTML divs
   - Converts remaining markdown (tables, lists, bold, etc.) to HTML
3. Creates the post via `POST /wp-json/wp/v2/posts`
4. Organizes posts into categories: **AI Curriculum → Phase 1: LLM Foundations**, etc.

## Mermaid rendering modes

| Mode | How it works | Pros | Cons |
|------|-------------|------|------|
| `shortcode` | Outputs `[mermaid]...[/mermaid]` | Simple, no build step | Requires WP Mermaid plugin |
| `image` | Runs `mmdc` → uploads PNG | No plugin needed | Requires Node.js + mmdc |
| `svg` | Runs `mmdc` → inlines SVG | Crisp at any size, no plugin | Requires Node.js + mmdc, larger HTML |

## Troubleshooting

**"401 Unauthorized"** — Make sure you're using an Application Password, not your main password.

**"rest_cannot_create"** — Your user role may not have `publish_posts` capability. Check user permissions.

**Mermaid not rendering** — If using shortcode mode, ensure the WP Mermaid plugin is active. Otherwise, use `--mermaid image` or `--mermaid svg`.

**Code not highlighted** — Install a syntax highlighting plugin that supports `<code class="language-python">` format.

**Rate limited** — Increase `--delay` (default is 1 second between posts).

# WordPress Publishing Scripts

Scripts to publish the AI curriculum to WordPress with proper formatting.

## Setup

### 1. Install Python Dependencies

```bash
cd scripts
pip install -r requirements.txt
```

### 2. Install WordPress Plugins

Install these plugins on your WordPress site:

**For Mermaid Diagrams (pick one):**
- [WP Mermaid](https://wordpress.org/plugins/flavor/) - Renders mermaid shortcodes
- [Flavor](https://wordpress.org/plugins/flavor/) - Gutenberg mermaid support

**For Code Highlighting (pick one):**
- [SyntaxHighlighter Evolved](https://wordpress.org/plugins/syntaxhighlighter/) - Most compatible
- [Prismatic](https://wordpress.org/plugins/flavor/) - Lightweight
- [Code Block Pro](https://wordpress.org/plugins/flavor/) - Modern UI

### 3. Enable XML-RPC in WordPress

Go to **Settings → Writing** and ensure XML-RPC is enabled.

### 4. Create Application Password

1. Go to **Users → Profile**
2. Scroll to **Application Passwords**
3. Enter a name (e.g., "Publish Script")
4. Click **Add New Application Password**
5. Copy the generated password (you won't see it again!)

## Usage

### Publish All Files (as drafts)

```bash
python publish_to_wordpress.py \
  --url https://yourblog.com \
  --user your_username \
  --password "xxxx xxxx xxxx xxxx" \
  --path /Users/akash/Personal/notes
```

### Publish All Files (immediately)

```bash
python publish_to_wordpress.py \
  --url https://yourblog.com \
  --user your_username \
  --password "xxxx xxxx xxxx xxxx" \
  --publish
```

### Publish Single File

```bash
python publish_to_wordpress.py \
  --url https://yourblog.com \
  --user your_username \
  --password "xxxx xxxx xxxx xxxx" \
  --single "/Users/akash/Personal/notes/Month_1_LLM_Basics/Week_1_Introduction/01_llm_architecture.md"
```

### Convert Mermaid to Images

If the mermaid plugin doesn't work well, convert diagrams to images:

```bash
# First install mermaid-cli
npm install -g @mermaid-js/mermaid-cli

# Then run with --mermaid-images flag
python publish_to_wordpress.py \
  --url https://yourblog.com \
  --user your_username \
  --password "xxxx xxxx xxxx xxxx" \
  --mermaid-images
```

## Options

| Flag | Description |
|------|-------------|
| `--url` | WordPress site URL (required) |
| `--user` | WordPress username (required) |
| `--password` | Application password (required) |
| `--path` | Path to notes directory (default: /Users/akash/Personal/notes) |
| `--publish` | Publish immediately instead of creating drafts |
| `--mermaid-images` | Convert mermaid to PNG images |
| `--single` | Publish only one specific file |

## Output

The script will:
1. Create posts organized by category (Month X - Week Y)
2. Convert mermaid diagrams to shortcodes or images
3. Convert Python/Bash/YAML code blocks to syntax-highlighted shortcodes
4. Convert markdown tables to HTML

## Troubleshooting

### "XML-RPC services are disabled"
Enable XML-RPC in WordPress Settings → Writing

### "Invalid credentials"
Make sure you're using an Application Password, not your main password

### "Mermaid not rendering"
- Check if WP Mermaid plugin is activated
- Try the `--mermaid-images` flag instead

### "Code not highlighted"
- Install SyntaxHighlighter Evolved plugin
- Make sure it supports the language (python, bash, yaml)

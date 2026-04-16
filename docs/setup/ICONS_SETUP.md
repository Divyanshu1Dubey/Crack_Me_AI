# Icons Setup (Icons8 MCP + Bulk Downloads)

## 1) Icons8 MCP server in VS Code

Configured in:

- `.vscode/settings.json`
- `.vscode/mcp.json`

Server name: `icons8mcp`

Command used:

- `npx mcp-remote https://mcp.icons8.com/mcp/`

After this, restart VS Code and open Agent mode. You should see Icons8 MCP tools available.

## 2) Bulk-download icon assets into this project

A downloader is included at:

- `frontend/scripts/download-icons.mjs`

Manifest template:

- `frontend/icons/icons-manifest.json`

### Usage

```bash
cd frontend
npm run icons:download
```

Icons are saved to:

- `frontend/public/icons/custom/`

The script also writes an index file:

- `frontend/public/icons/custom/icons-index.json`

## 3) Add your Iconscout / Icons8 icon URLs

Edit `frontend/icons/icons-manifest.json` and add entries like:

```json
[
  {
    "name": "dashboard-analytics",
    "url": "https://...",
    "style": "line",
    "source": "iconscout",
    "notes": "sidebar dashboard"
  }
]
```

## 4) About listing all icons from your private dashboard

Your subscription dashboard data is private. To use all your icons here, export/copy your icon links and paste them into `icons-manifest.json`.

If you share that list in chat, I can map every icon to exact UI locations and replace current icons app-wide.

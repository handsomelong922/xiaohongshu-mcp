---
title: Xiaohongshu MCP
sdk: docker
app_port: 18060
pinned: false
short_description: Self-hosted Xiaohongshu MCP (fork deployment)
---

# Xiaohongshu MCP

This Space runs [handsomelong922/xiaohongshu-mcp](https://github.com/handsomelong922/xiaohongshu-mcp),
which tracks [xpzouying/xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp).

- MCP endpoint: `/mcp`
- Health endpoint: `/health`
- Login state: `/data/cookies.json` (requires a persistent, read-write bucket volume at `/data`)
- Authentication: the **Space must be Private**; clients must authenticate with a Hugging Face token.

Deployment is handled by the fork's GitHub Actions workflow; edits to this generated
Space repository will be overwritten on the next deployment.

The first time you connect, call the MCP tool `get_login_qrcode`, scan using the
Xiaohongshu mobile app, and verify with `check_login_status`.

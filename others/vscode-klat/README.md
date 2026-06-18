# Klat VSCode Auto-Open Integration

This lightweight VSCode extension automatically opens any files modified by the Klat CLI inside your editor tabs.

## Features

- **Automatic Connection**: Starts a fast, lightweight loopback server on port `55282`.
- **Zero Overhead**: Does not perform polling, diff computations, or load heavy packages.
- **Fast Open**: Uses VSCode's built-in file APIs to open modified files instantly.

## Installation

To install this extension locally:

1. Copy the `vscode-klat` folder into your VSCode extensions directory:
   - **Windows**: `%USERPROFILE%\.vscode\extensions\vscode-klat`
   - **macOS / Linux**: `~/.vscode/extensions/vscode-klat`
2. Restart or reload VSCode (`Developer: Reload Window` from the Command Palette).

## Configuration

You can customize the port in your VSCode `settings.json`:

```json
"klat.port": 55282
```

Make sure the same port is set if you configure it in Klat settings or environment variables (`vscode_port` in config/env).

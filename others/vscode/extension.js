const vscode = require('vscode');
const net = require('net');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { exec } = require('child_process');

let server = null;
let outputChannel = null;
let decorationProvider = null;
let fileWatcher = null;
let statusBarItem = null;

function log(message) {
    if (outputChannel) {
        outputChannel.appendLine(`[${new Date().toISOString()}] ${message}`);
    }
}

class KlatChangesGroup {
    constructor(label) {
        this.label = label;
        this.collapsibleState = vscode.TreeItemCollapsibleState.Expanded;
        this.contextValue = 'group';
    }
}

class KlatModifiedFilesProvider {
    constructor() {
        this._onDidChangeTreeData = new vscode.EventEmitter();
        this.onDidChangeTreeData = this._onDidChangeTreeData.event;
        this.modifiedFiles = new Map(); // lowercase path -> { path, status }
        this.changesGroup = new KlatChangesGroup('Changes');
    }

    refresh() {
        this._onDidChangeTreeData.fire();
    }

    addFile(filePath, status) {
        const resolvedPath = path.normalize(filePath);
        this.modifiedFiles.set(resolvedPath.toLowerCase(), { path: resolvedPath, status: status || 'M' });
        this.refresh();
        if (decorationProvider) {
            decorationProvider.refresh();
        }
    }

    getFile(filePath) {
        return this.modifiedFiles.get(path.normalize(filePath).toLowerCase());
    }

    clear() {
        this.modifiedFiles.clear();
        this.refresh();
        if (decorationProvider) {
            decorationProvider.refresh();
        }
    }

    getTreeItem(element) {
        if (element instanceof KlatChangesGroup) {
            const treeItem = new vscode.TreeItem(element.label, element.collapsibleState);
            treeItem.description = String(this.modifiedFiles.size);
            treeItem.contextValue = 'group';
            return treeItem;
        }

        const fileObj = this.getFile(element);
        const resolvedPath = fileObj ? fileObj.path : element;
        const klatUri = vscode.Uri.file(resolvedPath).with({ scheme: 'klat-file' });
        
        const treeItem = new vscode.TreeItem(klatUri);
        treeItem.description = true;
        treeItem.contextValue = 'file';
        treeItem.command = {
            command: 'klat.openFile',
            title: 'Open File',
            arguments: [resolvedPath]
        };
        return treeItem;
    }

    getChildren(element) {
        if (!element) {
            return [this.changesGroup];
        }
        if (element instanceof KlatChangesGroup) {
            return Array.from(this.modifiedFiles.values()).map(f => f.path);
        }
        return [];
    }
}

class KlatFileDecorationProvider {
    constructor(provider) {
        this._onDidChangeFileDecorations = new vscode.EventEmitter();
        this.onDidChangeFileDecorations = this._onDidChangeFileDecorations.event;
        this.provider = provider;
    }

    provideFileDecoration(uri) {
        if (uri.scheme === 'klat-file') {
            const filePath = uri.fsPath;
            const fileObj = this.provider.getFile(filePath);
            if (fileObj) {
                return {
                    badge: fileObj.status,
                    tooltip: `Modified by Klat: ${fileObj.status === 'M' ? 'Modified' : 'Untracked'}`
                };
            }
        }
        return undefined;
    }

    refresh() {
        this._onDidChangeFileDecorations.fire();
    }
}

function getKlatThemeColor() {
    const configPath = path.join(os.homedir(), '.klat', 'settings', 'config.json');
    let theme = 'green';
    try {
        if (fs.existsSync(configPath)) {
            const data = JSON.parse(fs.readFileSync(configPath, 'utf8'));
            if (data.theme) {
                theme = data.theme.toLowerCase().trim();
            }
        }
    } catch (e) {
        // fallback
    }

    const themeMap = {
        'green': '#00b450',
        'red': '#dc0032',
        'blue': '#0066cc',
        'yellow': '#f0a000',
        'pure white': '#ffffff',
        'orange': '#ff4400',
        'purple': '#8a2be2',
        'cyan': '#009696',
        'pink': '#ff1493',
        'rainbow': '#00e5a3',
        'animated_rainbow': '#00e5a3',
        'cyberpunk': '#ff0080',
        'sunset': '#ff0080',
        'matrix': '#00ff44',
        'ocean': '#0066ff',
        'forest': '#8cc878'
    };

    if (theme.startsWith('#')) {
        const parts = theme.split(/\s+/);
        if (parts[0]) return parts[0];
    }

    return themeMap[theme] || '#00b450';
}

function generateActivityBarIcon(color) {
    const mediaDir = path.join(__dirname, 'media');
    if (!fs.existsSync(mediaDir)) {
        fs.mkdirSync(mediaDir, { recursive: true });
    }
    const svgContent = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <path d="M4.5 2v12M4.5 8l6-6M4.5 8l6.5 6" stroke="${color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
    </svg>`;
    const iconPath = path.join(mediaDir, 'icon.svg');
    fs.writeFileSync(iconPath, svgContent, 'utf8');
}

function updateKlatTheme() {
    try {
        const color = getKlatThemeColor();
        generateActivityBarIcon(color);

        const config = vscode.workspace.getConfiguration('workbench');
        const colorCustomizations = config.get('colorCustomizations') || {};
        if (colorCustomizations['klat.accentColor'] !== color) {
            colorCustomizations['klat.accentColor'] = color;
            config.update('colorCustomizations', colorCustomizations, vscode.ConfigurationTarget.Global);
        }

        if (decorationProvider) {
            decorationProvider.refresh();
        }
    } catch (e) {
        log(`Failed to update theme: ${e.message}`);
    }
}

function findGitRoot(startPath) {
    try {
        let current = path.resolve(startPath);
        if (fs.existsSync(current) && fs.statSync(current).isFile()) {
            current = path.dirname(current);
        }
        while (true) {
            const gitDir = path.join(current, '.git');
            if (fs.existsSync(gitDir)) {
                return current;
            }
            const parent = path.dirname(current);
            if (parent === current) {
                break;
            }
            current = parent;
        }
    } catch (e) {
        // fallback
    }
    return null;
}

class KlatOriginalContentProvider {
    provideTextDocumentContent(uri) {
        const filePath = uri.fsPath;
        const gitRoot = findGitRoot(filePath);
        if (!gitRoot) {
            return '';
        }
        const relativePath = path.relative(gitRoot, filePath).replace(/\\/g, '/');
        return new Promise((resolve) => {
            exec(`git show "HEAD:${relativePath}"`, { cwd: gitRoot }, (error, stdout) => {
                if (error) {
                    resolve('');
                } else {
                    resolve(stdout);
                }
            });
        });
    }
}

function updateStatusBar(state) {
    if (!statusBarItem) {
        statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    }

    if (state === 'hidden') {
        statusBarItem.hide();
        return;
    }

    let text = '';
    let color = '';

    if (state === 'working') {
        text = `$(sync~spin) Klat: Working`;
        color = getKlatThemeColor();
    } else if (state === 'idle') {
        text = `$(circle-outline) Klat: Idle`;
    } else if (state === 'done') {
        text = `$(check) Klat: Done`;
        color = getKlatThemeColor();
    }

    statusBarItem.text = text;
    statusBarItem.color = color || undefined;
    statusBarItem.show();
}

let lastActiveFile = null;
let lastVisibleFiles = [];
let lastHighlightedText = null;

function updateVSCodeStateCache() {
    const activeEditor = vscode.window.activeTextEditor;
    if (activeEditor) {
        lastActiveFile = activeEditor.document.uri.fsPath;
        lastHighlightedText = activeEditor.document.getText(activeEditor.selection);
    }

    const visible = vscode.window.visibleTextEditors.map(e => e.document.uri.fsPath);
    if (visible.length > 0) {
        lastVisibleFiles = Array.from(new Set(visible));
    }
}

function getTabUri(tab) {
    if (!tab || !tab.input) return null;
    if (tab.input.uri) return tab.input.uri;
    if (tab.input.modified) return tab.input.modified;
    return null;
}

function getVSCodeState() {
    let activeFile = null;
    let openFiles = [];

    if (vscode.window.tabGroups) {
        try {
            const activeGroup = vscode.window.tabGroups.activeTabGroup;
            if (activeGroup && activeGroup.activeTab) {
                const uri = getTabUri(activeGroup.activeTab);
                if (uri && uri.scheme === 'file') {
                    activeFile = uri.fsPath;
                }
            }

            for (const group of vscode.window.tabGroups.all) {
                for (const tab of group.tabs) {
                    const uri = getTabUri(tab);
                    if (uri && uri.scheme === 'file') {
                        openFiles.push(uri.fsPath);
                    }
                }
            }
        } catch (e) {
            log(`Error reading tabGroups: ${e.message}`);
        }
    }

    updateVSCodeStateCache();

    if (!activeFile) {
        activeFile = lastActiveFile;
    }

    if (openFiles.length === 0) {
        openFiles = lastVisibleFiles;
    } else {
        // Merge with visible files
        openFiles = Array.from(new Set([...openFiles, ...lastVisibleFiles]));
    }

    return {
        active_file: activeFile,
        visible_files: openFiles,
        highlighted_text: lastHighlightedText
    };
}

function openFileOrDiff(filePath, status) {
    const isUntracked = status === 'U';
    if (isUntracked) {
        const uri = vscode.Uri.file(filePath);
        vscode.workspace.openTextDocument(uri).then(doc => {
            vscode.window.showTextDocument(doc, { preview: false });
        }, err => {
            log(`Failed to open document: ${err.message}`);
        });
    } else {
        const originalUri = vscode.Uri.file(filePath).with({ scheme: 'klat-original' });
        const modifiedUri = vscode.Uri.file(filePath);
        const fileName = path.basename(filePath);
        vscode.commands.executeCommand('vscode.diff', originalUri, modifiedUri, `${fileName} (Original) <-> (Modified by Klat)`);
    }
}

function activate(context) {
    outputChannel = vscode.window.createOutputChannel('Klat Integration');
    log('Klat VSCode Integration activating...');

    const provider = new KlatModifiedFilesProvider();
    decorationProvider = new KlatFileDecorationProvider(provider);

    updateKlatTheme();

    updateVSCodeStateCache();
    vscode.window.onDidChangeActiveTextEditor(updateVSCodeStateCache, null, context.subscriptions);
    vscode.window.onDidChangeTextEditorSelection(updateVSCodeStateCache, null, context.subscriptions);

    const originalProvider = new KlatOriginalContentProvider();
    const origProviderReg = vscode.workspace.registerTextDocumentContentProvider('klat-original', originalProvider);
    context.subscriptions.push(origProviderReg);

    const configPath = path.join(os.homedir(), '.klat', 'settings', 'config.json');
    try {
        if (fs.existsSync(configPath)) {
            fileWatcher = fs.watch(configPath, (eventType) => {
                if (eventType === 'change') {
                    updateKlatTheme();
                }
            });
        }
    } catch (e) {
        log(`Failed to setup config watcher: ${e.message}`);
    }

    const treeView = vscode.window.createTreeView('klat-modified-files', {
        treeDataProvider: provider
    });

    const decProviderReg = vscode.window.registerFileDecorationProvider(decorationProvider);

    const port = vscode.workspace.getConfiguration('klat').get('port') || 55282;

    function startServer() {
        if (server) {
            try {
                server.close();
            } catch (e) {
                // ignore
            }
        }

        server = net.createServer((socket) => {
            log('Klat CLI client connected.');
            updateStatusBar('idle');
            
            provider.clear();
            treeView.badge = undefined;

            let buffer = '';

            socket.on('data', (data) => {
                buffer += data.toString('utf8');
                let boundary = buffer.indexOf('\n');
                while (boundary !== -1) {
                    const line = buffer.substring(0, boundary).trim();
                    buffer = buffer.substring(boundary + 1);
                    boundary = buffer.indexOf('\n');
                    
                    if (line) {
                        try {
                            const msg = JSON.parse(line);
                            if (msg.action === 'open') {
                                const filePath = msg.path;
                                const status = msg.status || 'M';
                                if (filePath) {
                                    log(`Received open: ${filePath} (${status})`);
                                    provider.addFile(filePath, status);

                                    const count = provider.modifiedFiles.size;
                                    treeView.badge = {
                                        value: count,
                                        tooltip: `${count} file(s) modified by Klat`
                                    };

                                    openFileOrDiff(filePath, status);
                                }
                            } else if (msg.action === 'clear') {
                                log('Received clear command from Klat CLI.');
                                provider.clear();
                                treeView.badge = undefined;
                            } else if (msg.action === 'status') {
                                updateStatusBar(msg.state);
                            } else if (msg.action === 'get_state') {
                                socket.write(JSON.stringify(getVSCodeState()) + '\n');
                            }
                        } catch (e) {
                            log(`Error parsing message line: ${e.message}`);
                        }
                    }
                }
            });

            socket.on('end', () => {
                log('Klat CLI client connection ended.');
                provider.clear();
                treeView.badge = undefined;
                updateStatusBar('hidden');
            });

            socket.on('error', (err) => {
                log(`Socket error: ${err.message}`);
                provider.clear();
                treeView.badge = undefined;
                updateStatusBar('hidden');
            });
        });

        server.on('error', (err) => {
            const msg = `Klat Integration failed to start TCP server on port ${port}: ${err.message}`;
            log(msg);
            vscode.window.showErrorMessage(msg);
        });

        server.listen(port, '127.0.0.1', () => {
            log(`Klat VSCode TCP server listening on 127.0.0.1:${port}`);
        });
    }

    startServer();

    const reconnectCmd = vscode.commands.registerCommand('klat.reconnect', () => {
        log('Force reconnecting / restarting TCP server...');
        provider.clear();
        treeView.badge = undefined;
        startServer();
        vscode.window.showInformationMessage('Klat integration server restarted.');
    });

    const openCmd = vscode.commands.registerCommand('klat.openFile', (filePath) => {
        const fileObj = provider.getFile(filePath);
        const status = fileObj ? fileObj.status : 'M';
        openFileOrDiff(filePath, status);
    });

    context.subscriptions.push(treeView, decProviderReg, reconnectCmd, openCmd, {
        dispose() {
            if (server) {
                server.close();
                log('Klat VSCode server stopped.');
            }
            if (fileWatcher) {
                fileWatcher.close();
            }
            if (outputChannel) {
                outputChannel.dispose();
            }
            if (statusBarItem) {
                statusBarItem.dispose();
            }
        }
    });
}

function deactivate() {
    if (server) {
        server.close();
    }
    if (fileWatcher) {
        fileWatcher.close();
    }
    if (statusBarItem) {
        statusBarItem.dispose();
    }
}

module.exports = {
    activate,
    deactivate
};

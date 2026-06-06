# 技术架构文档 - CLI 展示页面

## 技术栈

- **纯前端**: HTML5 + CSS3 + Vanilla JavaScript
- **无框架依赖**: 零外部库，单文件实现
- **字体**: JetBrains Mono (Google Fonts CDN)

## 文件结构

```
web/
└── cli.html          # CLI 展示页面（单文件）
```

## 核心模块

### 1. Terminal 类

```javascript
class Terminal {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.history = [];
        this.historyIndex = -1;
        this.currentLine = '';
        this.isTyping = false;
    }

    async type(text, speed = 30) {
        // 打字机效果输出
    }

    execute(command) {
        // 解析并执行命令
    }

    clear() {
        // 清屏
    }
}
```

### 2. 命令注册表

```javascript
const commands = {
    help: () => displayHelp(),
    about: () => displayAbout(),
    agents: () => displayAgents(),
    factors: () => displayFactors(),
    risk: () => displayRisk(),
    architecture: () => displayArchitecture(),
    distillation: () => displayDistillation(),
    reflection: () => displayReflection(),
    clear: () => terminal.clear(),
    exit: () => displayExit(),
};
```

### 3. 启动动画序列

```javascript
const bootSequence = [
    { text: 'BIOS Date: 05/13/26 14:22:51 Ver 3.1', delay: 100 },
    { text: 'CPU: QuantCore i9-9900K @ 5.00GHz', delay: 200 },
    { text: 'Memory Test: 65536K OK', delay: 300 },
    { text: '', delay: 100 },
    { text: 'Loading Factor Trading v3.0 ...', delay: 500 },
    { text: '[OK] Core Engine Loaded', delay: 200 },
    { text: '[OK] Agent Framework Loaded', delay: 200 },
    { text: '[OK] Risk Monitor Loaded', delay: 200 },
    { text: '[OK] 228 Tests Passed', delay: 300 },
    { text: '', delay: 100 },
    { text: 'System Ready.', delay: 200 },
];
```

## 样式规范

### 颜色变量

```css
:root {
    --bg-primary: #0d1117;
    --bg-secondary: #161b22;
    --text-primary: #3fb950;
    --text-secondary: #8b949e;
    --text-accent: #58a6ff;
    --text-warning: #d29922;
    --border-color: #30363d;
    --cursor-color: #3fb950;
}
```

### 字体

```css
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');

body {
    font-family: 'JetBrains Mono', monospace;
    font-size: 14px;
    line-height: 1.6;
}
```

## 性能优化

- 使用 `requestAnimationFrame` 实现流畅打字效果
- 虚拟滚动处理大量输出
- 本地存储命令历史（最多 100 条）

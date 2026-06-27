# 任务清单桌面小部件

一个基于 PySide6 的 Windows 桌面任务清单小部件，置顶显示在桌面上，随时提醒我们当前还有哪些任务待办。

## 功能

- 在桌面显示一个无边框、半透明、圆角的小窗口
- **添加任务**：在输入框中输入任务内容，按回车或点击 + 按钮
- **编辑任务**：点击任务右侧的 ✎ 按钮，修改后按回车或失去焦点自动保存
- **排序任务**：按住任务左侧的 ≡ 拖动，可调整任务顺序
- **完成任务**：点击任务左侧的复选框标记完成/未完成
- **删除任务**：点击任务右侧的 × 按钮
- **精简模式**：点击标题栏 ◱ 切换到迷你视图，只显示待办任务数量
- **系统托盘图标**：悬停显示任务统计，点击显示/隐藏窗口
- 任务数据自动保存到 `data/tasks.json`，关闭后不会丢失
- 支持鼠标拖动调整窗口位置

## 运行环境

- Windows
- Python 3.11+
- 使用 [uv](https://github.com/astral-sh/uv) 管理依赖

## 开发运行

```bash
# 进入项目目录
cd task-widget

# 使用 uv 运行源码
uv run main.py
```

或者：

```bash
uv run task-widget
```

## 测试模式

```bash
uv run main.py --test
```

测试模式会在 3 秒后自动退出，用于验证程序能否正常启动。

## 打包成 exe

已配置 PyInstaller，直接运行：

```bash
uv run pyinstaller --onefile --windowed --name task-widget --icon=NONE main.py
```

打包完成后，可执行文件位于：

```
dist/task-widget.exe
```

可以直接复制该 exe 到任意位置运行，无需安装 Python。

## 项目结构

```
task-widget/
├── main.py                          # 主程序
├── pyproject.toml                   # 项目配置与依赖
├── README.md                        # 说明文档
├── CHANGELOG.md                     # 更新日志
├── .gitignore                       # Git 忽略规则
├── task-widget.spec                 # PyInstaller 配置文件
├── scripts/
│   ├── install_autostart.py         # 安装并设置开机自启
│   └── remove_autostart.py          # 移除开机自启并删除安装文件
└── data/                            # 运行时的任务数据（自动创建）
    └── tasks.json
```

## 设置开机自启

先打包出 exe，然后运行安装脚本：

```bash
cd task-widget
uv run pyinstaller --onefile --windowed --name task-widget --icon=NONE main.py
uv run scripts/install_autostart.py
```

这会把程序复制到 `%APPDATA%\TaskWidget\task-widget.exe`，并写入注册表 `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`，下次登录时自动启动。

可以在 **任务管理器 > 启动** 中查看是否已启用。

## 取消开机自启

```bash
uv run scripts/remove_autostart.py
```

这会删除注册表启动项，并删除 `%APPDATA%\TaskWidget\` 下的程序文件。

## 更新日志

详见 [CHANGELOG.md](CHANGELOG.md)。

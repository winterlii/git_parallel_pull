# -*- coding: utf-8 -*-
"""
并行 git pull 多个仓库

用法（三种方式任选其一，按优先级）：
1. 命令行参数：  python test.py repo1 repo2 repo3
2. 填写下方 REPOS 列表里的路径
3. 什么都不做：自动扫描本脚本所在目录下所有的一级子文件夹中带 .git 的仓库

例如把三个 repo 文件夹直接放在 test.py 同级目录下，直接运行 python test.py 即可。
"""
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Windows 下终端默认编码可能不是 UTF-8，会导致中文输出报错，这里强制用 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 三个仓库的路径（支持绝对路径或相对本脚本的路径）；留空则自动扫描
REPOS = [
    # r"C:\Users\MCUPTE\Desktop\repo1",
    # r"C:\Users\MCUPTE\Desktop\repo2",
    # r"C:\Users\MCUPTE\Desktop\repo3",
]

SCRIPT_DIR = Path(__file__).resolve().parent


def is_git_repo(path: Path) -> bool:
    """判断目录是否为 git 仓库（.git 可能是文件夹也可能是文件，如 submodule/worktree）"""
    return path.is_dir() and (path / ".git").exists()


def collect_repos() -> list[Path]:
    # 1) 命令行参数优先
    if len(sys.argv) > 1:
        return [Path(p).expanduser().resolve() for p in sys.argv[1:]]
    # 2) REPOS 配置
    if REPOS:
        return [Path(p).expanduser().resolve() for p in REPOS]
    # 3) 自动扫描脚本所在目录的一级子文件夹
    return sorted(p for p in SCRIPT_DIR.iterdir() if is_git_repo(p))


def git_pull(repo: Path) -> tuple[Path, bool, str]:
    """对单个仓库执行 git pull，返回 (路径, 是否成功, 输出)"""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "pull"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        output = (result.stdout + result.stderr).strip()
        return repo, result.returncode == 0, output
    except FileNotFoundError:
        return repo, False, "未找到 git 命令，请确认已安装 Git 并加入 PATH"
    except subprocess.TimeoutExpired:
        return repo, False, "拉取超时（超过 300 秒）"
    except Exception as e:  # noqa: BLE001
        return repo, False, f"执行异常: {e}"


def show_popup(title: str, message: str, kind: str = "error") -> None:
    """弹出提示对话框；tkinter 不可用时依次回退到 Windows MessageBox / 控制台输出

    kind: "error" 显示错误图标，"info" 显示信息图标
    """
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口，只显示弹窗
        root.attributes("-topmost", True)  # 保证弹窗置顶可见
        if kind == "info":
            messagebox.showinfo(title, message, parent=root)
        else:
            messagebox.showerror(title, message, parent=root)
        root.destroy()
        return
    except Exception:  # noqa: BLE001 - 弹窗失败不影响主流程
        pass

    if sys.platform == "win32":
        try:
            import ctypes

            icon = 0x40 if kind == "info" else 0x10  # 0x40 信息图标 / 0x10 错误图标
            ctypes.windll.user32.MessageBoxW(0, message, title, icon)
            return
        except Exception:  # noqa: BLE001
            pass

    print(f"[{title}] {message}")


def main() -> None:
    repos = collect_repos()
    if not repos:
        print("未找到任何 git 仓库。")
        print("请把仓库文件夹放在本脚本同级目录，或在 REPOS 中填写路径，或通过命令行参数传入。")
        return

    # 检查路径有效性
    valid, invalid = [], []
    for repo in repos:
        if is_git_repo(repo):
            valid.append(repo)
        else:
            invalid.append(repo)

    if invalid:
        for repo in invalid:
            print(f"[跳过] 不是 git 仓库: {repo}")

    if not valid:
        print("没有可更新的仓库。")
        return

    print(f"共 {len(valid)} 个仓库，开始并行 git pull ...\n")

    # 并行执行，每个仓库一个线程
    with ThreadPoolExecutor(max_workers=len(valid)) as pool:
        results = list(pool.map(git_pull, valid))

    # 汇总输出
    for repo, ok, output in results:
        status = "成功" if ok else "失败"
        print("=" * 60)
        print(f"[{status}] {repo.name}  <-  {repo}")
        print(output if output else "(没有新内容，已是最新)")
    print("=" * 60)

    failed = [str(repo) for repo, ok, _ in results if not ok]
    if failed:
        print(f"\n{len(failed)} 个仓库更新失败：")
        for path in failed:
            print(f"  - {path}")
        # 弹窗列出失败的仓库，避免只在控制台输出容易看漏
        show_popup(
            "git pull 更新失败",
            f"以下 {len(failed)} 个仓库更新失败：\n\n" + "\n".join(f"- {p}" for p in failed),
        )
        sys.exit(1)
    print("\n全部仓库更新完成。")
    # 全部成功时弹窗提示
    show_popup("git pull 更新成功", f"全部 {len(results)} 个仓库更新成功。", kind="info")


if __name__ == "__main__":
    main()

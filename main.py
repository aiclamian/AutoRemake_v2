import os
import sys
import shutil

from utils import (
    create_remake_archive_section, apply_remake_archive_section, mkdirs,
    sections, remake_arch_dir, down_dir,
)


def create_remake_archive():
    print("[i] 创建 Remake Archive 归档")

    print("[i] 清理归档目录")
    if remake_arch_dir.exists():
        if remake_arch_dir.is_file():
            remake_arch_dir.unlink()
        else:
            shutil.rmtree(remake_arch_dir)
    mkdirs(remake_arch_dir)
    if down_dir.exists():
        if down_dir.is_file():
            down_dir.unlink()
        else:
            shutil.rmtree(down_dir)
    mkdirs(down_dir)

    for section in sections:
        create_remake_archive_section(section)

    print("[✔] Remake Archive 创建完成")


def apply_remake_archive():
    print("[i] 应用 Remake Archive 归档")

    for section in sections:
        apply_remake_archive_section(section)

    print("[✔] Remake Archive 应用完成")


if __name__ == "__main__":
    print("[i] **!*!** AutoRemake **!*!**")

    if os.geteuid() != 0:
        print("[✘] AutoRemake 必须由用户 'root' 应用")
        sys.exit(1)

    mode = input("[i] 请选择模式 [Create/Apply]: ").strip().lower()
    if mode in ["create", "c"]:
        create_remake_archive()
    elif mode in ["apply", "a"]:
        apply_remake_archive()
    else:
        print(f"[✘] 模式 {mode} 不存在")

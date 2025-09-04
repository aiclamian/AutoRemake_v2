import shutil

from utils import remake_arch_dir, down_dir, script_dir


def main():
    print("[i] **!*!** AutoRemake **!*!**")
    mode = input("[i] 是否清理文件夹 [Yes/No]: ").strip().lower()
    if mode in ["yes", "y"]:
        print("[i] 清理归档及缓存目录")
        if remake_arch_dir.exists():
            if remake_arch_dir.is_file():
                remake_arch_dir.unlink()
            else:
                shutil.rmtree(remake_arch_dir)
        if down_dir.exists():
            if down_dir.is_file():
                down_dir.unlink()
            else:
                shutil.rmtree(down_dir)
        cache_dir = script_dir / "__pycache__"
        if cache_dir.exists():
            if cache_dir.is_file():
                cache_dir.unlink()
            else:
                shutil.rmtree(cache_dir)
        print(f"[✔] 清理完成")
    else:
        print("[i] 退出")


if __name__ == "__main__":
    main()
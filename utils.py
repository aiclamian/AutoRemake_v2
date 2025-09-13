import json
import os
import pwd
import re
import shutil
import subprocess
import sys
import tarfile
import urllib
import urllib.request
import zipfile
from pathlib import Path
from typing import NotRequired, TypedDict
from urllib.error import HTTPError

import yaml


class ConfigDict(TypedDict):
    username: NotRequired[str]
    hostname: NotRequired[str]
    sections: NotRequired[list[str]]


class RemakeArchSectionDict(TypedDict):
    desc: str
    cmds: NotRequired[list[str]]
    files: NotRequired[list[str | dict[str, str]]]


# 配置文件和目录位置
config_name = "config.yml"
remake_arch_map_name = "remake_arch_map.yml"
down_dir_name = "downloads"
remake_arch_dir_name = "remake_arch"
script_dir = Path(__file__).resolve().parent
# 读取用户名
config_path = script_dir / config_name
if not config_path.exists():
    print(f"[✘] 配置文件 '{config_name}' 不存在，退出！")
    sys.exit(1)
with open(config_path, "r") as f:
    config: ConfigDict = yaml.safe_load(f)
if "username" not in config:
    print("[✘] 配置项 'username' 不存在，退出！")
    sys.exit(1)
if "hostname" not in config:
    print("[] 配置项 'hostname' 不存在，退出！")
    sys.exit(1)
if "sections" not in config:
    print("[✘] 配置项 'sections' 不存在，退出！")
    sys.exit(1)
username: str = config["username"]
hostname: str = config["hostname"]
sections: list[str] = config["sections"]
# 读取用户信息
try:
    userinfo = pwd.getpwnam(username)
    print(f"[✔] 用户 '{username}' 信息获取成功！")
except KeyError:
    print(f"[✘] 用户 '{username}' 信息获取失败，退出！")
    sys.exit(1)
uid = userinfo.pw_uid
gid = userinfo.pw_gid
home = Path(userinfo.pw_dir)
# 加载 remake arch map
remake_arch_map_path = script_dir / remake_arch_map_name
if not remake_arch_map_path.exists():
    print(f"[✘] 配置文件 '{remake_arch_map_name}' 不存在，退出！")
    sys.exit(1)
with open(remake_arch_map_path, "r") as f:
    remake_arch_map: dict[str, RemakeArchSectionDict] = yaml.safe_load(f)
# 设置目录位置
down_dir = script_dir / down_dir_name
remake_arch_dir = script_dir / remake_arch_dir_name
# 校验
print(f"[i] 校验 '{remake_arch_map_name}' 合法性")
if not isinstance(remake_arch_map, dict):
    print(f"[✘] '{remake_arch_map_name}' 顶层必须是字典")
    sys.exit(1)
for section_name, section_content in remake_arch_map.items():
    if not isinstance(section_content, dict):
        print(f"[✘] 项目 '{section_name}' 必须是字典")
        sys.exit(1)
    if "desc" not in section_content or not isinstance(section_content["desc"], str):
        print(f"[✘] 项目 '{section_name}' 缺少字符串类型的 'desc'")
        sys.exit(1)
    if "cmds" not in section_content and "files" not in section_content:
        print(f"[✘] 项目 '{section_name}' 必须包含 'cmds' 或 'files'")
        sys.exit(1)
    all_allowed_keys = {"desc", "cmds", "files"}
    keys = set(section_content.keys())
    extra_keys = keys - all_allowed_keys
    if extra_keys:
        print(f"[✘] 项目 '{section_name}' 包含不允许的多余键: '{extra_keys}'")
    if "cmds" in section_content:
        cmds = section_content["cmds"]
        if not isinstance(cmds, list) or not all(isinstance(cmd, str) for cmd in cmds):
            print(f"[✘] 项目 '{section_content}' 的 'cmds' 必须是字符串组成的列表")
            sys.exit(1)
    if "files" in section_content:
        files = section_content["files"]
        if not isinstance(files, list):
            print(f"[✘] 项目 '{section_content}' 的 'files' 必须是列表")
            sys.exit(1)
        for idx, f in enumerate(files):
            if isinstance(f, str):
                continue
            elif isinstance(f, dict):
                required_keys = {"url", "src"}
                optional_keys = {"decomp", "dst"}
                all_allowed_keys = required_keys | optional_keys
                keys = set(f.keys())
                if not required_keys.issubset(keys):
                    missing = required_keys - keys
                    print(
                        f"[✘] 模块 '{section_name}' 的 'files[{idx}]' 缺少必须的键: '{
                            missing
                        }'"
                    )
                    sys.exit(1)
                extra_keys = keys - all_allowed_keys
                if extra_keys:
                    print(
                        f"[✘] 项目 '{section_name}' 的 'files[{
                            idx
                        }]' 包含不允许的多余键: '{extra_keys}'"
                    )
                    sys.exit(1)
            else:
                print(
                    f"[✘] 项目 '{section_name}' 的 'files[{
                        idx
                    }]' 必须是字符串或特定结构的字典"
                )
                sys.exit(1)
print(f"[✔] '{remake_arch_map_name}' 合法性校验通过")


# tools


def mkdirs(path: Path | str) -> None:
    path = Path(path).resolve()
    parents = list(path.parents)[::-1] + [path]

    for p in parents:
        if not p.exists():
            p.mkdir()
            os.chown(p, uid, gid)


def chown_user(path: Path) -> None:
    if path.is_file():
        os.chown(path, uid, gid)

    elif path.is_dir():
        for root, _, files in os.walk(path):
            r = Path(root)
            os.chown(r, uid, gid)
            for f in files:
                os.chown(r / f, uid, gid)


def chown_src(src: Path, dst: Path) -> None:
    if src.is_file():
        st = src.lstat()
        os.chown(dst, st.st_uid, st.st_gid)

    elif src.is_dir():
        for root, _, files in os.walk(src):
            src_r = Path(root)
            dst_r = dst / src_r.relative_to(src)
            st = src_r.lstat()
            os.chown(dst_r, st.st_uid, st.st_gid)

            for f in files:
                s_f = src_r / f
                d_f = dst_r / f
                st = s_f.lstat()
                os.chown(d_f, st.st_uid, st.st_gid)


# create remake archive


def create_remake_archive_section(section_name: str) -> None:
    print(f"[i] 开始为项目 '{section_name}' 创建归档")
    if section_name not in remake_arch_map:
        print(f"[!] 项目 '{section_name}' 不存在于 '{remake_arch_map_name}' 中，跳过")
        return

    section_map = remake_arch_map[section_name]
    if "files" not in section_map:
        print(f"[✔] 项目 '{section_name}' 不需要备份文件, 创建归档完成")
        return

    section_files: list[str | dict[str, str]] = section_map["files"]
    for section_file in section_files:
        if isinstance(section_file, str):
            backup(section_file)
        elif isinstance(section_file, dict):
            download(section_file)
            decompress(section_file)
            move(section_file)
        else:
            print(f"[!] 未知类型的 file, 请检查 '{remake_arch_map_name}'")

    print(f"[✔] 项目 '{section_name}' 创建归档完成")


def backup(section_file: str) -> None:
    rel_path = section_file
    src = home / rel_path
    dst = remake_arch_dir / rel_path

    print(f"[i] 备份文件或目录 '{src}' 到归档目录")

    if not src.exists():
        print(f"[✘] 源文件或目录不存在，跳过: '{src}'")
        return

    if dst.exists():
        print(f"[!] 归档中文件或目录 '{dst}' 已存在，删除")
        if dst.is_dir():
            shutil.rmtree(dst)
        elif dst.is_file():
            dst.unlink()
        else:
            print(f"[✘] 文件或目录 '{dst}' 不是普通的文件或目录, 归档失败")
            return

    if src.is_dir():
        mkdirs(dst)
        try:
            shutil.copytree(src, dst, dirs_exist_ok=True)
            chown_src(src, dst)
            print(f"[✔] 已备份目录: '{src}' -> '{dst}'")
        except Exception as e:
            print(f"[✘] 备份目录失败: '{src}' -> '{dst}'\n    原因: '{e}'")
    else:
        mkdirs(dst.parent)
        try:
            shutil.copy2(src, dst)
            chown_src(src, dst)
            print(f"[✔] 已备份文件: '{src}' -> '{dst}'")
        except Exception as e:
            print(f"[✘] 备份文件失败: '{src}' -> '{dst}'\n    原因: '{e}'")


class GitHubURLFormatError(Exception):
    pass


class GitHubRequestError(Exception):
    pass


class GitHubResponseError(Exception):
    pass


def _match_github_download_url(url: str) -> str:
    match = re.match(r"https://github\.com/([^/]+)/([^/]+)/releases/download/", url)
    if not match:
        raise GitHubURLFormatError

    owner, repo = match.groups()

    latest_api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"

    with urllib.request.urlopen(latest_api_url) as response:
        if response.status != 200:
            raise GitHubRequestError

        data: dict = json.load(response)
        tag_name: str | None = data.get("tag_name", None)
        if tag_name is None:
            raise GitHubResponseError
        version = tag_name.lstrip("v")

    return url.replace("{version}", version)


def _download_file(url: str, dst: Path) -> None:
    with urllib.request.urlopen(url) as response:
        total_size = int(response.getheader("Content-Length", 0))
        block_size = 8192
        downloaded = 0

        with open(dst, "wb") as out_file:
            while True:
                buffer = response.read(block_size)
                if not buffer:
                    break
                out_file.write(buffer)
                downloaded += len(buffer)
                if total_size:
                    percent = downloaded * 100 / total_size
                    print(
                        f"\r[i] 下载中: '{percent:.2f}%' ('{downloaded}'/'{
                            total_size
                        }' 字节)",
                        end="",
                    )
                else:
                    print(f"\r[i] 下载中: '{downloaded}' 字节", end="")
    chown_user(dst)
    print(f"\n[✔] 下载完成: '{dst}'")


def download(section_file: dict[str, str]) -> None:
    if "url" not in section_file or "src" not in section_file:
        return

    url = section_file["url"]
    tgt_name = section_file["src"]
    print(f"[i] 下载文件 '{tgt_name}' 到下载目录")

    if "{version}" in url:
        try:
            url = _match_github_download_url(url)
        except GitHubURLFormatError:
            print(f"[✘] URL '{url}' 模板格式错误")
            return
        except HTTPError:
            print("[✘] 获取最新下载链接失败，网络错误")
            return
        except GitHubRequestError:
            print("[✘] 获取最新下载链接失败，状态码错误")
            return
        except GitHubResponseError:
            print("[✘] 获取最新下载链接失败，响应错误")
            return
        except Exception:
            print("[✘] 获取最新下载链接失败")
            return

    try:
        _download_file(url, down_dir / tgt_name)
        print(f"[✔] 下载文件 '{tgt_name}' 成功")
    except Exception as e:
        print(f"[✘] 下载文件 '{tgt_name}' 失败：'{e}'")


def decompress(section_file: dict[str, str]) -> None:
    if "src" not in section_file or "decomp" not in section_file:
        return

    tgt_name = section_file["src"]
    print(f"[i] 解压文件 '{tgt_name}' 到临时目录")

    tgt = down_dir / tgt_name
    if not tgt.exists():
        print(f"[✘] 文件 '{tgt_name}' 不存在！跳过")
        return

    tmp_path = down_dir / "tmp"
    if tmp_path.is_dir():
        shutil.rmtree(tmp_path)
    elif tmp_path.is_file():
        tmp_path.unlink()

    if zipfile.is_zipfile(tgt):
        with zipfile.ZipFile(tgt, "r") as zip_ref:
            zip_ref.extractall(tmp_path)
        chown_user(tmp_path)
        print(f"[✔] ZIP 文件解压完成：'{tgt_name}'")

    elif tarfile.is_tarfile(tgt):
        with tarfile.open(tgt, "r:*") as tar_ref:
            tar_ref.extractall(tmp_path)
        chown_user(tmp_path)
        print(f"[✔] TAR 文件解压完成：'{tgt_name}'")

    else:
        print("[✘] 不支持的压缩包类型")


def move(section_file: dict[str, str]) -> None:
    if "dst" not in section_file:
        return
    dst = remake_arch_dir / section_file["dst"]

    if "decomp" in section_file:
        src = down_dir / "tmp" / section_file["decomp"]
    elif "src" in section_file:
        src = down_dir / section_file["src"]
    else:
        return

    print(f"[i] 移动文件或目录 '{src}' 到归档目录")

    if not src.exists():
        print(f"[✘] 源文件或目录不存在，跳过: '{src}'")
        return

    if dst.exists():
        print(f"[!] 归档中文件或目录 '{dst}' 已存在，删除")
        if dst.is_dir():
            shutil.rmtree(dst)
        elif dst.is_file():
            dst.unlink()
        else:
            print(f"[✘] 文件或目录 '{dst}' 不是普通的文件或目录, 归档失败")
            return

    if src.is_dir():
        mkdirs(dst)
        try:
            shutil.copytree(src, dst, dirs_exist_ok=True)
            chown_src(src, dst)
            shutil.rmtree(src)
            print(f"[✔] 已移动目录: '{src}' -> '{dst}'")
        except Exception as e:
            print(f"[✘] 移动目录失败: '{src}' -> '{dst}'\n    原因: '{e}'")
    else:
        mkdirs(dst.parent)
        try:
            shutil.copy2(src, dst)
            chown_src(src, dst)
            src.unlink()
            print(f"[✔] 已移动文件: '{src}' -> '{dst}'")
        except Exception as e:
            print(f"[✘] 移动文件失败: '{src}' -> '{dst}'\n    原因: '{e}'")


# apple remake archive


def apply_remake_archive_section(section_name: str) -> None:
    print(f"[i] 开始为项目 '{section_name}' 应用归档")
    if section_name not in remake_arch_map:
        print(f"[!] 项目 '{section_name}' 不存在于 '{remake_arch_map_name}' 中，跳过")
        return

    section_map = remake_arch_map[section_name]
    if "cmds" in section_map:
        section_cmds: list[str] = section_map["cmds"]
        for section_cmd in section_cmds:
            run_cmd(section_cmd)

    if "files" in section_map:
        section_files: list[str | dict[str, str]] = section_map["files"]
        for section_file in section_files:
            restore(section_file)

    print(f"[✔] 项目 '{section_name}' 应用归档完成")


def run_cmd(cmd: str, check: bool = True) -> None:
    # 定义替换映射表（变量名 -> 替换值）
    replacements = {
        "{username}": username,
        "{hostname}": hostname,
        "{uid}": str(uid),
        "{gid}": str(gid),
        "{home}": str(home),
        "{down_dir}": str(down_dir),
        "{remake_arch_dir}": str(remake_arch_dir),
    }

    processed_cmd = cmd.strip()
    for placeholder, value in replacements.items():
        processed_cmd = processed_cmd.replace(placeholder, value)

    print(f"[i] 执行命令：'{processed_cmd}'")

    try:
        subprocess.run(
            processed_cmd,
            executable="/bin/bash",
            shell=True,
            check=check,
        )
        print("[✔] 执行成功")
    except subprocess.CalledProcessError as e:
        print(f"[✘] 命令失败：'{e}'")


def restore(section_file) -> None:
    if isinstance(section_file, str):
        src = remake_arch_dir / section_file
        dst = home / section_file
    elif isinstance(section_file, dict):
        if "dst" not in section_file:
            return
        src = remake_arch_dir / section_file["dst"]
        dst = home / section_file["dst"]
    else:
        return

    print(f"[i] 从归档目录 '{src}' 还原到目标位置")

    if not src.exists():
        print(f"[✘] 归档目录文件或目录 '{src}' 不存在！跳过")
        return

    if dst.exists():
        print(f"[!] 目标位置文件或目录 '{dst}' 已存在，删除")
        if dst.is_dir():
            shutil.rmtree(dst)
        elif dst.is_file():
            dst.unlink()
        else:
            print(f"[✘] 目标位置文件或目录 '{dst}' 不是普通的文件或目录，执行失败")
            return

    if src.is_dir():
        mkdirs(dst)
        try:
            shutil.copytree(src, dst, dirs_exist_ok=True)
            chown_src(src, dst)
            print(f"[✔] 已还原目录: '{src}' -> '{dst}'")
        except Exception as e:
            print(f"[✘] 还原目录失败: '{src}' -> '{dst}'\n    原因: '{e}'")
    else:
        mkdirs(dst.parent)
        try:
            shutil.copy2(src, dst)
            chown_src(src, dst)
            print(f"[✔] 已还原文件: '{src}' -> '{dst}'")
        except Exception as e:
            print(f"[✘] 还原文件失败: '{src}' -> '{dst}'\n    原因: '{e}'")

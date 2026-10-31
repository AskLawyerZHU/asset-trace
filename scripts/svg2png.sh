#!/bin/bash
# asset-trace 速读图 SVG → PNG（macOS 原生 AppKit 渲染，零依赖）
# 用法: svg2png.sh <文件1.svg> [文件2.svg ...]
#       环境变量 AT_PNG_SCALE 控制倍率（默认 2，即 680 宽出 1360px）
# 说明: qlmanage 在部分宿主环境被沙箱拦截不可用，本脚本走 NSImage（JXA）。
#       PNG 输出到各 SVG 同目录；SVG 始终保留为源文件。
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
SCALE="${AT_PNG_SCALE:-2}"
for f in "$@"; do
  [ -f "$f" ] || { echo "跳过（不存在）: $f"; continue; }
  out="${f%.svg}.png"
  result=$(osascript -l JavaScript "$DIR/svg2png.js" "$f" "$out" "$SCALE")
  echo "$result"
  case "$result" in OK*) ;; *) exit 1 ;; esac
done

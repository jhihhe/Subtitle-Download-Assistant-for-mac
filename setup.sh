#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/python_backend"

echo "安装 Python 依赖..."
python3 -m pip install -r requirements.txt

echo "依赖安装完成。"

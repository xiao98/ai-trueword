#!/bin/bash
# AI真言机 — 服务器一键部署脚本
# 目标: Ubuntu 24.04
# 用法: bash setup.sh

set -e

echo "=== AI真言机 服务器部署 ==="

# 1. 系统更新 + 基础依赖
echo "[1/5] 安装系统依赖..."
apt update && apt upgrade -y
apt install -y python3.12 python3.12-venv python3-pip git

# 2. 创建应用用户
echo "[2/5] 创建应用用户..."
if ! id "trueword" &>/dev/null; then
    useradd -m -s /bin/bash trueword
fi

# 3. 拉取代码
echo "[3/5] 拉取代码..."
cd /home/trueword
if [ -d "ai-trueword" ]; then
    cd ai-trueword && git pull
else
    git clone https://github.com/xiao98/ai-trueword.git
    cd ai-trueword
fi

# 4. Python虚拟环境 + 依赖
echo "[4/5] 安装Python依赖..."
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -e ".[platforms]"

# 创建数据目录
mkdir -p data

# 设置权限
chown -R trueword:trueword /home/trueword/ai-trueword

# 5. 安装systemd服务
echo "[5/5] 配置systemd服务..."
cp deploy/ai-trueword-web.service /etc/systemd/system/
cp deploy/ai-trueword-bilibili.service /etc/systemd/system/
systemctl daemon-reload

echo ""
echo "=== 部署完成 ==="
echo ""
echo "接下来需要："
echo "1. 编辑环境变量文件:"
echo "   nano /home/trueword/ai-trueword/.env"
echo ""
echo "2. 启动服务:"
echo "   systemctl start ai-trueword-web"
echo "   systemctl start ai-trueword-bilibili"
echo ""
echo "3. 设置开机自启:"
echo "   systemctl enable ai-trueword-web"
echo "   systemctl enable ai-trueword-bilibili"
echo ""
echo "4. 查看日志:"
echo "   journalctl -u ai-trueword-bilibili -f"

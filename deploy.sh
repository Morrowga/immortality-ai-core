#!/bin/bash
set -e

echo "Deploying backend..."
cd ~/immortality-ai-core
git pull
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart immortality-backend
echo "Backend deployed."
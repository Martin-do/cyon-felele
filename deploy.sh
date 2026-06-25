#!/bin/bash
set -e

echo "🚀 Starting Deployment Process..."

# 1. Get latest code
echo "📦 Pulling latest code from GitHub..."
git fetch --all
git reset --hard origin/main

# 2. Install any new dependencies
echo "🐍 Activating virtual environment and installing dependencies..."
source venv/bin/activate
pip install -r requirements.txt

# 3. Apply database changes
echo "🗄️ Running database migrations..."
python manage.py migrate

# 4. Collect static files
echo "🎨 Collecting static files..."
python manage.py collectstatic --noinput

# 5. Fix permissions (Just in case git pull or collectstatic changed ownership)
echo "🔒 Fixing file permissions..."
sudo chown -R root:www-data /var/www/cyon_felele
sudo chmod -R 755 /var/www/cyon_felele

# 6. Restart services
echo "🔄 Reloading system configurations..."
sudo systemctl daemon-reload

echo "🚀 Restarting Gunicorn and Nginx..."
sudo systemctl restart gunicorn
sudo systemctl restart nginx

echo "✅ Deployment complete! The portal is live and synced."

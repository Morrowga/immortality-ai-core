# 1. Create venv (first time only)
python -m venv venv

# 2. Activate
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows

# 3. Install dependencies (first time only)
pip install -r requirements.txt

# 4. Install cryptography (first time only)
pip install cryptography

# 5. Generate encryption key (first time only — save this to .env)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Copy the output and add to .env as:
# ENCRYPTION_KEY=your-generated-key-here

# 6. Run the app
uvicorn app.main:app --reload

# Status
sudo systemctl status immortality-backend.service

# Restart
sudo systemctl restart immortality-backend.service

# Stop
sudo systemctl stop immortality-backend.service

# Logs (live follow)
sudo journalctl -u immortality-backend.service -f

# Logs (last 100 lines)
sudo journalctl -u immortality-backend.service -n 100
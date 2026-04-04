# 1. Create venv (first time only)
python -m venv venv

# 2. Activate
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows

# 3. Install dependencies (first time only)
pip install -r requirements.txt

# 4. Run the app
uvicorn app.main:app --reload
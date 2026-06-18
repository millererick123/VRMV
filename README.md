# Clone the repo
git clone <repo-url>
cd VRMV

# Create .env (already has your token committed as an example — fill it in)
cp .env.example .env
# Edit .env with your credentials

pip install -r requirements.txt
python main.py --test   # verify connection
python main.py          # run the full audit

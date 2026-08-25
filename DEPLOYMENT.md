# Deployment Guide

## 1) Push to GitHub

1. Create a new GitHub repository.
2. From this project root, run:

```powershell
git init
git add .
git commit -m "Initial Streamlit trading lab"
git branch -M main
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```

## 2) Host on Streamlit Community Cloud (recommended)

1. Go to https://share.streamlit.io and sign in with GitHub.
2. Click `New app`.
3. Select your repository, branch `main`, and main file `streamlit_app.py`.
4. Click `Deploy`.

The app installs dependencies from `requirements.txt` automatically.

## 3) Optional: Host on Render

1. Create a new `Web Service` from your GitHub repository.
2. Build command:

```bash
pip install -r requirements.txt
```

3. Start command:

```bash
streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0
```

## 4) GitHub Actions CI

A CI workflow is included at `.github/workflows/ci.yml`.
It runs compile checks and tests on pushes and pull requests.

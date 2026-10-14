# Deploy for free (Render, about 10 minutes)

## 1. Put the code on GitHub
Create an empty repo on github.com, then in PowerShell inside the project folder:
```powershell
git init
git add .
git commit -m "XploraKodo tutor"
git branch -M main
git remote add origin https://github.com/<your-username>/xplorakodo-tutor.git
git push -u origin main
```
`.gitignore` already skips `.venv`, `.env` and the `.db` file.

## 2. Create the service on Render
1. Sign up at render.com with GitHub.
2. **New > Blueprint**, pick your repo. Render reads `render.yaml` and creates the free web service.
   Manual way: New > Web Service, Runtime Python, Build `pip install -r requirements.txt`,
   Start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, Instance type Free.
3. Wait for the build. Your URL looks like `https://xplorakodo-tutor.onrender.com`.
4. Open `https://<your-url>/api/health`. You should see `{"ok":true,"grader":"mock"}`.

## 3. What to expect on the free plan (checked against Render's docs, October 2026)
- The service **sleeps after 15 minutes without traffic**; the next visit takes up to about a minute to wake.
- The **filesystem is ephemeral**: the SQLite file (students, scores, heatmap) is **erased on every restart, redeploy or sleep**.
  The browser still remembers profile names, but the app will then say the student was not found and the user creates the profile again.
- So this is right for demos and showing the project. For real students you need storage that survives:
  free Postgres on Neon or Supabase (schema in `db/schema.postgres.sql`; `app/db.py` needs a Postgres version, the next build step),
  or a paid Render instance with a persistent disk.

## 4. Real AI grading (optional)
In Render > Environment add `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY=...`, and add `anthropic` to `requirements.txt`.
Keep `DAILY_TOKEN_BUDGET` low so a public link cannot run up a bill. Never commit the key.

## Other options
- **Hugging Face Spaces (Docker)**: free CPU, sleeps when idle, disk not persistent. Use the included `Dockerfile`, set `app_port: 7860` in the Space README header and `PORT=7860`.
  One Hugging Face doc page says creating Docker Spaces needs a paid plan, so check at signup.
- **Any Docker host**: `docker build -t xk . && docker run -p 8000:8000 xk`.

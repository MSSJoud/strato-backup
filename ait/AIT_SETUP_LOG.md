# AIT Setup Log

## LLMgeoChat

### 1. Create local Node environment

```bash
conda create -p /home/ubuntu/work/ait/.node-env -y -c conda-forge nodejs=20
```

### 2. Install dependencies

```bash
cd /home/ubuntu/work/ait/LLMgeoChat
PATH=/home/ubuntu/work/ait/.node-env/bin:$PATH npm install --legacy-peer-deps
```

### 3. Create env file

```bash
cp .env.example .env.local
```

Minimum required values in `.env.local`:

```bash
BASE_URL=http://localhost:3000
NEXT_PUBLIC_BASE_URL=http://localhost:3000
NEXT_PUBLIC_APP_URL=http://localhost:3000
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
OPENAI_API_KEY=
GOOGLE_MAPS_API_KEY=
GCP_SERVICE_ACCOUNT_KEY=
```

### 4. Check missing env vars

```bash
PATH=/home/ubuntu/work/ait/.node-env/bin:$PATH npm run check-env
```

### 5. Start the app

```bash
PATH=/home/ubuntu/work/ait/.node-env/bin:$PATH npm run dev
```

### 6. Open the chat

- Browser: `http://localhost:3000/` or `http://localhost:3000/dashboard`
- If not logged in, the app redirects to `/login`

### 7. See the chat in VS Code

- Open the `PORTS` panel
- Forward port `3000` if needed
- Use `Open in Browser` or `Open in Preview` if your VS Code build provides it
- If preview is missing, open the forwarded URL in the normal browser

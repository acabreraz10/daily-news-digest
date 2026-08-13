# Daily News Digest

Automated news aggregator that sends you a morning digest and intraday updates via email. Pulls from 20+ RSS feeds across tech, finance, world news, sports, Colombia, and more.

## How It Works

1. **Fetches** articles from RSS feeds (BBC, Reuters, NYT, TechCrunch, Bloomberg, El Tiempo, etc.)
2. **Deduplicates** articles across sources
3. **Categorizes** by topic using keyword matching (AI & Tech, Finance, Colombia, Soccer, Tennis, etc.)
4. **Formats** a clean HTML email grouped by topic
5. **Sends** via Outlook/Office 365 SMTP

Runs automatically 3x/day via GitHub Actions:
- **6:00 AM PST** — Full morning digest (last 24 hours)
- **12:00 PM PST** — Midday update (last 6 hours)
- **5:00 PM PST** — Evening update (last 6 hours)

## Quick Start

### 1. Clone and install locally (for testing)

```bash
git clone <your-repo-url>
cd daily-news-digest
pip install -r requirements.txt
```

### 2. Test it locally (no email sent)

```bash
python -m src.main test
```

This fetches real articles and prints the digest to your console.

### 3. Set up email (for actual delivery)

Create a `.env` file (never commit this):

```bash
EMAIL_SENDER=your-outlook-email@company.com
EMAIL_PASSWORD=your-app-password
EMAIL_RECIPIENT=your-outlook-email@company.com
```

Then run with email delivery:

```bash
# Load env vars and run
# PowerShell:
$env:EMAIL_SENDER="your-email@company.com"; $env:EMAIL_PASSWORD="your-app-password"; $env:EMAIL_RECIPIENT="your-email@company.com"; python -m src.main digest

# Bash/Linux:
export EMAIL_SENDER="your-email@company.com"
export EMAIL_PASSWORD="your-app-password"
export EMAIL_RECIPIENT="your-email@company.com"
python -m src.main digest
```

## GitHub Actions Setup (Automated Daily Emails)

### Step 1: Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit - daily news digest"
gh repo create daily-news-digest --private --push
```

### Step 2: Add Secrets

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these secrets:

| Secret Name | Value |
|------------|-------|
| `EMAIL_SENDER` | Your Outlook email address |
| `EMAIL_PASSWORD` | Your app password (see below) |
| `EMAIL_RECIPIENT` | Email to receive the digest (can be same as sender) |
| `SMTP_SERVER` | `smtp.office365.com` (optional, this is the default) |
| `SMTP_PORT` | `587` (optional, this is the default) |

### Step 3: Generate an App Password (Outlook/Office 365)

Your regular password won't work with SMTP. You need an app password:

**For Microsoft 365 / Work Account:**
1. Go to [https://mysignins.microsoft.com/security-info](https://mysignins.microsoft.com/security-info)
2. Click **+ Add sign-in method** → **App password**
3. Give it a name (e.g., "News Digest")
4. Copy the generated password — use this as `EMAIL_PASSWORD`

**Note:** If your org disables app passwords, ask your IT admin about SMTP relay or use a personal Gmail account instead (change `SMTP_SERVER` to `smtp.gmail.com`).

### Step 4: Enable the Workflow

The workflow runs automatically on schedule. You can also trigger it manually:

1. Go to **Actions** tab in your repo
2. Select **Daily News Digest** workflow
3. Click **Run workflow** → choose `digest` or `update`

## Configuration

Edit `config.yaml` to customize:

- **Topics** — Add/remove categories and their keywords
- **Feeds** — Add/remove RSS sources
- **Schedule** — Adjust lookback hours and max articles per topic
- **Timing** — Edit `.github/workflows/digest.yml` cron expressions

### Adding a New Feed

```yaml
feeds:
  - name: "Your Feed Name"
    url: "https://example.com/rss"
    language: "en"
    default_topic: "AI & Technology"  # Must match a topic name
```

### Adding a New Topic

```yaml
topics:
  - name: "Your Topic"
    icon: "\U0001F4A1"  # Unicode emoji
    keywords:
      - keyword1
      - keyword2
```

## Project Structure

```
daily-news-digest/
├── src/
│   ├── __init__.py
│   ├── feeds.py          # RSS fetching + deduplication
│   ├── categorizer.py    # Topic classification
│   ├── formatter.py      # HTML email builder
│   ├── emailer.py        # SMTP delivery (Office 365)
│   └── main.py           # CLI orchestrator
├── config.yaml           # Feeds, topics, settings
├── requirements.txt      # Python dependencies
├── .github/workflows/
│   └── digest.yml        # GitHub Actions schedule
└── README.md
```

## CLI Usage

```bash
python -m src.main digest      # Full morning digest (24h lookback)
python -m src.main update      # Intraday update (6h lookback)
python -m src.main test        # Dry run - prints to console
python -m src.main digest --dry-run  # Fetch real data, don't send email
```

## Troubleshooting

**"SMTP authentication failed"**
- Make sure you're using an app password, not your regular password
- Check that SMTP is enabled for your account (some orgs disable it)

**"No articles fetched"**
- Some feeds may be temporarily down. Run `test` mode to see which feeds respond
- Check your internet connection

**GitHub Actions not running**
- Scheduled workflows only run on the default branch (usually `main`)
- GitHub may delay cron jobs by a few minutes
- Check the Actions tab for error logs

**Want to use Gmail instead?**
- Set `SMTP_SERVER` to `smtp.gmail.com`
- Generate an app password at [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
- Everything else stays the same

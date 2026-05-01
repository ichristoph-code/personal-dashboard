# 💰 YNAB Financial Dashboard

Generate a beautiful, interactive HTML dashboard with your real-time YNAB financial data!

## Features

✨ **Real-time data** from your YNAB account
📊 **Interactive charts** showing account balances and spending
💳 **Account breakdown** - checking, savings, credit cards, and more
📈 **Category activity** visualization
🎨 **Beautiful design** with gradient backgrounds and modern UI
⚡ **Fast** - generates in seconds

## Quick Start

### Step 1: Get Your YNAB API Token

1. Log into YNAB at [app.ynab.com](https://app.ynab.com)
2. Click on your email/name in the bottom left
3. Select **"Account Settings"**
4. Go to **"Developer Settings"**
5. Click **"New Token"** or **"Personal Access Tokens"**
6. Give it a name (like "Financial Dashboard")
7. Copy the token (it will look like a long string of random characters)

### Step 2: Add Your Token to Config File

1. Open `ynab_config.json` in a text editor
2. Replace `YOUR_YNAB_API_TOKEN_HERE` with your actual token
3. Save the file

**Example:**
```json
{
  "api_token": "abc123def456ghi789jkl0mnop1qrst2uvwxyz",
  "budget_id": "last-used"
}
```

### Step 3: Install Required Package

Open terminal and run:
```bash
pip install requests --break-system-packages
```

Or if you prefer using pip3:
```bash
pip3 install requests --break-system-packages
```

### Step 4: Run the Program

```bash
python3 ynab_dashboard.py
```

The program will:
- Connect to your YNAB account
- Fetch all your financial data
- Generate `ynab_dashboard.html`
- Tell you when it's ready!

### Step 5: View Your Dashboard

Simply **double-click** the `ynab_dashboard.html` file to open it in your browser!

## What You'll See

### 📊 Summary Cards
- **Total Net Worth** - All your accounts combined
- **Budget Accounts** - Money actively budgeted
- **Tracking Accounts** - Off-budget accounts

### 📈 Charts
- **Account Balances Bar Chart** - Visual comparison of all accounts
- **Category Activity** - Top spending categories this month

### 🏦 Account Details
Organized by type:
- Checking & Savings accounts
- Credit Cards
- Other accounts (investments, loans, etc.)

## Updating Your Dashboard

Just run the program again anytime:
```bash
python3 ynab_dashboard.py
```

It will regenerate the HTML with your latest YNAB data!

## Troubleshooting

### "Config file not found"
- Make sure `ynab_config.json` is in the same folder as `ynab_dashboard.py`

### "Please add your YNAB API token"
- Open `ynab_config.json` and replace `YOUR_YNAB_API_TOKEN_HERE` with your actual token

### "API Error: 401"
- Your API token is invalid or expired
- Generate a new token in YNAB settings

### "No module named 'requests'"
- Run: `pip install requests --break-system-packages`

## Security Note

⚠️ **Keep your API token private!** Don't share `ynab_config.json` with anyone or commit it to version control.

Your token gives full access to your YNAB data. Treat it like a password.

## Files in This Program

- `ynab_dashboard.py` - Main program that fetches data and generates HTML
- `ynab_config.json` - Your API token (keep this private!)
- `ynab_dashboard.html` - The generated dashboard (opens in browser)
- `README.md` - This file

## Tips

💡 **Bookmark the dashboard** - Keep `ynab_dashboard.html` bookmarked for quick access
💡 **Run daily** - Add to your morning routine to check your finances
💡 **Mobile friendly** - The dashboard works on phones and tablets too!

## Need Help?

If you run into issues, make sure:
1. You have an active YNAB subscription
2. Your API token is correctly copied (no extra spaces)
3. You have internet connection
4. Python 3 is installed (`python3 --version`)

---

**Enjoy your financial dashboard!** 🎉

# CurveBot

## Setup Instructions

### Linux / Mac
```bash
python -m venv venv
source venv/bin/activate
```

### Windows
```bash
python -m venv venv
venv\Scripts\activate
```

## Install dependencies

```bash
pip install -r requirements.txt
```

## Running the bot

### To run the bot:

```bash
python bot.py
```

### To run the bot with mock data (no API calls):
```bash
python bot.py --mockdata
```

### To run tests
```bash
DATABASE=test_bot_data.db pytest tests.py
```

## Using the Makefile

### Run the bot:
```bash
make bot
```

### Run the bot with mockdata:
```bash
make bot-mock
```

### Run tests:
```bash
make test
```

## Environment Variables

### Set the following environment variables before running the bot

```bash
BOT_TOKEN: <key from Telegram BotFather>
BOT_USERNAME: <bot username>
DATABASE: bot_data.db
VIDO_API_KEY: <your VIDO API key>
ADMIN_ID: <your Telegram user ID>
```

## Suggested workflow

1. Add bot to a group
2. Go to the bot chat and type /groups
3. This will return your all groups and their ID's
4. In the bot chat, type /reference <group_id> <urls>
5. OR add a text file with URLs, make caption /reference <group_id>
6. IMPORTANT: Include "-" in the ID if its returned in #3
7. Use /sgl <group_id> <group_limit> to set the group limit
8. Use /sul <group_id> <user_limit> to set a limit for users

That should be it

Repeating any of the commands will override in the database
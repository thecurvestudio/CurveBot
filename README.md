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
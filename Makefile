test:
	DATABASE=test_bot_data.db pytest -s tests.py

bot-mock:
	python bot.py --mockdata

bot:
	python bot.py
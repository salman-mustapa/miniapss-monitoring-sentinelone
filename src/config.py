# src/config.py
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, 'config', 'config.json')

def load_config():
	if not os.path.exists(CONFIG_PATH):
		raise FileNotFoundError(f'Config file not found at {CONFIG_PATH}. run setup_config.py first')
	with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
		return json.load(f)

if __name__ == '__main__':
	print('Testing load_config →', CONFIG_PATH)

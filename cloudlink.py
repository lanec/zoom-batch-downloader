import datetime
import math
import os
import re
import shutil
import unicodedata
from calendar import monthrange
from time import sleep

import colorama
import requests
from colorama import Fore, Style

# Zoom API credentials
ACCOUNT_ID = '##########'
CLIENT_ID = '##########'
CLIENT_SECRET = '##########'

# Put your USER IDs that you get from the API. If empty, all data from all users will be downloaded.
USERIDS = [
	# '##########'
]

# Put your own download path here, I used an external hard drive so mine will differ from yours
PATH = '/Volumes/Ext3/Zoom/'

# Date range (inclusive) for downloads, None value for Days gets replaced by first/last day of the month.
START_DAY, START_MONTH, START_YEAR = None, 5, 2020
END_DAY, END_MONTH, END_YEAR = None , 3, 2022

# If true, recordings will be grouped in folders by their owning user.
GROUP_BY_USER = True

# If true, recordings will be grouped in folders by their topics
GROUP_BY_TOPIC = True

# If true, each instance of recording will be in its own folder (which may contain multiple files).
GROUP_BY_RECORDING = False

# Set to true for more verbose output
VERBOSE_OUTPUT = False

# Constants used for indicating size in bytes.
KB = 1024
MB = 1024 * KB
GB = 1024 * MB
TB = 1024 * GB

# Chunk size in bytes, determines the rate at which progress is reported, you might want to change it depending
# on your internet speed.
CHUNK_SIZE = 1 * MB

# Minimum free disk space in bytes for downloads to happen, downloading will be stalled if disk space is
# expected to get below this amount as a result of the new file.
MINIMUM_FREE_DISK = 1 * GB

# Fetched at runtime. No Need to provide.
ACCESS_TOKEN = ""

colorama.init()

def refresh_token():
	data = {
		'grant_type': 'account_credentials',
		'account_id': ACCOUNT_ID
	}
	response = requests.post('https://api.zoom.us/oauth/token', auth=(CLIENT_ID, CLIENT_SECRET),  data=data).json()
	if 'access_token' not in response:
		raise Exception(f'Unable to fetch access token: {response["reason"]} - verify your credentials.')

	global ACCESS_TOKEN
	ACCESS_TOKEN = response['access_token']

def get_headers(token):
	return {
		'Authorization': f'Bearer {token}',
		'Content-Type': 'application/json'
	} 

def size_to_string(size_bytes):
   if size_bytes == 0:
       return '0', 'B'
   units = ('B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB')
   i = int(math.floor(math.log(size_bytes, 1024)))
   p = 1024**i
   size = round(size_bytes / p, 2)
   return str(size), units[i]

def main():
	from_date = datetime.datetime(START_YEAR , START_MONTH, START_DAY or 1)
	to_date = datetime.datetime(END_YEAR, END_MONTH, END_DAY or monthrange(END_YEAR, END_MONTH)[1])

	date_format = '%Y-%m-%d'
	from_date_string = from_date.strftime(date_format)
	to_date_string = to_date.strftime(date_format)

	file_count = 0
	total_size = 0
	skipped_count = 0

	if not USERIDS:
		users = get_users()
	else:
		users = [(id, '', '') for id in USERIDS]

	for user_id, user_email, user_name in users:
		user_description = get_user_description(user_id, user_email, user_name)
		user_host_folder = get_user_host_folder(user_id, user_email)

		print(Style.BRIGHT)
		print(f'Downloading videos from user {user_description} - Starting at {from_date_string} and up to (inclusive) {to_date_string}.')
		print(Style.RESET_ALL)

		url = f'https://api.zoom.us/v2/users/{user_id}/recordings?from={from_date_string}&to={to_date_string}&page_size=90000000'

		if VERBOSE_OUTPUT:
			print(f'{Style.DIM}Searching: {url}{Style.RESET_ALL}')

		data = get_with_token(lambda t: requests.get(url, headers=get_headers(t))).json()

		user_file_count, user_total_size, user_skipped_count = get_recordings(data, user_host_folder)

		print(f'{Style.BRIGHT}==============================================================={Style.RESET_ALL}')
		

	file_count += user_file_count
	total_size += user_total_size
	skipped_count += user_skipped_count

	total_size_str = ''.join(size_to_string(total_size))

	print()
	print(
		f'{Style.BRIGHT}Downloaded {Fore.GREEN}{file_count}{Fore.RESET} files.',
		f'Total size: {Fore.GREEN}{total_size_str}{Fore.RESET}.{Style.RESET_ALL}',
		f'Skipped: {skipped_count} files.'
	)

def get_user_description(user_id, user_email, user_name):
	part_1 = f'{user_email} ({user_name})' if (user_name) else user_email
	return f'{part_1} ID: {user_id}' if part_1 else f'ID: {user_id}'

def get_user_host_folder(user_id, user_email):
	if GROUP_BY_USER:
		folder_name = f'{user_email}__{user_id}' if user_email else user_id
		return os.path.join(PATH, folder_name)
	else:
		return PATH
	
def get_with_token(get):
	response = get(ACCESS_TOKEN)
	
	if response.status_code == 401:
		refresh_token()
		response = get(ACCESS_TOKEN)

	if not response.ok:
		raise Exception(f'{response.status_code} {response.text}')
	
	return response
	
def get_users():
	users_data = get_with_token(
		lambda t: requests.get(url='https://api.zoom.us/v2/users', headers=get_headers(t))
	).json()

	all_users = []

	page_count = int(users_data['page_count'])
	for page_number in range(1, page_count + 1):
		page = get_with_token(
			lambda t: requests.get(url=f'https://api.zoom.us/v2/users?page_number={page_number}', headers=get_headers(t))
		).json()

		all_users += [(user['id'], user['email'], get_user_name(user)) for user in page['users']]

	return all_users

def get_user_name(user_data):
	return f'({user_data.get("first_name") or ""} {user_data.get("last_name") or ""})'

def get_recordings(data, host_folder):
	total_size, file_count, skipped_count = 0, 0, 0

	if 'code' in data:
		raise Exception(f'{data["code"]} {data["message"]}')

	for meeting in data['meetings']:
		for record in meeting['recording_files']:
			if record['status'] != 'completed':
				continue

			topic_name = slugify(meeting['topic'])
			file_size = record['file_size']
			ext = slugify(record['file_extension'])
			record_name = slugify(f'{topic_name}__{record["recording_start"]}')
			file_name = slugify(f'{record_name}__{record["recording_type"]}')
			downloaded = download_recording(
				record['download_url'], 
				host_folder,
				f'{file_name}.{ext}',
				file_size,
				topic_name,
				record_name
			)

			if downloaded:
				total_size += file_size
				file_count += 1
			else:
				skipped_count += 1
	
	return file_count, total_size, skipped_count

def slugify(value, allow_unicode=True):
    """
    Taken from https://github.com/django/django/blob/master/django/utils/text.py
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '-', value).strip('-_')

def create_path(host_folder, file_name, topic_name, record_name):
	folder_path = host_folder

	if GROUP_BY_TOPIC:
		folder_path = os.path.join(folder_path, topic_name)
	if GROUP_BY_RECORDING:
		folder_path = os.path.join(folder_path, record_name)

	os.makedirs(folder_path, exist_ok=True)
	return os.path.join(folder_path, file_name)

def download_recording(download_url, host_folder, file_name, file_size, topic_name, meeting_name):
	if VERBOSE_OUTPUT:
		print(Style.BRIGHT + f'Found: {download_url}' + Style.RESET_ALL)

	file_path = create_path(host_folder, file_name, topic_name, meeting_name)

	if os.path.exists(file_path) and os.path.getsize(file_path) == file_size:
		print(f'{Style.DIM}Skipping existing file: {file_name}{Style.RESET_ALL}')
		return False

	print(f'{Style.BRIGHT}Downloading: {file_name}{Style.RESET_ALL}')

	wait_for_disk_space(file_size)

	response = get_with_token(
		lambda t: requests.get(f'{download_url}?access_token={t}', stream=True)
	)

	tmp_file_path = file_path + '.tmp'
	save_to_disk(response, tmp_file_path, file_size)
	os.rename(tmp_file_path, file_path)

	return True

def wait_for_disk_space(file_size):
	file_size_str = ''.join(size_to_string(file_size))

	free_disk = shutil.disk_usage(PATH)[2]
	free_disk_str = ''.join(size_to_string(free_disk))

	while free_disk < file_size + MINIMUM_FREE_DISK:
		print(f'{Fore.RED + Style.BRIGHT}Waiting for disk space... (File size: {file_size_str}, available: {free_disk_str}){Style.RESET_ALL}')
		sleep(30)
		free_disk = shutil.disk_usage(PATH)[2]
		free_disk_str = ''.join(size_to_string(free_disk))

def save_to_disk(response, file_path, file_size):
	file_size_str = ''.join(size_to_string(file_size))

	size, size_length = 0, 0

	print(Fore.CYAN, end='')

	with open(file_path, 'wb') as file:
		size_str1, size_str2 = size_to_string(size)
		print(f'\r{size_str1: <{size_length}}{size_str2} / {file_size_str}', end='\r')
		
		chunk: int
		for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
			size += len(chunk)
			if size >= file_size:
				print(Fore.GREEN, end='')

			size_str1, size_str2 = size_to_string(size)
			size_length = max(size_length, len(size_str1))
			print(f'\r{size_str1: <{size_length}}{size_str2} / {file_size_str}', end='\r')

			file.write(chunk)

	print(Style.RESET_ALL)
	   
if __name__ == '__main__':
	try:
		main()
	except Exception as error:
		print()
		print(f'{Fore.RED + Style.BRIGHT}Error: {error}{Style.RESET_ALL}')
		print()

	print()
	input('Press Enter to exit...')

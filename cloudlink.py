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

# Put your JWT token that you get from https://marketplace.zoom.us/ here. 
JWT = '##########'

# Put your USER ID that you get from the API. 
USERID = '##########'

# Put your own download path here, I used an external hard drive so mine will differ from yours
PATH = '/Volumes/Ext3/Zoom/'

# Date range (inclusive) for downloads, None value for Days gets replaced by first/last day of the month.
START_DAY, START_MONTH, START_YEAR = None, 5, 2020
END_DAY, END_MONTH, END_YEAR = None , 3, 2022

# If true, recordings will be grouped in folders by their topics
GROUP_BY_TOPIC = True

# If true, recordings will be grouped in folders by their meetings name
GROUP_BY_MEETING = False

# Set to true for more verbose output
VERBOSE_OUTPUT = False

# Chunk size in bytes, determines the rate at which progress is reported, you might want to change it depending
# on your internet speed.
CHUNK_SIZE = 1024**2

# Minimum free disk space in bytes for downloads to happen, downloading will be stalled if disk space is
# expected to get below this amount as a result of the new file.
MINIMUM_FREE_DISK = 1024**3

headers = {
		'Authorization': 
		'Bearer {}'.format(JWT),
		'content-type':
		'application/json',
	}

colorama.init()

def size_to_string(size_bytes):
   if size_bytes == 0:
       return "0", "B"
   units = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
   i = int(math.floor(math.log(size_bytes, 1024)))
   p = 1024**i
   size = round(size_bytes / p, 2)
   return str(size), units[i]

def main():
	from_date = datetime.datetime(START_YEAR , START_MONTH, START_DAY or 1)
	to_date = datetime.datetime(END_YEAR, END_MONTH, END_DAY or monthrange(END_YEAR, END_MONTH)[1])

	date_string = '%Y-%m-%d'
	url = 'https://api.zoom.us/v2/users/{}/recordings?from={}&to={}&page_size=90000000'.format(
				USERID,
				from_date.strftime(date_string),
				to_date.strftime(date_string)
			)

	if VERBOSE_OUTPUT:
		print(Style.DIM + "Searching: " + url + Style.RESET_ALL)

	response = requests.get(url, headers=headers)
	data = response.json()

	file_count, total_size, skipped_count = get_recordings(data)
	
	total_size_str = ''.join(size_to_string(total_size))

	print(Style.BRIGHT)
	print("Downloaded", Fore.GREEN + str(file_count) + Fore.RESET,
		  "files. Total size:", Fore.GREEN + total_size_str + Fore.RESET + ".",
		  Style.RESET_ALL + "Skipped:", str(skipped_count), "files.")

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


def get_recordings(data):
	total_size, file_count, skipped_count = 0, 0, 0

	if 'code' in data:
		raise Exception(f'{data["code"]} {data["message"]}')

	for meeting in data['meetings']:
		for record in meeting['recording_files']:
			if record['status'] != 'completed':
				continue

			topic_name = slugify(meeting["topic"])
			file_size = record["file_size"]
			ext = slugify(record["file_extension"])
			meeting_name = slugify(f'{topic_name}__{record["recording_start"]}')
			file_name = slugify(f'{meeting_name}__{record["recording_type"]}')
			downloaded = download_recording(
				record['download_url'], 
				f'{file_name}.{ext}',
				file_size,
				topic_name,
				meeting_name
			)

			if downloaded:
				total_size += file_size
				file_count += 1
			else:
				skipped_count += 1
	
	return file_count, total_size, skipped_count

def create_path(file_name, topic_name, meeting_name):
	folder_path = PATH

	if GROUP_BY_TOPIC:
		folder_path = os.path.join(folder_path, topic_name)
	if GROUP_BY_MEETING:
		folder_path = os.path.join(folder_path, meeting_name)

	os.makedirs(folder_path, exist_ok=True)
	return os.path.join(folder_path, file_name)

def check_disk_space(file_size):
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

	print(Fore.CYAN, end="")

	with open(file_path, 'wb') as file:
		size_str1, size_str2 = size_to_string(size)
		print(f'\r{size_str1: <{size_length}}{size_str2} / {file_size_str}', end="\r")
		
		chunk: int
		for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
			size += len(chunk)
			if size >= file_size:
				print(Fore.GREEN, end="")

			size_str1, size_str2 = size_to_string(size)
			size_length = max(size_length, len(size_str1))
			print(f'\r{size_str1: <{size_length}}{size_str2} / {file_size_str}', end="\r")

			file.write(chunk)

	print(Style.RESET_ALL)

def download_recording(download_url, file_name, file_size, topic_name, meeting_name):
	if VERBOSE_OUTPUT:
		print(Style.BRIGHT + f'Found: {download_url}' + Style.RESET_ALL)

	file_path = create_path(file_name, topic_name, meeting_name)

	if os.path.exists(file_path) and os.path.getsize(file_path) == file_size:
		print(f'{Style.DIM}Skipping existing file: {file_name}{Style.RESET_ALL}')
		return False

	print(f'{Style.BRIGHT}Downloading: {file_name}{Style.RESET_ALL}')

	check_disk_space(file_size)

	download_access_url = f'{download_url}?access_token={JWT}'
	response = requests.get(download_access_url, stream=True)

	tmp_file_path = file_path + '.tmp'
	save_to_disk(response, tmp_file_path, file_size)
	os.rename(tmp_file_path, file_path)

	return True

	   
if __name__ == '__main__':
	try:
		main()
	except Exception as error:
		print(Fore.RED + Style.BRIGHT)
		print("Error:", error, end="")
		print(Style.RESET_ALL)

	print()
	input("Press Enter to exit...")

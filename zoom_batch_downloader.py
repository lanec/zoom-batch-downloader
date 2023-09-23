import datetime
import math
import os
import re
import shutil
import unicodedata
import urllib
from calendar import monthrange
from json import dumps
from time import sleep

import colorama
import requests
from colorama import Fore, Style
from tqdm import tqdm

# Zoom API credentials
ACCOUNT_ID = '##########'
CLIENT_ID = '##########'
CLIENT_SECRET = '##########'

# Put here emails of the users you want to check for recordings. If empty, all users in the accounts will be checked.
USERS = [
	# '####@####.####'
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

# Minimum free disk space in bytes for downloads to happen, downloading will be stalled if disk space is
# expected to get below this amount as a result of the new file.
MINIMUM_FREE_DISK = 1 * GB

colorama.init()

def main():
	from_date = datetime.datetime(START_YEAR , START_MONTH, START_DAY or 1)
	to_date = datetime.datetime(END_YEAR, END_MONTH, END_DAY or monthrange(END_YEAR, END_MONTH)[1])

	date_format = '%Y-%m-%d'
	from_date_string = from_date.strftime(date_format)
	to_date_string = to_date.strftime(date_format)

	file_count = 0
	total_size = 0
	skipped_count = 0

	if not USERS:
		users = get_users()
	else:
		users = [(email, '') for email in USERS]

	for user_email, user_name in users:
		user_description = get_user_description(user_email, user_name)
		user_host_folder = get_user_host_folder(user_email)

		user_message = f'Downloading videos from user {user_description} - Starting at {from_date_string} and up to (inclusive) {to_date_string}.'
		print(Style.BRIGHT + user_message + Style.RESET_ALL)
		print()
	
		meetings = get_meetings(user_email, from_date_string, to_date_string)
		user_file_count, user_total_size, user_skipped_count = download_recordings(meetings, user_host_folder)

		print()
		print(f'{Style.BRIGHT}==============================================================={Style.RESET_ALL}')
		print()
		
		file_count += user_file_count
		total_size += user_total_size
		skipped_count += user_skipped_count

	total_size_str = size_to_string(total_size)

	print(
		f'{Style.BRIGHT}Downloaded {Fore.GREEN}{file_count}{Fore.RESET} files.',
		f'Total size: {Fore.GREEN}{total_size_str}{Fore.RESET}.{Style.RESET_ALL}',
		f'Skipped: {skipped_count} files.'
	)

def get_users():
	return paginate_reduce(
		'https://api.zoom.us/v2/users', [],
		lambda users, page: users + [(user['email'], get_user_name(user)) for user in page['users']]
	)

def get_user_description(user_email, user_name):
	return f'{user_email} ({user_name})' if (user_name) else user_email

def get_user_host_folder(user_email):
	if GROUP_BY_USER:
		return os.path.join(PATH, user_email)
	else:
		return PATH

def get_meetings(user_email, from_date_string, to_date_string):
	url = f'https://api.zoom.us/v2/users/{user_email}/recordings?from={from_date_string}&to={to_date_string}'
	
	return paginate_reduce(url, [], lambda meetings, page: meetings + page['meetings'])

def get_headers(token):
	return {
		'Authorization': f'Bearer {token}',
		'Content-Type': 'application/json'
	} 

def size_to_string(size_bytes):
   if size_bytes == 0:
       return '0B'
   units = ('B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB')
   i = int(math.floor(math.log(size_bytes, 1024)))
   p = 1024**i
   size = round(size_bytes / p, 2)
   return f'{size}{units[i]}'

def get_with_token(get):
	cached_token = getattr(get_with_token, 'token', '')
	response = get(cached_token)
	
	if response.status_code == 401:
		get_with_token.token = fetch_token()
		response = get(get_with_token.token)

	if not response.ok:
		raise Exception(f'{response.status_code} {response.text}')
	
	return response

def fetch_token():
	data = {
		'grant_type': 'account_credentials',
		'account_id': ACCOUNT_ID
	}
	response = requests.post('https://api.zoom.us/oauth/token', auth=(CLIENT_ID, CLIENT_SECRET),  data=data).json()
	if 'access_token' not in response:
		raise Exception(f'Unable to fetch access token: {response["reason"]} - verify your credentials.')

	return response['access_token']

def paginate_reduce(url, initial, reduce):
	initial_url = add_url_params(url, {'page_size': 1})
	page = get_with_token(
		lambda t: requests.get(url=initial_url, headers=get_headers(t))
	).json()

	result = initial

	while page:
		result = reduce(result, page)

		next_page_token = page['next_page_token']
		if next_page_token:
			next_url = add_url_params(url, {'page_token': next_page_token})
			page = get_with_token(lambda t: requests.get(next_url, headers=get_headers(t))).json()
		else:
			page = None

	return result

def add_url_params(url, params):
    """ Add GET params to provided URL being aware of existing.

    :param url: string of target URL
    :param params: dict containing requested params to be added
    :return: string with updated URL
    
    >> url = 'https://stackoverflow.com/test?answers=true'
    >> new_params = {'answers': False, 'data': ['some','values']}
    >> add_url_params(url, new_params)
    'https://stackoverflow.com/test?data=some&data=values&answers=false'
    """
    # Unquoting URL first so we don't lose existing args
    url = urllib.parse.unquote(url)
    # Extracting url info
    parsed_url = urllib.parse.urlparse(url)
    # Extracting URL arguments from parsed URL
    get_args = parsed_url.query
    # Converting URL arguments to dict
    parsed_get_args = dict(urllib.parse.parse_qsl(get_args))
    # Merging URL arguments dict with new params
    parsed_get_args.update(params)

    # Bool and Dict values should be converted to json-friendly values
    # you may throw this part away if you don't like it :)
    parsed_get_args.update(
        {k: dumps(v) for k, v in parsed_get_args.items()
         if isinstance(v, (bool, dict))}
    )

    # Converting URL argument to proper query string
    encoded_get_args = urllib.parse.urlencode(parsed_get_args, doseq=True)
    # Creating new parsed result object based on provided with new
    # URL arguments. Same thing happens inside urlparse.
    new_url = urllib.parse.ParseResult(
        parsed_url.scheme, parsed_url.netloc, parsed_url.path,
        parsed_url.params, encoded_get_args, parsed_url.fragment
    ).geturl()

    return new_url

def get_user_name(user_data):
	first_name = user_data.get("first_name")
	last_name = user_data.get("last_name")

	if first_name and last_name:
		return f'{first_name} {last_name}'
	else:
		return first_name or last_name

def download_recordings(meetings, host_folder):
	total_size, file_count, skipped_count = 0, 0, 0

	for meeting in meetings:
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
		print()
		print(Style.DIM + f'Found: {download_url}' + Style.RESET_ALL)

	file_path = create_path(host_folder, file_name, topic_name, meeting_name)

	if os.path.exists(file_path) and os.path.getsize(file_path) == file_size:
		print(f'{Style.DIM}Skipping existing file: {file_name}{Style.RESET_ALL}')
		return False
	elif os.path.exists(file_path):
		print(f'{Style.DIM}{Fore.RED}Deleting corrupt file: {file_name}{Style.RESET_ALL}')
		os.remove(file_path)

	print(f'{Style.BRIGHT}Downloading: {file_name}{Style.RESET_ALL}')

	wait_for_disk_space(file_size)

	tmp_file_path = file_path + '.tmp'
	do_with_token(lambda t: download(f'{download_url}?access_token={t}', tmp_file_path))
	
	os.rename(tmp_file_path, file_path)

	return True

def wait_for_disk_space(file_size):
	file_size_str = size_to_string(file_size)

	free_disk = shutil.disk_usage(PATH)[2]
	free_disk_str = size_to_string(free_disk)
	required_disk_space = file_size + MINIMUM_FREE_DISK

	while free_disk < file_size + MINIMUM_FREE_DISK:
		print(
			f'{Fore.RED + Style.BRIGHT}Waiting for disk space... '
			f'(File size: {file_size_str}, minimum free disk space: {size_to_string(MINIMUM_FREE_DISK)}, '
			f'available: {free_disk_str}/{size_to_string(required_disk_space)}){Style.RESET_ALL}'
		)
		sleep(15)
		free_disk = shutil.disk_usage(PATH)[2]
		free_disk_str = size_to_string(free_disk)

def do_with_token(do):
	def do_wrapper(token):
		test_response = requests.get('https://api.zoom.us/v2/users/me/recordings', headers=get_headers(token))
		if test_response.ok:
			do(token)

		return test_response
		
	get_with_token(lambda t: do_wrapper(t))

def download(url, output_path):
	class DownloadProgressBar(tqdm):
		def update_to(self, b=1, bsize=1, tsize=None):
			if tsize is not None:
				self.total = tsize
			self.update(b * bsize - self.n)

	with DownloadProgressBar(
		unit='B', unit_divisor=1024, unit_scale=True, miniters=1
	) as t:
		try:
			urllib.request.urlretrieve(url, filename=output_path, reporthook=t.update_to)
			size = os.path.getsize(output_path)
			t.update_to(bsize=size, tsize=size)
		except:
			try:
				os.remove(output_path)
			except OSError:
				pass
			
			raise
	   
if __name__ == '__main__':
	try:
		try:
			main()
		except Exception as error:
			print()
			print(f'{Fore.RED + Style.BRIGHT}Error: {error}{Style.RESET_ALL}')
			print()
		
		print()
		input('Press Enter to exit...')

	except KeyboardInterrupt:
		print()
		print(f'{Fore.RED + Style.BRIGHT}Interrupted by the user{Style.RESET_ALL}')
		exit(1)

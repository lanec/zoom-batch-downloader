import datetime
import os
import traceback
from calendar import monthrange

import colorama
import requests
from colorama import Fore, Style

import utils

colorama.init()

def main():
	CONFIG.OUTPUT_PATH = utils.prepend_path_on_windows(CONFIG.OUTPUT_PATH)

	print_filter_warning()

	from_date = datetime.datetime(CONFIG.START_YEAR, CONFIG.START_MONTH, CONFIG.START_DAY or 1)
	to_date = datetime.datetime(
		CONFIG.END_YEAR, CONFIG.END_MONTH, CONFIG.END_DAY or monthrange(CONFIG.END_YEAR, CONFIG.END_MONTH)[1],
	)

	file_count, total_size, skipped_count = download_recordings(get_users(), from_date, to_date)

	total_size_str = utils.size_to_string(total_size)

	print(
		f'{Style.BRIGHT}Downloaded {Fore.GREEN}{file_count}{Fore.RESET} files.',
		f'Total size: {Fore.GREEN}{total_size_str}{Fore.RESET}.{Style.RESET_ALL}',
		f'Skipped: {skipped_count} files.'
	)

def print_filter_warning():
	did_print = False

	if CONFIG.TOPICS:
		utils.print_bright(f'Topics filter is active {CONFIG.TOPICS}')
		did_print = True
	if CONFIG.USERS:
		utils.print_bright(f'Users filter is active {CONFIG.USERS}')
		did_print = True
	if CONFIG.RECORDING_FILE_TYPES:
		utils.print_bright(f'Recording file types filter is active {CONFIG.RECORDING_FILE_TYPES}')
		did_print = True
		
	if did_print:
		print()

def get_users():
	if CONFIG.USERS:
		return [(email, '') for email in CONFIG.USERS]

	return paginate_reduce(
		'https://api.zoom.us/v2/users?status=active', [],
		lambda users, page: users + [(user['email'], get_user_name(user)) for user in page['users']]
	) + paginate_reduce(
		'https://api.zoom.us/v2/users?status=inactive', [],
		lambda users, page: users + [(user['email'], get_user_name(user)) for user in page['users']]
	)

def paginate_reduce(url, initial, reduce):
	initial_url = utils.add_url_params(url, {'page_size': 300})
	page = get_with_token(
		lambda t: requests.get(url=initial_url, headers=get_headers(t))
	).json()

	result = initial
	while page:
		result = reduce(result, page)

		next_page_token = page['next_page_token']
		if next_page_token:
			next_url = utils.add_url_params(url, {'page_token': next_page_token})
			page = get_with_token(lambda t: requests.get(next_url, headers=get_headers(t))).json()
		else:
			page = None

	return result

def get_with_token(get):
	cached_token = getattr(get_with_token, 'token', '')

	if cached_token:
		response = get(cached_token)
	
	if not cached_token or response.status_code == 401:
		get_with_token.token = fetch_token()
		response = get(get_with_token.token)

	if not response.ok:
		raise Exception(f'{response.status_code} {response.text}')
	
	return response

def fetch_token():
	data = {
		'grant_type': 'account_credentials',
		'account_id': CONFIG.ACCOUNT_ID
	}
	response = requests.post('https://api.zoom.us/oauth/token', auth=(CONFIG.CLIENT_ID, CONFIG.CLIENT_SECRET),  data=data).json()
	if 'access_token' not in response:
		raise Exception(f'Unable to fetch access token: {response["reason"]} - verify your credentials.')

	return response['access_token']

def get_headers(token):
	return {
		'Authorization': f'Bearer {token}',
		'Content-Type': 'application/json'
	} 

def get_user_name(user_data):
	first_name = user_data.get("first_name")
	last_name = user_data.get("last_name")

	if first_name and last_name:
		return f'{first_name} {last_name}'
	else:
		return first_name or last_name
	
def download_recordings(users, from_date, to_date):
	file_count, total_size, skipped_count = 0, 0, 0

	for user_email, user_name in users:
		user_description = get_user_description(user_email, user_name)
		user_host_folder = get_user_host_folder(user_email)

		utils.print_bright(
			f'Downloading recordings from user {user_description} - Starting at {date_to_str(from_date)} '
			f'and up to {date_to_str(to_date)} (inclusive).'
		)
	
		meetings = get_meetings(user_email, from_date, to_date)
		user_file_count, user_total_size, user_skipped_count = download_recordings_from_meetings(meetings, user_host_folder)

		utils.print_bright('######################################################################')
		print()
		
		file_count += user_file_count
		total_size += user_total_size
		skipped_count += user_skipped_count
	
	return (file_count, total_size, skipped_count)

def get_user_description(user_email, user_name):
	return f'{user_email} ({user_name})' if (user_name) else user_email

def get_user_host_folder(user_email):
	if CONFIG.GROUP_BY_USER:
		return os.path.join(CONFIG.OUTPUT_PATH, user_email)
	else:
		return CONFIG.OUTPUT_PATH
	
def date_to_str(date):
	return date.strftime('%Y-%m-%d')

def get_meetings(user_email, start_date, end_date):
	meetings = []

	local_start_date = start_date
	delta = datetime.timedelta(days=29)
	while local_start_date <= end_date:
		local_end_date = min(local_start_date + delta, end_date)

		local_start_date_str = date_to_str(local_start_date)
		local_end_date_str = date_to_str(local_end_date)
		if CONFIG.VERBOSE_OUTPUT:
			utils.print_dim(f'Searching for recordings between {local_start_date_str} and {local_end_date_str}')

		url = f'https://api.zoom.us/v2/users/{user_email}/recordings?from={local_start_date_str}&to={local_end_date_str}'
		meetings += paginate_reduce(url, [], lambda meetings, page: meetings + page['meetings'])[::-1]

		local_start_date = local_end_date + datetime.timedelta(days=1)

	return meetings

def download_recordings_from_meetings(meetings, host_folder):
	file_count, total_size, skipped_count = 0, 0, 0

	for meeting in meetings:
		if CONFIG.TOPICS and meeting['topic'] not in CONFIG.TOPICS and utils.slugify(meeting['topic']) not in CONFIG.TOPICS:
			continue

		if 'recording_files' not in meeting:
			continue
		
		for recording_file in meeting['recording_files']:
			if 'file_size' not in recording_file:
				continue

			if CONFIG.RECORDING_FILE_TYPES and recording_file['file_type'] not in CONFIG.RECORDING_FILE_TYPES:
				continue

			url = recording_file['download_url']
			topic = utils.slugify(meeting['topic'])
			ext = utils.slugify(recording_file['file_extension'])
			recording_name = utils.slugify(f'{topic}__{recording_file["recording_start"]}')
			file_id = recording_file['id']
			file_name = utils.slugify(f'{recording_name}__{recording_file["recording_type"]}__{file_id[-8:]}') + '.' + ext
			file_size = int(recording_file.get('file_size'))

			if download_recording_file(url, host_folder, file_name, file_size, topic, recording_name):
				total_size += file_size
				file_count += 1
			else:
				skipped_count += 1
	
	return file_count, total_size, skipped_count

def download_recording_file(download_url, host_folder, file_name, file_size, topic, recording_name):
	if CONFIG.VERBOSE_OUTPUT:
		print()
		utils.print_dim(f'URL: {download_url}')

	file_path = create_path(host_folder, file_name, topic, recording_name)

	if os.path.exists(file_path) and abs(os.path.getsize(file_path) - file_size) <= CONFIG.FILE_SIZE_MISMATCH_TOLERANCE:
		utils.print_dim(f'Skipping existing file: {file_name}')
		return False
	elif os.path.exists(file_path):
		utils.print_dim_red(f'Deleting corrupt file: {file_name}')
		os.remove(file_path)

	utils.print_bright(f'Downloading: {file_name}')
	utils.wait_for_disk_space(file_size, CONFIG.OUTPUT_PATH, CONFIG.MINIMUM_FREE_DISK, interval=5)

	tmp_file_path = file_path + '.tmp'
	do_with_token(
		lambda t: utils.download_with_progress(
			f'{download_url}?access_token={t}', tmp_file_path, file_size, CONFIG.VERBOSE_OUTPUT,
			CONFIG.FILE_SIZE_MISMATCH_TOLERANCE
		)
	)
	
	os.rename(tmp_file_path, file_path)

	return True

def create_path(host_folder, file_name, topic, recording_name):
	folder_path = host_folder

	if CONFIG.GROUP_BY_TOPIC:
		folder_path = os.path.join(folder_path, topic)
	if CONFIG.GROUP_BY_RECORDING:
		folder_path = os.path.join(folder_path, recording_name)

	os.makedirs(folder_path, exist_ok=True)
	return os.path.join(folder_path, file_name)

def do_with_token(do):
	def do_as_get(token):
		test_url = 'https://api.zoom.us/v2/users/me/recordings'

		test_response = requests.get(test_url, headers=get_headers(token))
		if test_response.ok:
			try:
				do(token)
			except:
				test_response = requests.get(test_url, headers=get_headers(token))
				if test_response.ok:
					raise

		return test_response
		
	get_with_token(lambda t: do_as_get(t))

if __name__ == '__main__':
	try:
		import config as CONFIG
	except ImportError:
		utils.print_bright_red('Missing config file, copy config_template.py to config.py and change as needed.')

	try:
		main()
	except AttributeError as error:
		if error.obj.__name__ == 'config':
			print()
			utils.print_bright_red(
				f'Variable {error.name} is not defined in config.py. '
				f'See config_template.py for the complete list of variables.'
			)
		else:
			raise
	except Exception as error:
		print()
		if not getattr(CONFIG, "VERBOSE_OUTPUT"):
			utils.print_bright_red(f'Error: {error}')
		else:
			utils.print_dim_red(traceback.format_exc())

	except KeyboardInterrupt:
		print()
		utils.print_bright_red('Interrupted by the user')
		exit(1)
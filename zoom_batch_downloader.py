import datetime
import os
from calendar import monthrange

import colorama
import requests
from colorama import Fore, Style

import utils

colorama.init()

def main():
	if CONFIG.TOPICS:
		utils.print_bright(f'Topics filter is active {CONFIG.TOPICS}')
	if CONFIG.USERS:
		utils.print_bright(f'Users filter is active {CONFIG.USERS}')
	if CONFIG.TOPICS or CONFIG.USERS:
		print()

	from_date = get_date_str(CONFIG.START_DAY or 1, CONFIG.START_MONTH, CONFIG.START_YEAR)
	to_date = get_date_str(
		CONFIG.END_DAY or monthrange(CONFIG.END_YEAR, CONFIG.END_MONTH)[1], CONFIG.END_MONTH, CONFIG.END_YEAR
	)

	file_count, total_size, skipped_count = download_recordings(get_users(), from_date, to_date)

	total_size_str = utils.size_to_string(total_size)

	print(
		f'{Style.BRIGHT}Downloaded {Fore.GREEN}{file_count}{Fore.RESET} files.',
		f'Total size: {Fore.GREEN}{total_size_str}{Fore.RESET}.{Style.RESET_ALL}',
		f'Skipped: {skipped_count} files.'
	)

def get_date_str(day, month, year):
	return datetime.datetime(year, month, day).strftime('%Y-%m-%d')

def get_users():
	if CONFIG.USERS:
		return [(email, '') for email in CONFIG.USERS]

	return paginate_reduce(
		'https://api.zoom.us/v2/users', [],
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
	
def download_recordings(users, from_date_str, to_date_str):
	file_count, total_size, skipped_count = 0, 0, 0

	for user_email, user_name in users:
		user_description = get_user_description(user_email, user_name)
		user_host_folder = get_user_host_folder(user_email)

		utils.print_bright(
			f'Downloading videos from user {user_description} - Starting at {from_date_str} and up to (inclusive) {to_date_str}.'
		)
	
		meetings = get_meetings(user_email, from_date_str, to_date_str)
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

def get_meetings(user_email, from_date_str, to_date_str):
	url = f'https://api.zoom.us/v2/users/{user_email}/recordings?from={from_date_str}&to={to_date_str}'
	return paginate_reduce(url, [], lambda meetings, page: meetings + page['meetings'])

def download_recordings_from_meetings(meetings, host_folder):
	file_count, total_size, skipped_count = 0, 0, 0

	for meeting in meetings:
		if CONFIG.TOPICS and meeting['topic'] not in CONFIG.TOPICS and utils.slugify(meeting['topic']) not in CONFIG.TOPICS:
			continue

		for recording_file in meeting['recording_files']:
			if recording_file['status'] != 'completed':
				continue

			url = recording_file['download_url']
			topic = utils.slugify(meeting['topic'])
			ext = utils.slugify(recording_file['file_extension'])
			recording_name = utils.slugify(f'{topic}__{recording_file["recording_start"]}')
			file_name = utils.slugify(f'{recording_name}__{recording_file["recording_type"]}') + '.' + ext
			file_size = int(recording_file['file_size'])

			if download_recording_file(url, host_folder, file_name, file_size, topic, recording_name):
				total_size += file_size
				file_count += 1
			else:
				skipped_count += 1
	
	return file_count, total_size, skipped_count

def download_recording_file(download_url, host_folder, file_name, file_size, topic, recording_name):
	if CONFIG.VERBOSE_OUTPUT:
		print()
		utils.print_dim(f'Found: {download_url}')

	file_path = create_path(host_folder, file_name, topic, recording_name)

	if os.path.exists(file_path) and os.path.getsize(file_path) == file_size:
		utils.print_dim(f'Skipping existing file: {file_name}')
		return False
	elif os.path.exists(file_path):
		utils.print_dim(f'{Fore.RED}Deleting corrupt file: {file_name}{Fore.RESET}')
		os.remove(file_path)

	utils.print_bright(f'Downloading: {file_name}')
	utils.wait_for_disk_space(file_size, CONFIG.OUTPUT_PATH, CONFIG.MINIMUM_FREE_DISK, interval=5)

	tmp_file_path = file_path + '.tmp'
	do_with_token(
		lambda t: utils.download_with_progress(f'{download_url}?access_token={t}', tmp_file_path, file_size)
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
					f'Missing variable {error.name} from config.py. '
					f'See config_template.py for the complete list of variables.'
				)
			else:
				raise
		except Exception as error:
			print()
			utils.print_bright_red(f'Error: {error}')
		
		print()
		input('Press Enter to exit...')

	except KeyboardInterrupt:
		print()
		utils.print_bright_red('Interrupted by the user')
		exit(1)
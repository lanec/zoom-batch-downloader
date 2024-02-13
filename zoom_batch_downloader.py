import datetime
import math
import os
import traceback
from calendar import monthrange

import colorama
import requests
from colorama import Fore, Style
from hanging_threads import start_monitoring

import utils

colorama.init()

def main():
	if CONFIG.VERBOSE_OUTPUT:
		start_monitoring(seconds_frozen=20, test_interval=100)
		
	CONFIG.OUTPUT_PATH = utils.prepend_path_on_windows(CONFIG.OUTPUT_PATH)

	print_filter_warnings()

	if CONFIG.PARTIAL_MATCH_TOPICS:
		CONFIG.TOPICS = [topic.lower() for topic in CONFIG.TOPICS]

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

def print_filter_warnings():
	did_print = False

	if CONFIG.TOPICS:
		utils.print_bright(f'Topics filter is active {CONFIG.TOPICS}')
		did_print = True
	if CONFIG.USERS_INCLUDE:
		utils.print_bright(f'Users include filter is active {CONFIG.USERS_INCLUDE}')
		did_print = True
	if CONFIG.USERS_EXCLUDE:
		utils.print_bright(f'Users exclude filter is active {CONFIG.USERS_EXCLUDE}')
		did_print = True
	if CONFIG.RECORDING_FILE_TYPES:
		utils.print_bright(f'Recording file types filter is active {CONFIG.RECORDING_FILE_TYPES}')
		did_print = True
		
	if did_print:
		print()

def get_users():
	if CONFIG.USERS_INCLUDE:
		users = [(email, '') for email in CONFIG.USERS_INCLUDE]
	else:
		users = paginate_reduce(
			'https://api.zoom.us/v2/users?status=active', [],
			lambda users, page: users + [(user['email'], get_user_name(user)) for user in page['users']]
		) + paginate_reduce(
			'https://api.zoom.us/v2/users?status=inactive', [],
			lambda users, page: users + [(user['email'], get_user_name(user)) for user in page['users']]
		)
	
	if CONFIG.VERBOSE_OUTPUT:
		utils.print_dim('Found matching users:')
	
	for user_email, user_name in users:
		if user_email in CONFIG.USERS_EXCLUDE:
			users.pop(users.index((user_email, user_name)))
			continue

		if CONFIG.VERBOSE_OUTPUT:
			utils.print_dim(f'{user_name} <{user_email}>')

	return users

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
		host_folder = CONFIG.OUTPUT_PATH

		utils.print_bright(
			f'Downloading recordings from user {user_description} - Starting at {date_to_str(from_date)} '
			f'and up to {date_to_str(to_date)} (inclusive).'
		)
	
		meetings = get_meetings(get_meeting_uuids(user_email, from_date, to_date))
		user_file_count, user_total_size, user_skipped_count = download_recordings_from_meetings(meetings, host_folder, user_email)

		utils.print_bright('######################################################################')
		print()
		
		file_count += user_file_count
		total_size += user_total_size
		skipped_count += user_skipped_count
	
	return (file_count, total_size, skipped_count)

def get_user_description(user_email, user_name):
	return f'{user_email} ({user_name})' if (user_name) else user_email

def date_to_str(date):
	return date.strftime('%Y-%m-%d')

def get_meeting_uuids(user_email, start_date, end_date):
	meeting_uuids = []

	local_start_date = start_date
	delta = datetime.timedelta(days=29)
	
	utils.print_bright('Scanning for meetings:')
	estimated_iterations = math.ceil((end_date-start_date) / datetime.timedelta(days=30))
	with utils.percentage_tqdm(total=estimated_iterations) as progress_bar:
		while local_start_date <= end_date:
			local_end_date = min(local_start_date + delta, end_date)

			local_start_date_str = date_to_str(local_start_date)
			local_end_date_str = date_to_str(local_end_date)

			url = f'https://api.zoom.us/v2/users/{user_email}/recordings?from={local_start_date_str}&to={local_end_date_str}'
			meeting_uuids += paginate_reduce(
				url, [],
				lambda ids, page: ids + list(map(lambda meeting: meeting['uuid'], page['meetings']))
			)[::-1]

			local_start_date = local_end_date + datetime.timedelta(days=1)
			progress_bar.update(1)

	utils.print_dim(f"Meetings found: {len(meeting_uuids)}")

	return meeting_uuids

def get_meetings(meeting_uuids):
	meetings = []
	utils.print_bright(f'Scanning for recordings:')
	for meeting_uuid in utils.percentage_tqdm(meeting_uuids):
		url = f'https://api.zoom.us/v2/meetings/{utils.double_encode(meeting_uuid)}/recordings'
		meetings.append(get_with_token(lambda t: requests.get(url=url, headers=get_headers(t))).json())

	utils.print_dim(f"Recordings found: {len(meetings)}")

	return meetings

def download_recordings_from_meetings(meetings, host_folder, user_email):
	file_count, total_size, skipped_count = 0, 0, 0

	for meeting in meetings:
		if CONFIG.TOPICS and meeting['topic']:
			if CONFIG.PARTIAL_MATCH_TOPICS:
				topic_lower = str.lower(meeting['topic'])
				topic_lower_slug = utils.slugify(meeting['topic'])
				if not any(topic in topic_lower for topic in CONFIG.TOPICS) and not any(topic in topic_lower_slug for topic in CONFIG.TOPICS):
					continue
			else:
				if meeting['topic'] not in CONFIG.TOPICS and utils.slugify(meeting['topic']) not in CONFIG.TOPICS:
					continue
		
		recording_files = meeting.get('recording_files') or []
		participant_audio_files = meeting.get('participant_audio_files') or [] if CONFIG.INCLUDE_PARTICIPANT_AUDIO else []

		for recording_file in recording_files + participant_audio_files:
			if 'file_size' not in recording_file:
				continue

			if CONFIG.RECORDING_FILE_TYPES and recording_file['file_type'] not in CONFIG.RECORDING_FILE_TYPES:
				continue

			url = recording_file['download_url']
			topic = utils.slugify(meeting['topic'])
			recording_name = utils.slugify(f'{topic}')

			file_name = build_file_name(recording_file, topic)
			file_size = int(recording_file.get('file_size'))

			if download_recording_file(url, host_folder, file_name, file_size, topic, recording_name, recording_file["recording_start"], user_email):
				total_size += file_size
				file_count += 1
			else:
				skipped_count += 1
	
	return file_count, total_size, skipped_count

def build_file_name(recording_file, topic):
	recording_name = utils.slugify(f'{topic}')
	recording_start = utils.slugify(f'{recording_file["recording_start"]}')
	file_id = recording_file['id'][-8:]
	file_name_suffix =  os.path.splitext(recording_file['file_name'])[0] + '__' if 'file_name' in recording_file else ''
	recording_type_suffix = ''

	recording_type_suffix =  recording_file["recording_type"] if 'recording_type' in recording_file else ''
	file_extension = recording_file.get('file_extension') or os.path.splitext(recording_file['file_name'])[1]
	
	file_name_pieces = []
	for format in CONFIG.FILE_NAME_FORMAT:
		if format == "RECORDING_START_DATETIME":
			file_name_pieces.append(f'{recording_start}')
		if format == "RECORDING_NAME":
			file_name_pieces.append(f'{recording_name}{file_name_suffix}')
		if format == "RECORDING_TYPE":
			file_name_pieces.append(f'{recording_type_suffix}')
		if format == "FILE_ID":
			file_name_pieces.append(f'{file_id}')

	file_name = utils.slugify(f'{CONFIG.FILE_NAME_SEPERATOR}'.join(file_name_pieces)) + '.' + file_extension

	return file_name

def download_recording_file(download_url, host_folder, file_name, file_size, topic, recording_name, recording_start, user_email):
	folder_path = create_folder_path(host_folder, topic, recording_name, recording_start, user_email)
	file_path = os.path.join(folder_path, file_name)

	if CONFIG.VERBOSE_OUTPUT:
		print()
		utils.print_dim(f'URL: {download_url}')
		utils.print_dim(f'Folder: {folder_path}')

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

def create_folder_path(host_folder, topic, recording_name, recording_start, user_email):
	folder_path = host_folder

	for group_by in CONFIG.GROUP_FOLDERS_BY:
		if group_by == "YEAR_MONTH":
			recording_start_date = datetime.datetime.strptime(recording_start, '%Y-%m-%dT%H:%M:%SZ')
			year_month = recording_start_date.strftime('%Y-%m')
			folder_path = os.path.join(folder_path, year_month)
		if group_by == "USER_EMAIL":
			folder_path = os.path.join(folder_path, user_email)
		if group_by == "TOPIC":
			folder_path = os.path.join(folder_path, topic)
		
	if CONFIG.GROUP_BY_RECORDING:
		folder_path = os.path.join(folder_path, recording_name)

	os.makedirs(folder_path, exist_ok=True)

	return folder_path

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
		elif utils.is_debug():
			raise
		else:
			utils.print_dim_red(traceback.format_exc())

	except KeyboardInterrupt:
		print()
		utils.print_bright_red('Interrupted by the user')
		exit(1)
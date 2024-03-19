import datetime
import math
import os
import traceback
import glob
import shutil
import time
import subprocess
import json
from calendar import monthrange

import colorama
import requests
from colorama import Fore, Style

import utils

colorama.init()

def delete_files_in_folder(folder_path):
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f'Failed to delete {file_path}. Reason: {e}')

def main():
    CONFIG.OUTPUT_PATH = utils.prepend_path_on_windows(CONFIG.OUTPUT_PATH)

    # Delete files in the output folder if DELETE_FILES_BEFORE_DOWNLOAD is True
    if CONFIG.DELETE_FILES_BEFORE_DOWNLOAD:
        delete_files_in_folder(CONFIG.OUTPUT_PATH)

    print_filter_warnings()

    # Prompt the user to enter the date
    year = int(input("Enter the year: "))
    month = int(input("Enter the month: "))
    day = int(input("Enter the day: "))

    from_date = datetime.datetime(year, month, day)
    to_date = from_date + datetime.timedelta(days=0)

    # Check if the from_date is Friday
    if from_date.weekday() == 4:  # 0 is Monday, so 4 is Friday
        to_date += datetime.timedelta(days=2)  # Add two days if from_date is Friday

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
	if CONFIG.USERS:
		utils.print_bright(f'Users filter is active {CONFIG.USERS}')
		did_print = True
	if CONFIG.RECORDING_FILE_TYPES:
		utils.print_bright(f'Recording file types filter is active {CONFIG.RECORDING_FILE_TYPES}')
		did_print = True
		
	if did_print:
		print()

def get_users():
    all_users = paginate_reduce(
        'https://api.zoom.us/v2/users?status=active', [],
        lambda users, page: users + [user for user in page['users']]
    ) + paginate_reduce(
        'https://api.zoom.us/v2/users?status=inactive', [],
        lambda users, page: users + [user for user in page['users']]
    )

    if CONFIG.CHECK_ONLY_LICENSED:
        # Filter for licensed users
        users = [(user['email'], get_user_name(user)) for user in all_users if user['type'] == 2]
    else:
        users = [(user['email'], get_user_name(user)) for user in all_users]

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
		user_host_folder = get_user_host_folder(user_email)

		utils.print_bright(
			f'Downloading recordings from user {user_description} - Starting at {date_to_str(from_date)} '
			f'and up to {date_to_str(to_date)} (inclusive).'
		)
	
		meetings = get_meetings(get_meeting_uuids(user_email, from_date, to_date))
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

	return meeting_uuids

def get_meetings(meeting_uuids):
	meetings = []
	utils.print_bright(f'Scanning for recordings:')
	for meeting_uuid in utils.percentage_tqdm(meeting_uuids):
		url = f'https://api.zoom.us/v2/meetings/{utils.double_encode(meeting_uuid)}/recordings'
		meetings.append(get_with_token(lambda t: requests.get(url=url, headers=get_headers(t))).json())

	return meetings

def download_recordings_from_meetings(meetings, host_folder):
    file_count, total_size, skipped_count = 0, 0, 0

    for meeting in meetings:
        if CONFIG.TOPICS and meeting['topic'] not in CONFIG.TOPICS and utils.slugify(meeting['topic']) not in CONFIG.TOPICS:
            continue
        
        recording_files = meeting.get('recording_files') or []
        participant_audio_files = meeting.get('participant_audio_files') or [] if CONFIG.INCLUDE_PARTICIPANT_AUDIO else []

        for recording_file in recording_files + participant_audio_files:
            if 'file_size' not in recording_file:
                continue

            if CONFIG.RECORDING_FILE_TYPES and recording_file['file_type'] not in CONFIG.RECORDING_FILE_TYPES:
                continue

            url = recording_file['download_url']
            topic = utils.slugify(meeting['topic']).replace('-', ' ')  # This line was modified
            ext = recording_file.get('file_extension') or os.path.splitext(recording_file['file_name'])[1]
            file_name = f'{topic}.{ext}'
            file_size = int(recording_file.get('file_size'))

            if download_recording_file(url, host_folder, file_name, file_size, topic):
                total_size += file_size
                file_count += 1
            else:
                skipped_count += 1
    
    return file_count, total_size, skipped_count



def download_recording_file(download_url, host_folder, file_name, file_size, topic):
    # Skip download if file size is less than MIN_FILE_SIZE
    if file_size < CONFIG.MIN_FILE_SIZE * 1024 * 1024:  # Convert MIN_FILE_SIZE from MB to bytes
        print(f'Skipping: {file_name} (size is less than {CONFIG.MIN_FILE_SIZE} MB)')
        return False

    if CONFIG.VERBOSE_OUTPUT:
        print()
        utils.print_dim(f'URL: {download_url}')

    file_path = create_path(host_folder, file_name, topic)

    # Check if file already exists
    if os.path.exists(file_path):
        base_name, ext = os.path.splitext(file_path)
        i = 1
        # If file exists, create a new file name with suffix
        while os.path.exists(file_path):
            file_path = base_name + "_" + str(i) + ext
            i += 1

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




def create_path(host_folder, file_name, topic):
    folder_path = host_folder

    if CONFIG.GROUP_BY_TOPIC:
        folder_path = os.path.join(folder_path, topic)

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

def process_videos():
    # Initialize total time spent
    total_time_spent = 0

    # Use OUTPUT_PATH from config as the input and output folder
    input_output_folder = CONFIG.OUTPUT_PATH

    print(f"Processing videos in {input_output_folder}...")
    for filename in os.listdir(input_output_folder):
        if filename.lower().endswith((".mp4", ".avi", ".mkv", ".flv", ".mov")):  # Add or remove video formats as needed
            print(f"Processing {filename}...")
            input_file = os.path.join(input_output_folder, filename)
            output_file = os.path.join(input_output_folder, os.path.splitext(filename)[0] + "-proj.llc")
            log_file = os.path.join(input_output_folder, os.path.splitext(filename)[0] + ".txt")

            command = f'ffmpeg -hide_banner -vn -i "{input_file}" -af silencedetect=noise=-40dB:d=7 -f null - 2>&1'
            
            # Start the timer
            start_time = time.time()
            output = subprocess.check_output(command, shell=True).decode("utf-8")
            # End the timer
            end_time = time.time()
            
            # Calculate the time spent
            time_spent = end_time - start_time
            total_time_spent += time_spent  # Add the time spent on this video to the total
            print(f"Time spent on silent audio detection: {time_spent} seconds")

            with open(log_file, "w", encoding="utf-8") as f:
                f.write(output)

            cut_segments = []
            start = None
            end = None
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if "[silencedetect @" in line:
                        if "silence_start" in line:
                            start = float(line.split(":")[1].strip())
                        elif "silence_end" in line:
                            end = float(line.split(":")[1].split("|")[0].strip())
                            if start is not None and end is not None and end > start:
                                cut_segments.append({"start": start, "end": end, "name": ""})
                                start = None
                                end = None

            llc_data = {
                "version": 1,
                "mediaFileName": filename,
                "cutSegments": cut_segments
            }

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(llc_data, f, indent=2, ensure_ascii=False)

            # Delete the temporary log file
            os.remove(log_file)
            print(f"Finished processing {filename}.")
    print(f"Finished processing videos in {input_output_folder}.")

    # Print the total time spent on processing videos
    print(f"Total time spent on processing videos: {total_time_spent} seconds")


if __name__ == '__main__':
    try:
        import config as CONFIG
    except ImportError:
        utils.print_bright_red('Missing config file, copy config_template.py to config.py and change as needed.')

    try:
        main()

        # Call the process_videos function if GENERATE_LLC_FILES is True
        if CONFIG.GENERATE_LLC_FILES:
            process_videos()

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

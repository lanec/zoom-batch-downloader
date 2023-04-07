import requests 
import datetime

# Put your JWT token that you get from https://marketplace.zoom.us/ here. 
JWT = '[REDACTED]'

# Put your USER ID that you get from the API. 
USERID = '[REDACTED]'


headers = {
		'Authorization': 
		'Bearer {}'.format(JWT),
		'content-type':
		'application/json',
	}

# Put your own download path here, I used an external hard drive so mine will differ from yours
PATH = '/Volumes/MAC BETA/zoom_recordings/'



def main():
	for year in range(2022,2023):
		for month in range(1,13):
			next_month = month + 1
			next_year = year

			if month == 12:
				next_month = 1
				next_year = year + 1
    		# b/c we already have the recordings for the first 2 months of 2022
			if next_year == 2022 and next_month < 3:
				next_month = 3
   
			start_date = datetime.datetime(year,month,1)
			next_date = datetime.datetime(next_year,next_month,1)

			get_recording(start_date, next_date)


def get_recording(start_date, next_date):
	
	date_string = '%Y-%m-%d'
	url = 'https://api.zoom.us/v2/users/{}/recordings?from={}&to={}&page_size=300&'.format(
				USERID,
				start_date.strftime(date_string),
				next_date.strftime(date_string)
			)

	print(url)

	response = requests.get(
		url,
		headers=headers
	)

	data = response.json()
	print('page_count: ', data['page_count'])
	print('page_size: ', data['page_size'])
	print(len(data['meetings']))
	print(data['from'])
	print(data['to'])

	for meeting in data['meetings']:
		for record in meeting['recording_files']:
			if record['status'] != 'completed':
				continue

			download_recording(
				record['download_url'], 
				record['recording_start'].replace(':','-')
			)


def download_recording(download_url, filename):
	print(download_url)
	download_access_url = '{}?access_token={}'.format(download_url, JWT)
	print(download_access_url)
	local_filename = '{}{}.mp4'.format(PATH, filename)
	print (local_filename)
 	# r = requests.get(download_access_url, allow_redirects=True)
 	# open(local_filename, 'wb').write(r.content)
	response = requests.get(download_access_url, stream=True)


	with open(local_filename, 'wb') as f:
		for chunk in response.iter_content(chunk_size=8192):
			# print (len(chunk))
			f.write(chunk)

	   
if __name__ == '__main__':
	main()





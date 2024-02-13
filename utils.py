import math
import os
import re
import shutil
import sys
import unicodedata
import urllib
from json import dumps
from time import sleep

from colorama import Fore, Style
from tqdm import tqdm

def prepend_path_on_windows(path):
	if os.name != 'nt':
		return path
	
	path = os.path.abspath(path)

	if path.startswith(u"\\\\?\\"):
		return path

	if path.startswith(u"\\\\"):
		path=u"\\\\?\\UNC\\" + path[2:]
	else:
		path=u"\\\\?\\" + path

	return path

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

def double_encode(str):
	return urllib.parse.quote(urllib.parse.quote(str, safe=''))

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

def wait_for_disk_space(file_size, path, minimum_free_disk, interval):
	file_size_str = size_to_string(file_size)

	free_disk = shutil.disk_usage(path)[2]
	required_disk_space = file_size + minimum_free_disk
	required_disk_space_str = size_to_string(required_disk_space)

	i = 0
	while free_disk < required_disk_space:
		if i % 3 == 0:
			free_disk_str = size_to_string(free_disk)
			minimum_free_disk_str = size_to_string(minimum_free_disk)

			print_bright_red(
				f'Waiting for disk space... '
				f'(File size: {file_size_str}, minimum free disk space: {minimum_free_disk_str}, '
				f'available: {free_disk_str}/{required_disk_space_str})'
			)
		sleep(interval)
		free_disk = shutil.disk_usage(path)[2]
		i += 1

def size_to_string(size_bytes, separator = ''):
	if size_bytes == 0:
		return '0B'
	units = ('B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB')
	i = int(math.floor(math.log(size_bytes, 1024)))
	p = 1024**i
	size = round(size_bytes / p, 2)
	return str(size) + str(separator) + units[i]

def print_bright_red(msg):
	print_bright(Fore.RED + str(msg) + Fore.RESET)

def print_bright(msg):
	print(Style.BRIGHT + str(msg) + Style.RESET_ALL)

def print_dim_red(msg):
	print_dim(Fore.RED + str(msg) + Fore.RESET)	

def print_dim(msg):
	print(Style.DIM + str(msg) + Style.RESET_ALL)

def download_with_progress(url, output_path, expected_size, verbose_output, size_tolerance):
	class DownloadProgressBar(tqdm):
		def update_to(self, b=1, bsize=1, tsize=None):
			if tsize is not None:
				self.total = tsize
			self.update(b * bsize - self.n)
			

	r_bar = '| {n_fmt}{unit}/{total_fmt}{unit} [{elapsed}<{remaining}, {rate_fmt}{postfix}]'
	format = '{l_bar}{bar}' + r_bar

	with DownloadProgressBar(
		unit='B', unit_divisor=1024, unit_scale=True, miniters=1, dynamic_ncols=True, bar_format=format
	) as t:
		try:
			urllib.request.urlretrieve(url, filename=output_path, reporthook=t.update_to)
			file_size = os.path.getsize(output_path)
			if abs(file_size - expected_size) > size_tolerance:
				t.update_to(bsize=0, tsize=expected_size)
				if verbose_output:
					print_dim_red(
						f'Size mismatch: Expected {expected_size} bytes but got {file_size}. '
			   			f'Size difference: {size_to_string(abs(file_size - expected_size))}.\n'
						f'You might want to increase FILE_SIZE_MISMATCH_TOLERANCE in config.py'
					)
				raise Exception(f'Failed to download file at {url}.{"" if verbose_output else " Enable verbose output for more details."}')
			
			t.update_to(bsize=file_size, tsize=file_size)
			t.close()

			if file_size != expected_size and verbose_output:
				print_dim_red(
					f'Size mismatch within tolerance: Expected {expected_size} bytes but got {file_size}. '
					f'Size difference: {size_to_string(abs(file_size - expected_size))}.'
				)
		except:
			try:
				os.remove(output_path)
			except OSError:
				pass
			
			raise

def is_debug() -> bool:
    """Return if the debugger is currently active"""
    return hasattr(sys, 'gettrace') and sys.gettrace() is not None

class percentage_tqdm(tqdm):
	def __init__(self, iterable=None, total=None, fill_on_close=False):
		tqdm.__init__(
			self, iterable=iterable, total=total, bar_format='{l_bar}{bar}| [{elapsed}<{remaining}]', dynamic_ncols=True
		)
		self.fill_on_close = fill_on_close

	def close(self):
		if self.fill_on_close:
			self.total = self.n
		tqdm.close(self)
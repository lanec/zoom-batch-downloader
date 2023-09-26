# Zoom API credentials
ACCOUNT_ID = '##########'
CLIENT_ID = '##########'
CLIENT_SECRET = '##########'

# Put here emails of the users you want to check for recordings. If empty, all users under the account will be checked.
USERS = [
	# '####@####.####'
]

# Put here the topics of the meetings you wish to download recordings for. If empty, no topic filtering will happen.
TOPICS = [
    # '############'
]

# Put your own download path here, I used an external hard drive so mine will differ from yours
OUTPUT_PATH = '/Volumes/Ext3/Zoom/'

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

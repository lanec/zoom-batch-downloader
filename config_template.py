# Zoom API credentials.
ACCOUNT_ID = R"##########"
CLIENT_ID = R"##########"
CLIENT_SECRET = R"##########"

# Put your own download path here, no need to escape backslashes but avoid ending with one.
OUTPUT_PATH = R"C:\Test\Zoom"

# Date range (inclusive) for downloads, None value for Days gets replaced by first/last day of the month.
START_DAY, START_MONTH, START_YEAR = None, 5, 2020
END_DAY, END_MONTH, END_YEAR = None , 3, 2022

# Put here emails of the users you want to check for recordings. If empty, all users under the account will be checked.
USERS = [
	# R"####@####.####",
    # R"####@####.####",
]

# Put here the topics of the meetings you wish to download recordings for. If empty, no topic filtering will happen.
TOPICS = [
    # R"############",
    # R"############",
]

# Put here the file types you wish to download. If empty, no file type filtering will happen.
RECORDING_FILE_TYPES = [
    # R"MP4",            # Video file of the recording.
    # R"M4A",            # Audio-only file of the recording.
    # R"TRANSCRIPT",     # Transcription file of the recording in VTT format.
    # R"CHAT",           # A TXT file containing in-meeting chat messages that were sent during the meeting.
    # R"CSV",            # File containing polling data in CSV format.
    # R"SUMMARY",        # Summary file of the recording in JSON file format.
]

# If True, will include recordings in the trash, you weirdo.
INCLUDE_TRASH = False

# If True, recordings will be grouped in folders by their owning user.
GROUP_BY_USER = True

# If True, recordings will be grouped in folders by their topics
GROUP_BY_TOPIC = True

# If True, each instance of recording will be in its own folder (which may contain multiple files).
# Note: One "meeting" can have multiple recording instances.
GROUP_BY_RECORDING = False

# Set to True for more verbose output
VERBOSE_OUTPUT = False

# Constants used for indicating size in bytes.
B = 1
KB = 1024 * B
MB = 1024 * KB
GB = 1024 * MB
TB = 1024 * GB

# Minimum free disk space in bytes for downloads to happen, downloading will be stalled if disk space is
# expected to get below this amount as a result of the new file.
MINIMUM_FREE_DISK = 1 * GB

# Tolerance for recording files size mismatch between the declared size in Zoom Servers and the files actually downloaded
# from the server. It seems like sometimes they don't match perfectly.
# High tolerance might cause issues like corrupt downloads not being recognized by script.
FILE_SIZE_MISMATCH_TOLERANCE = 0 * MB

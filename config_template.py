# Zoom API credentials.
ACCOUNT_ID = R"##########"
CLIENT_ID = R"##########"
CLIENT_SECRET = R"##########"

# Put your own download path here, no need to escape backslashes but avoid ending with one.
OUTPUT_PATH = R"C:\Test\Zoom"

# Date range (inclusive) for downloads, None value for Days gets replaced by first/last day of the month.
START_DAY, START_MONTH, START_YEAR = None, 5, 2020
END_DAY,   END_MONTH,   END_YEAR   = None, 3, 2022

# Put here emails of the users you want to check for recordings. If empty, all users under the account will be checked.
USERS_INCLUDE = [
    # R"####@####.####",
    # R"####@####.####",
]

# Put here emails of the users you want to exclude from checking for recordings. Optional.
USERS_EXCLUDE = [
    # R"####@####.####",
    # R"####@####.####",
]

# Put here the topics of the meetings you wish to download recordings for. If empty, no topic filtering will happen.
TOPICS = [
    # R"############",
    # R"############",
]

# If True, topics that partially match your topic filters are downloaded. If False, only meetings with exact topic matches are downloaded.
PARTIAL_MATCH_TOPICS = False

# Put here the file types you wish to download. If empty, no file type filtering will happen.
RECORDING_FILE_TYPES = [
    # R"MP4",            # Video file of the recording.
    # R"M4A",            # Audio-only file of the recording.
    # R"TRANSCRIPT",     # Transcription file of the recording in VTT format.
    # R"CHAT",           # A TXT file containing in-meeting chat messages that were sent during the meeting.
    # R"CSV",            # File containing polling data in CSV format.
    # R"SUMMARY",        # Summary file of the recording in JSON file format.
]

# Group records in a folder hierarchy using the order below.
# Reorder or comment out any of the folder groups below to control the folder hierarchy created to orgainze the downloaded recording files.
GROUP_FOLDERS_BY = [
    # R"YEAR_MONTH",     # Recordings will be grouped in folders by their recording start date in yyyy-mm format.
     R"USER_EMAIL",     # Recordings will be grouped in folders by their owning user's email address.
     R"TOPIC",          # Recordings will be grouped in folders by their topics.
]

# If True, each instance of recording will be in its own folder (which may contain multiple files).
# Note: One "meeting" can have multiple recording instances.
GROUP_BY_RECORDING = False

# If True, participant audio files will be downloaded as well.
# This works when "Record a separate audio file of each participant" is enabled.
INCLUDE_PARTICIPANT_AUDIO = True

# Recording file name format to use when saving files. Reorder or comment out any file name format pieces below to control the file naming pattern.
# Example: 2023-12-25t143021z__name-of-the-meeting__audio_transcript__ff625374.VTT
FILE_NAME_FORMAT = [
     R"RECORDING_START_DATETIME",   # Recording start datetime
     R"RECORDING_NAME",             # Recording name
     R"RECORDING_TYPE",             # Recoding type
     R"FILE_ID",                    # Recording unique file ID
]

# Seperator character(s) to place in between the file name format pieces when building the recording file names.
FILE_NAME_SEPERATOR = "__"

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

# Tolerance for recording files size mismatch between the declared size in Zoom Servers and the files 
# actually downloaded the server.
# This was observed to happen sometimes on google drive mounted storage (mismatches of < 300 KBs)
# Note: High tolerance might cause issues like corrupt downloads not being recognized by script.
FILE_SIZE_MISMATCH_TOLERANCE = 0 * KB

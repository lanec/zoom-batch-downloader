# zoom-batch-downloader

Download all your zoom cloud recordings

This script requires [server-to-server](https://developers.zoom.us/docs/internal-apps/) credentials from the [Zoom marketplace](https://marketplace.zoom.us/user/build)

Required Scopes:
- `recording:read:admin` to download the recordings.
- `user:read:admin` if you want the script to iterate over all users in the account (default behavior).
  
Instructions:

1. Create a server-to-server app as specified above and activate it (no need to publish).

1. Edit zoom_batch_downloader.py to include your credentials and the correct path for your downloads.

1. Install the requirements listed in requirements.txt using [pip](https://pip.pypa.io/en/stable/reference/requirement-specifiers/)

1. Run zoom_batch_downloader.py.

```
pip install -r requirements.txt
python zoom_batch_downloader.py
```

Code written by Georg Kasmin, Lane Campbell and Aness Zurba

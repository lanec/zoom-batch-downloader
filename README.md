# zoom-batch-downloader

Download all your Zoom cloud recordings for accounts with [paid plans](https://zoom.us/pricing#personal).

This script requires [server-to-server app](https://developers.zoom.us/docs/internal-apps/create/) credentials from the [Zoom marketplace](https://marketplace.zoom.us/user/build)

Required Scopes for your server-to-server zoom app:
- `recording:read:admin` to download the recordings.
- `user:read:admin` if you want the script to iterate over all users in the account (default behavior).
  
## Instructions:

1. Create a server-to-server app as specified above and activate it (no need to publish).

1. Clone/[Download](https://github.com/lanec/zoom-batch-downloader/archive/refs/heads/master.zip) this repository.

1. Copy `config_template.py` to a new file called `config.py` in the same directory and edit it to include your credentials and the target path for your recording downloads.

1. Go over `config.py` to see if you wish to change any other settings (optional).

1. Install [Python 3](https://wiki.python.org/moin/BeginnersGuide/Download).

1. Install the requirements listed in `requirements.txt` using [pip](https://pip.pypa.io/en/stable/reference/requirement-specifiers/).

    ```bash
    python -m pip install -r requirements.txt
    ```

1. Run `zoom_batch_downloader.py`.

    ```bash
    python zoom_batch_downloader.py
    ```

Code written by Georg Kasmin, Lane Campbell and Aness Zurba.

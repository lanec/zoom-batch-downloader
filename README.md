# zoom-batch-downloader

Download all your zoom cloud recordings

This script requires [server-to-server](https://developers.zoom.us/docs/internal-apps/) credentials from the [Zoom marketplace](https://marketplace.zoom.us/user/build)

1. Edit zoom_batch_downloader.py to include your credentials and the correct path for your downloads.

2. Install the requirements listed in requirements.txt using [pip](https://pip.pypa.io/en/stable/reference/requirement-specifiers/)

3. Run zoom_batch_downloader.py to download the recording to the path you specified.

```
pip install -r requirements.txt
python zoom_batch_downloader.py
```

Code written by Georg Kasmin, Lane Campbell and Aness Zurba

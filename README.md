# zoom-batch-downloader
Download all your zoom cloud recordings

Edit zoom_batch_downloader.py to include your credentials and the correct path for your downloads.

This requires [server-to-server](https://developers.zoom.us/docs/internal-apps/) credentials from the [Zoom marketplace](https://marketplace.zoom.us/user/build)

Install the requirements listed in requirements.txt 

If you haven't done that before you will need to use [pip](https://pip.pypa.io/en/stable/reference/requirement-specifiers/)

```python
pip install -r requirements.txt
python zoom_batch_downloader.py
```

That will download all the recordings wherever you specify. 

Code written by Georg Kasmin, Lane Campbell and Aness Zurba

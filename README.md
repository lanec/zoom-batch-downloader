# zoom-batch-downloader
Download all your zoom cloud recordings

Edit cloudlink.py to include your JWT token, the correct path for your downloads, and the USER ID from Zoom's API. 

Here is where you can find instructions on listing a USER ID - https://marketplace.zoom.us/docs/api-reference/zoom-api/users/users

Install the requirements listed in requirements.txt 

If you haven't done that before you will need to use PIP (https://pip.readthedocs.io/en/1.1/requirements.html)

Exact command is "pip install -r requirements.txt"

Then run "python cloudlink.py"

That will download all the recordings wherever you specify. 

Code written by Georg Kasmin and Lane Campbell

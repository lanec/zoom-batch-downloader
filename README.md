# WARNING #
This script was authored to use the JWT API that is now being depreciated and/or is already depreciated depending on if you have a legacy app to use - I am posting this in August 2023 - consider it no longer functional

# zoom-batch-downloader
Download all your zoom cloud recordings

Edit cloudlink.py to include your JWT token, the correct path for your downloads, and the USER ID from Zoom's API. 

This requires a JWT token from the Zoom marketplace - https://marketplace.zoom.us

If you have a pro account you can find the USER ID in the URL for your account on this page - https://us02web.zoom.us/account/user#/

Here is where you can find instructions on listing a USER ID from an API endpoint - https://marketplace.zoom.us/docs/api-reference/zoom-api/users/users

Install the requirements listed in requirements.txt 

If you haven't done that before you will need to use PIP (https://pip.readthedocs.io/en/1.1/requirements.html)

Exact command is "pip install -r requirements.txt"

Then run "python cloudlink.py"

That will download all the recordings wherever you specify. 

Code written by Georg Kasmin and Lane Campbell

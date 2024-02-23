import requests

import utils

class zoom_client:
    def __init__(self, account_id: str, client_id: str, client_secret: str, PAGE_SIZE: int = 300):
        self.account_id = account_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.PAGE_SIZE = PAGE_SIZE
        self.cached_token = None

    def get(self, url):
        return self._get_with_token(lambda t: requests.get(url=url, headers=self.get_headers(t))).json()

    def _get_with_token(self, get):
        if self.cached_token:
            response = get(self.cached_token)
        
        if not self.cached_token or response.status_code == 401:
            self.cached_token = self.fetch_token()
            response = get(self.cached_token)

        if not response.ok:
            raise Exception(f'{response.status_code} {response.text}')
        
        return response

    def fetch_token(self):
        data = {
            'grant_type': 'account_credentials',
            'account_id': self.account_id
        }
        response = requests.post(
            'https://api.zoom.us/oauth/token', auth=(self.client_id, self.client_secret),  data=data
        ).json()
        if 'access_token' not in response:
            raise Exception(f'Unable to fetch access token: {response["reason"]} - verify your credentials.')

        return response['access_token']  
    
    def get_headers(self, token):
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

    def paginate(self, url):
        class __paginate_iter:
            def __init__(self, client, url):
                self.url = utils.add_url_params(url, {'page_size': client.PAGE_SIZE})
                self.client = client
                self.page = client.get(self.url)
                self.page_count = self.page['page_count'] or 1
            
            def __iter__(self): return self

            def __len__(self): return self.page_count

            def __next__(self):
                page = self.page
                if not page and self.page_token:
                    page = self.client.get(utils.add_url_params(self.url, {'next_page_token': self.page_token}))

                if not page:
                    raise StopIteration()

                self.page, self.page_token = None, page['next_page_token']
                return page
            
        return __paginate_iter(self, url)
    
    def do_with_token(self, do):
        def do_as_get(token):
            test_url = 'https://api.zoom.us/v2/users/me/recordings'

            test_response = requests.get(test_url, headers=self.get_headers(token))
            if test_response.ok:
                try:
                    do(token)
                except:
                    test_response = requests.get(test_url, headers=self.get_headers(token))
                    if test_response.ok:
                        raise

            return test_response
            
        self._get_with_token(lambda t: do_as_get(t))
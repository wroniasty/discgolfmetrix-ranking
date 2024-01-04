from typing import Tuple
import requests
from bs4 import BeautifulSoup as bs, element


# get player's pgda rating from the pdga website by player id
# returns a tuple of (rating, player_name)
# if player is not found, returns (None, None)
def get_player_rating(player_id: int) -> tuple[int | None, str | None]:
    url = f'https://pdga.com/player/{player_id}'
    result = requests.get(url)
    soup = bs(result.content, 'html.parser')
    try:
        header = soup.find('div', {'class': 'pane-page-title'}).find('h1')
        name = header.text.split('#')[0].strip() if header is not None else None
        rating = soup.find('ul', {'class': 'player-info'}).find('li', {'class': 'current-rating'})
        if rating is not None:
            rating = int("".join([str(t) for t in rating.children if isinstance(t, element.NavigableString)]).strip())
    except AttributeError:
        return None, None

    return rating, name


# search for player by name on the pdga website and return the first result
# returns a tuple of (player_id, player_rating)
# if player is not found, returns (None, None)
def search_player(player_name: str) -> Tuple[int | None, int | None]:
    fn, ln = player_name.split(' ')[:2]
    params = {
        "FirstName": fn,
        "LastName": ln,
        "PDGANum": "",
        "Status": "All",
        "Gender":  "All",
        "Class": "All",
        "MemberType": "All",
        "City": "",
        "StateProv": "All",
        "Country": "All",
        "Country_1": "All",
        "UpdateDate": ""
    }
    url = f'https://pdga.com/players'
    result = requests.get(url, params=params)
    soup = bs(result.content, 'html.parser')
    try:
        player_id = soup.find('td', {'class': 'views-field-PDGANum'}).text
        rating = soup.find('td', {'class': 'views-field-Rating-1'}).text
        if not rating.isnumeric():
            rating = "0"

        return int(player_id), int(rating)
    except AttributeError:
        return None, None

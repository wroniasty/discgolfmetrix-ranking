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


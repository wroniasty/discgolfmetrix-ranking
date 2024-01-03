from typing import List
from models import CompetitionResult


def calculate_round_rating(results: List[CompetitionResult]):
    for r in results:
        # TODO: calculate round rating
        r.rating = 0


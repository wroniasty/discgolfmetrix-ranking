import logging
import os.path

import requests
import datetime
from typing import Dict
import pickle
from models import Competition, Player, Course, Track, Score, CompetitionResult

"""metrix.py: Wrapper for  discgolfmetrix.com API (see https://discgolfmetrix.com/?u=rule&ID=37 )."""

__author__ = "Jakub Wroniecki"
__copyright__ = "Copyright 2022, Jakub Wroniecki, see LICENSE.txt for details."


class MetrixAPIError(BaseException):
    pass


class MetrixAPI:

    def __init__(self, cache_file=None):
        self.courses: Dict[int, Course] = {}
        self.players: Dict[int, Player] = {}
        self.competitions: Dict[int, Competition] = {}
        self.sub_competitions: Dict[int, Competition] = {}
        self._cache_file = None
        self.cache = {
            'competitions': {},
            'players': [],
            'ratings': {},
            'ratings_info': {},
        }

        if cache_file is not None:
            self._cache_file = cache_file

        self.load_cache()

    def load_cache(self):
        if self._cache_file is not None and os.path.isfile(self._cache_file):
            with open(self._cache_file, 'rb') as f:
                self.cache = pickle.load(f)

            if 'ratings' not in self.cache:
                self.cache['ratings'] = {}
            if 'ratings_info' not in self.cache:
                self.cache['ratings_info'] = {}
            if 'competitions' not in self.cache:
                self.cache['competitions'] = {}
            if 'players' not in self.cache:
                self.cache['players'] = []

            for p in self.cache['players']:
                self.players[p.id] = p
                self.players[hash(p.name.upper())] = p

    def save_cache(self):
        players_set = set()
        for p in self.players.values():
            players_set.add(p)
        self.cache['players'] = list(sorted(players_set, key=lambda p: p.name))

        for c in self.competitions.values():
            for c_sub in c.sub:
                if any(r.rating is not None for r in c_sub.results):
                    self.cache['ratings'][c_sub.id] = {r.player.id: r.rating for r in c_sub.results}
                    self.cache['ratings_info'][c_sub.id] = {
                        "rating_par": c_sub.rating_par,
                        "rating_propagators": c_sub.rating_propagators,
                        "rating_per_stroke": c_sub.rating_per_stroke,
                    }
                else:
                    self.cache['ratings'].pop(c_sub.id, None)
                    self.cache['ratings_info'].pop(c_sub.id, None)

        if self._cache_file is not None:
            with open(self._cache_file, 'wb') as f:
                pickle.dump(self.cache, f)

    def fetch_results_json(self, competition_id: int):

        if competition_id not in self.cache['competitions']:
            url = f'https://discgolfmetrix.com/api.php?content=result&id={competition_id}'
            logging.info(f"Fetching: {url}")
            result = requests.get(url)
            reply = result.json()
            self.cache['competitions'][competition_id] = reply

        return self.cache['competitions'][competition_id]

    def results(self, competition_id: int,ignore_holes=None):
        reply = self.fetch_results_json(competition_id)
        if "Competition" not in reply:
            raise MetrixAPIError(f'Missing key - "Competition" in API reply (content=result)')

        data = reply.get("Competition")
        if "Events" in data and len(data.get("Events", [])) > 0 \
                and len(data.get("SubCompetitions", [])) == 0:

            sub_competitions = []
            for event in data['Events']:
                sub_event_results = self.fetch_results_json(int(event['ID']))
                if 'Competition' not in sub_event_results:
                    raise MetrixAPIError(f'Missing key - "Competition" in API reply for sub event ID={event["ID"]}')
                sub_competitions.append(sub_event_results['Competition'])
            data['SubCompetitions'] = sub_competitions

        competition = self.get_competition_from_json(data,ignore_holes)
        for sub_data in data.get('SubCompetitions', []):
            sub_competition = self.get_competition_from_json(sub_data,ignore_holes)
            competition.sub.append(sub_competition)
            sub_competition.parent = competition
            self.sub_competitions[sub_competition.id] = sub_competition

        # print(data["SubCompetitions"])
        # print(competition)
        return competition

    def get_competition_from_json(self, data,ignore_holes) -> Competition:
        competition = self.get_competition(int(data['ID']),
                                           name=data['Name'],
                                           date=datetime.datetime.strptime(data['Date'], '%Y-%m-%d'))
        if data.get("CourseID"):
            competition.course = self.get_course(int(data['CourseID']), name=data['CourseName'])
        for track in data['Tracks']:
            competition.tracks.append(Track(number=int(track['Number']), par=int(track['Par']),
                                            number_alt=track['NumberAlt']))

        competition.rating_par = self.cache['ratings_info'].get(competition.id, {}).get('rating_par', None)
        competition.rating_propagators = self.cache['ratings_info'].get(competition.id, {}).get('rating_propagators',
                                                                                                None)
        competition.rating_per_stroke = self.cache['ratings_info'].get(competition.id, {}).get('rating_per_stroke',
                                                                                               None)

        for result in data['Results']:
            try:
                hash_id = hash(result['Name'].upper())
                if self.has_player(hash_id) and result['UserID'] is not None:
                    self.players[int(result['UserID'])] = self.get_player(hash_id)

                comp_result = CompetitionResult(
                    player=self.get_player(int(result['UserID'] or hash(result['Name'].upper())), name=result['Name']),
                    competition=competition,
                    class_name=result['ClassName'],
                    order_number=int(result['OrderNumber'] or 0),
                    submitted_sum=int(result['Sum']),
                    submitted_diff=int(result['Diff']),
                    rating=self.cache['ratings'].get(competition.id, {}).get(
                        int(result['UserID'] or hash(result['Name'].upper())), None)
                )
                self.players[hash_id] = comp_result.player
                round_missing = False

                if result.get('DNF') not in (None, "0"):
                    comp_result.valid = False

                if len(list(plresult for plresult in result['PlayerResults'] if
                            isinstance(plresult, dict) and "Result" in plresult)) == 0:
                    logging.warning(f"[{competition.id}] {competition.name} - {comp_result.player.name}: "
                                    f"Brak wyników rundy (używam 999).")
                    comp_result.valid = False
                    score = Score(result=999, diff=999 - competition.par)
                    comp_result.scores.append(score)
                    round_missing = True
                    
                if not round_missing:

                    for track_idx, plresult in enumerate(result['PlayerResults']):
                        if ignore_holes and (track_idx+1) in ignore_holes:
                            score = Score(
                                    result=competition.tracks[track_idx].par,
                                    diff=0
                                )
                        else:
                            if isinstance(plresult, dict) and "Result" in plresult:
                                score = Score(
                                    result=int(plresult['Result']),
                                    diff=int(plresult["Diff"])
                                )
                            else:
                                score = Score(
                                    result=competition.tracks[track_idx].par + 3,
                                    diff=3
                                )
                                logging.warning(f"[{competition.id}] {competition.name} - {comp_result.player.name}: "
                                                f"Brak wyniku - dołek nr {track_idx + 1} - używam par+3 == {score.result}.")
                        if score.result > 0:
                            comp_result.scores.append(score)

                if comp_result.submitted_sum != comp_result.sum and comp_result.valid:
                    logging.warning(f"[{competition.id}] {competition.name} - {comp_result.player.name}: "
                                    f"Podany wynik {comp_result.submitted_sum} niezgodny z obliczonym == {comp_result.sum}")

                # if len(comp_result.scores) < len(competition.tracks):
                #     logging.error(f"Ejecting result for {comp_result.player.name} in {competition.name} - invalid number of results "
                #                   f"({len(comp_result.scores)} < {len(competition.tracks)}) submitted == {comp_result.submitted_sum}.")
                #     comp_result.valid = False

                if result.get('DNF') not in (None, "0"):
                    comp_result.valid = False

                competition.results.append(comp_result)

            except TypeError as e:
                logging.error(f"Error processing {competition.id} [{competition.name}] {result}", exc_info=e)

        return competition

    def get_course(self, id, **params) -> Course:
        if id not in self.courses:
            self.courses[id] = Course(id=id, **params)
        return self.courses[id]

    def get_player(self, id, **params) -> Player:
        if id not in self.players:
            self.players[id] = Player(id=id, **params)
        return self.players[id]

    def has_player(self, id) -> bool:
        return id in self.players

    def get_competition(self, id, **params) -> Competition:
        if id not in self.competitions:
            self.competitions[id] = Competition(id=id, **params)
        return self.competitions[id]

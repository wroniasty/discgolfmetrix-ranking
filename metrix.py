import logging
import requests
import datetime
from typing import Dict
from models import Competition, Player, Course, Track, Score, CompetitionResult


class MetrixAPIError(BaseException):
    pass


class MetrixAPI:

    def __init__(self):
        self.courses: Dict[int, Course] = {}
        self.players: Dict[int, Player] = {}
        self.competitions: Dict[int, Competition] = {}
        pass

    def results(self, competition_id: int):
        result = requests.get(f'https://discgolfmetrix.com/api.php?content=result&id={competition_id}')
        reply = result.json()
        if "Competition" not in reply:
            raise MetrixAPIError(f'Missing key - "Competition" in API reply (content=result)')
        data = reply.get("Competition")
        competition = self.get_competition_from_json(data)
        for sub_data in data.get('SubCompetitions', []):
            sub_competition = self.get_competition_from_json(sub_data)
            competition.sub.append(sub_competition)
            sub_competition.parent = competition

        # print(data["SubCompetitions"])
        # print(competition)
        return competition

    def get_competition_from_json(self, data) -> Competition:
        competition = self.get_competition(int(data['ID']),
                                           name=data['Name'],
                                           date=datetime.datetime.strptime(data['Date'], '%Y-%m-%d'))
        if data.get("CourseID"):
            competition.course = self.get_course(int(data['CourseID']), name=data['CourseName'])
        for track in data['Tracks']:
            competition.tracks.append(Track(number=int(track['Number']), par=int(track['Par']),
                                            number_alt=track['NumberAlt']))
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
                    submitted_diff=int(result['Diff'])
                )
                self.players[hash_id] = comp_result.player
                round_missing = False

                if result.get('DNF') not in (None, "0"):
                    comp_result.valid = False

                if len(list(plresult for plresult in result['PlayerResults'] if isinstance(plresult, dict) and "Result" in plresult)) == 0:
                    logging.error(f"[{competition.id}] {competition.name} - {comp_result.player.name}: "
                                  f"Brak wyników rundy (używam 999).")
                    comp_result.valid = False
                    score = Score(result=999, diff=999 - competition.par)
                    comp_result.scores.append(score)
                    round_missing = True

                if not round_missing:
                    for track_idx, plresult in enumerate(result['PlayerResults']):
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
                            logging.error(f"[{competition.id}] {competition.name} - {comp_result.player.name}: "
                                          f"Brak wyniku - dołek nr {track_idx+1} - używam par+3 == {score.result}.")
                        if score.result > 0:
                            comp_result.scores.append(score)

                if comp_result.submitted_sum != comp_result.sum and comp_result.valid:
                    logging.error(f"[{competition.id}] {competition.name} - {comp_result.player.name}: "
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
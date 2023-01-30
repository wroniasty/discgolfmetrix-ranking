from dataclasses import dataclass, field
from typing import Dict, List

from models import RankingEntry, Competition, Player
from metrix import MetrixAPI

"""main.py: Generator rankingu Zimowej Ligi DGW."""

__author__ = "Jakub Wroniecki"
__copyright__ = "Copyright 2022, Jakub Wroniecki, see LICENSE.txt for details."

class ZimowyDGW:

    @dataclass
    class DGWEntry:
        player: Player
        results: Dict[int, RankingEntry] = field(default_factory=dict)
        sum: int = 0
        place: int = None

        def best(self, count):
            for s in self.results.values():
                s.selected = False
            selected = sorted(self.results.values(), key=lambda r: 0 if r.dqf else -r.points)[:count]
            for s in selected:
                s.selected = True
            self.sum = sum(0 if s.dqf else s.points for s in selected)
            return self.sum

        def __hash__(self):
            return hash(self.player)

    def __init__(self, competition_ids: List[int], title=''):
        self.competition_ids = competition_ids

        self.entries = {
            "OPEN": {},
            "WOMEN": {},
            "MASTERS": {},
            "JUNIOR": {}
        }

        self.entries_sorted: Dict[str, List[ZimowyDGW.DGWEntry]] = {}

        self.rankings = {
            "OPEN": {},
            "WOMEN": {},
            "MASTERS": {},
            "JUNIOR": {}
        }
        self.competitions: List[Competition] = []

        self.errors: List[str] = []
        self.title = title

    def reload(self) -> List[Competition]:
        api = MetrixAPI()
        data: List[Competition] = []

        for competition_id in self.competition_ids:
            data.append(api.results(competition_id))

        for competition in data:
            self.competitions.append(competition)
            rankings = {}
            for class_name, ranking in competition.ranking:
                class_name = class_name.upper()
                if "MASTER" in class_name:
                    real_class_name = "MASTERS"
                elif "WOMEN" in class_name:
                    real_class_name = "WOMEN"
                elif "JUNIOR" in class_name:
                    real_class_name = "JUNIOR"
                else:
                    real_class_name = "OPEN"
                rankings[real_class_name] = ranking

            if "OPEN" not in rankings:
                continue

            LuOpen = len(list(e for e in rankings["OPEN"].entries if not e[1].dqf))

            for class_name, ranking in rankings.items():
                Lu = len(list(e for e in ranking.entries if not e[1].dqf))
                if Lu < 3:
                    filler_ranking = rankings["OPEN"].entries[:]
                    filler_ranking.extend(ranking.entries)

                for entry in ranking.entries:
                    dgw_entry: ZimowyDGW.DGWEntry = self.entries[class_name].get(entry[1].player, self.DGWEntry(player=entry[1].player))
                    if Lu >= 3:
                        entry[1].points = (Lu-entry[0]+1)*(100/Lu)
                        entry[1].comment = f"{entry[0]} na {Lu} = ({Lu}-{entry[0]}+1)*(100/{Lu}) = ({Lu - entry[0] +1}*{(100/Lu):0.3f})"
                    else:
                        M = 1
                        for m, re in rankings["OPEN"].entries:
                            if re.sum < entry[1].sum:
                                M = M + 1
                            else:
                                break
                        entry[1].comment = f"(OPEN) {M} na {LuOpen+1} = ({LuOpen + 1}-{entry[0]}+1)*(100/{Lu}) = ({LuOpen + 1 - entry[0]+1}*{(100/(LuOpen+1)):0.2f}) "
                        entry[1].points = (LuOpen + 1 - M + 1)*(100/(LuOpen+1))
                    dgw_entry.results[competition.id] = entry[1]
                    self.entries[class_name][entry[1].player] = dgw_entry

        for class_name, entries in self.entries.items():
            print(f"Ranking: {class_name}")
            self.entries_sorted[class_name] = list(sorted(entries.values(), key=lambda e: -e.best(7)))
            place = 0
            count = 1
            previous_points = 1e24
            for e in self.entries_sorted[class_name]:
                if e.sum < previous_points:
                    place = count
                    previous_points = e.sum
                e.place = place
                count = count + 1

        return data


def main(args):
    import jinja2
    import os
    import logging
    import yaml

    try:
        config = yaml.load(open(args.config, 'r'), Loader=yaml.CLoader)
    except IOError as e:
        print(e)
        return

    if args.league not in config['leagues']:
        print(f"{args.league} not found in {args.config}.")
        return
    else:
        league = config['leagues'].get(args.league)

    class HtmlHandler(logging.StreamHandler):

        def __init__(self, dgw: ZimowyDGW):
            super().__init__()
            self.dgw = dgw

        def emit(self, record: logging.LogRecord):
            self.dgw.errors.append(self.format(record))

    logger = logging.getLogger()
    logger.addHandler(logging.StreamHandler())

    print(os.path.realpath(__file__))
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(os.path.realpath(__file__))),
                             trim_blocks=True, lstrip_blocks=True)
    template = env.get_template("dgw.template.html")
    dgw = ZimowyDGW(league.get('competition_ids'), league.get('title'))
    logger.addHandler(HtmlHandler(dgw))
    dgw.reload()
    with open(f'{args.league}.ranking.html', 'w') as f:
        f.write(template.render(data=dgw))


if __name__ == '__main__':
    import argparse
    import os

    argparser = argparse.ArgumentParser()
    argparser.add_argument('--league', '-l', type=str, required=True)
    argparser.add_argument('--config', '-c', type=str, default=os.path.dirname(os.path.realpath(__file__)) + '/config.yaml')
    main(argparser.parse_args())


from dataclasses import dataclass, field
from typing import Dict, List, Optional
import logging

from models import RankingEntry, Competition, Player
from metrix import MetrixAPI
import jinja2
import os, os.path

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
            selected = sorted(self.results.values(), key=lambda r: 1 if r.dqf else -r.points)[:count]
            for s in selected:
                s.selected = True
            self.sum = sum(1 if s.dqf else s.points for s in selected)
            return self.sum

        def __hash__(self):
            return hash(self.player)

    def __init__(self, competition_ids: List[int], title='', api: Optional[MetrixAPI] = None, cache_file=None,ignore_holes=None):
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

        self.cache_file = cache_file

        self.api = api or MetrixAPI(cache_file=self.cache_file)

        self.ignore_holes=ignore_holes

    def reload(self) -> List[Competition]:
        api = self.api
        data: List[Competition] = []

        for competition_id in self.competition_ids:
            if self.ignore_holes and competition_id in self.ignore_holes:
                data.append(api.results(competition_id,self.ignore_holes[competition_id]))
            else:
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
            logging.info(f"Generating ranking: {class_name}")
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

    def render_ranking(self, filename: str):
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(os.path.realpath(__file__))),
                                 trim_blocks=True, lstrip_blocks=True)
        template = env.get_template("dgw.template.html")
        html_file = f'{filename}'
        logging.info(f"Generating HTML -> {html_file}.")
        all_results = []
        for c in self.competitions:
            for s in c.sub:
                all_results.extend(s.results)
        all_results = list(sorted(all_results, key=lambda r: r.rating or 0, reverse=True))
        logging.info(f"Results: {len(all_results)}")
        top_results = all_results[:50]
        with open(f'{html_file}', 'w', encoding='utf-8') as f:
            f.write(template.render(data=self, ratings=self.api.cache['ratings'], top_rounds=top_results))

    def render_rating(self, filename: str):
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(os.path.realpath(__file__))),
                                 trim_blocks=True, lstrip_blocks=True)
        template = env.get_template("dgw.rating.template.html")
        html_file = f'{filename}'
        logging.info(f"Generating HTML -> {html_file}.")
        all_results = []
        for c in self.competitions:
            for s in c.sub:
                all_results.extend(s.results)
        all_results = list(sorted(all_results, key=lambda r: r.rating or 0, reverse=True))
        logging.info(f"Results: {len(all_results)}")
        top_results = all_results[:50]
        with open(f'{html_file}', 'w', encoding='utf-8') as f:
            f.write(template.render(data=self, ratings=self.api.cache['ratings'], top_rounds=top_results))


class DgwHtmlHandler(logging.StreamHandler):

    def __init__(self, dgw: ZimowyDGW):
        super().__init__()
        self.dgw = dgw

    def emit(self, record: logging.LogRecord):
        self.dgw.errors.append(self.format(record))

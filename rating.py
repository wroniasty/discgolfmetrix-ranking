import dgw

def main(args):
    import jinja2
    import re
    import statistics
    from collections import defaultdict
    import logging
    import yaml
    from metrix import MetrixAPI
    from models import Competition
    from typing import List

    from rich.console import Console
    from rich.logging import RichHandler
    from rich.table import Table

    from dgw import ZimowyDGW

    logging.basicConfig(level=logging.INFO,
                        handlers=[RichHandler(level=logging.INFO)],
                        format='%(asctime)s %(levelname)s %(message)s')

    console = Console(stderr=True)
    try:
        config = yaml.load(open(args.config, 'r'), Loader=yaml.CLoader)
    except IOError as e:
        console.print(e)
        return

    api = MetrixAPI()
    # api.on_score_missing = MetrixAPI.Const.IGNORE
    api.on_round_missing = MetrixAPI.Const.IGNORE

    data: List[Competition] = [api.results(competition_id)
                               for competition_id in config['leagues'][args.league]['competition_ids']
                               ]



    #print(data)
    for competition_data in data:
        logging.info(f"""[{competition_data.id}] {competition_data.name} Holes: {len(competition_data.tracks)} Rounds: {len(competition_data.sub)}""")

        for s in competition_data.sub:
            results = defaultdict(lambda: {h.number: [] for h in competition_data.tracks})
            for r in s.results:
                if not r.valid:
                    continue
                for idx, score in enumerate(r.scores):
                    results[r.class_name][idx+1].append(score.result)

            table = Table(title=f"{s.name}", expand=True)
            table.add_column(f"Hole", justify="right")
            table.add_column(f"Par", justify="right")
            [table.add_column(stat) for stat in [f"Cnt", "Geo", "Har", "Mean", "Std", "Var"]]

            for hole in competition_data.tracks:

                hole_data = []
                for class_name in [cn for cn in results.keys() if not re.match(r"WOMEN|JUNIOR", cn, re.I)]:
                    hole_data += results[class_name][hole.number]

                geo_mean = statistics.geometric_mean(hole_data)
                har_mean = statistics.harmonic_mean(hole_data)
                mean = statistics.fmean(hole_data)
                stdev = statistics.stdev(hole_data)
                variance = statistics.variance(hole_data)

                row = [f"{hole.number}", f"{hole.par} ({mean - hole.par:.2f})",
                       f"{len(hole_data)}",
                       f"{geo_mean:.2f}",
                       f"{har_mean:.2f}",
                       f"{mean:.2f}",
                       f"{stdev:.2f}",
                       f"{variance:.2f}"]

                table.add_row(*row)

            # console.print(s.id, s.name)
            console.print(table)


if __name__ == '__main__':
    import argparse
    import os

    argparser = argparse.ArgumentParser()
    argparser.add_argument('--league', '-l', type=str, required=True)
    argparser.add_argument('--config', '-c', type=str, default=os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                                                            'config.yaml'))
    main(argparser.parse_args())

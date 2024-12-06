import logging
from dgw import ZimowyDGW, DgwHtmlHandler

"""main.py: Generator rankingu Zimowej Ligi DGW."""

__author__ = "Jakub Wroniecki"
__copyright__ = "Copyright 2022, Jakub Wroniecki, see LICENSE.txt for details."


def main(args):
    import jinja2
    import os
    import yaml
    import rating
    from rich.logging import RichHandler
    from pprint import pprint

    logger = logging.getLogger()
    logger.addHandler(RichHandler())

    try:
        config = yaml.load(open(args.config, 'r'), Loader=yaml.CLoader)
    except IOError as e:
        logging.exception(f"Loading config file '{args.config}' failed.")
        return

    if args.league not in config['leagues']:
        print(f"{args.league} not found in {args.config}.")
        return
    else:
        league = config['leagues'].get(args.league)


    if args.quiet > 0:
        logger.setLevel(logging.ERROR)
    elif args.verbose > 0:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    # env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(os.path.realpath(__file__))),
    #                          trim_blocks=True, lstrip_blocks=True)
    # template = env.get_template("dgw.template.html")
    dgw = ZimowyDGW(league.get('competition_ids'), league.get('title'), cache_file=args.cache_file, ignore_holes=league.get("ignore_holes"))
    logger.addHandler(DgwHtmlHandler(dgw))
    dgw.reload()

    if not args.skip_ratings:
        player_lookup = {
            player.id: player.pdga_rating for player in dgw.api.players.values() if (player.pdga_rating or 0) > 0
        }
        for comp in dgw.api.competitions.values():
            for sub_comp in comp.sub:
                if any(r.rating is not None for r in sub_comp.results) and not args.force_ratings:
                    logging.warning(f"Skipping calculating ratings for {comp.name}, already in cache.")
                else:
                    rating.calculate_round_rating(sub_comp, player_lookup, plotting=True,
                                                  outlier_fraction=config.get("rating", {}).get("outlier_fraction", 0.25),
                                                  prop_min_rating=config.get("rating", {}).get("prop_min_rating", 500))
    else:
        logging.info("Skipping ratings calculation.")

    dgw.api.save_cache()

    html_file = f'{args.league}.ranking.html'
    dgw.render_ranking(html_file)
    html_file = f'{args.league}.rating.html'
    dgw.render_rating(html_file)

    # logging.info(f"Generating HTML -> {html_file}.")
    # with open(f'{html_file}', 'w', encoding='utf-8') as f:
    #     f.write(template.render(data=dgw, ratings=dgw.api.cache['ratings']))


if __name__ == '__main__':
    import argparse
    import os

    argparser = argparse.ArgumentParser()
    argparser.add_argument('--league', '-l', type=str, required=True)
    argparser.add_argument('--skip-ratings', action='store_true')
    argparser.add_argument('--force-ratings', action='store_true', help="Force ratings calculation, ignore cached values.")
    argparser.add_argument('--config', '-c', type=str,
                           default=os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                                'config.yaml'))
    argparser.add_argument('--cache-file', type=str,
                           default=os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                                'results.cache.pkl'))
    argparser.add_argument('-v', action="count", dest="verbose", default=0)
    argparser.add_argument('--quiet', '-q', action="store_const", const=True, default=False)

    main(argparser.parse_args())


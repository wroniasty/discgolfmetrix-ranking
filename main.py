"""main.py: Generator rankingu Zimowej Ligi DGW."""

__author__ = "Jakub Wroniecki"
__copyright__ = "Copyright 2022, Jakub Wroniecki, see LICENSE.txt for details."


def main(args):
    import jinja2
    import os
    import logging
    import yaml

    from dgw import ZimowyDGW

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


"""Run standard oTree with the optional feedback gateway outside its middleware.

Examples from this directory:
    python study_server.py devserver_inner 8000
    python study_server.py prodserver1of2

The normal oTree setup, session checks, timeout subprocess and shutdown handling
are retained. Request access logging is disabled to protect pilot feedback.
"""

import sys


def run_study_uvicorn(addr, port, *, is_devserver):
    from otree.asgi import app as otree_app
    from uvicorn import Config, Server
    from anonymous_feedback import FeedbackGateway

    server = Server(Config(
        FeedbackGateway(otree_app), host=addr, port=int(port), workers=1,
        log_level='warning' if is_devserver else 'info', log_config=None,
        ws='websockets', access_log=False,
    ))
    server.run()


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in {'devserver_inner', 'prodserver1of2'}:
        raise SystemExit(
            'Use: python study_server.py devserver_inner [port], '
            'or python study_server.py prodserver1of2 [port]'
        )
    from otree.main import execute_from_command_line
    from otree.cli import prodserver1of2

    prodserver1of2.run_uvicorn = run_study_uvicorn
    execute_from_command_line()

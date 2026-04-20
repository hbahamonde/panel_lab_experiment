from os import environ

SESSION_CONFIGS = [
    dict(
        name='panel_lab_experiment',
        display_name='3-wave panel lab experiment',
        num_demo_participants=1,
        app_sequence=['intro_consent', 'wave1_threat', 'wave2_discontinuity', 'wave3_election'],
        wave1_date='2026-05-05',
        wave2_date='2026-05-12',
        wave3_date='2026-05-19',
        wave_window_days=3,
        enable_wave_gates=False,
    )
]

# if you set a property in SESSION_CONFIG_DEFAULTS, it will be inherited by all configs
# in SESSION_CONFIGS, except those that explicitly override it.
# the session config can be accessed from methods in your apps as self.session.config,
# e.g. self.session.config['participation_fee']

SESSION_CONFIG_DEFAULTS = dict(
    real_world_currency_per_point=1.00, participation_fee=0.00, doc=""
)

PARTICIPANT_FIELDS = []
SESSION_FIELDS = []

# ISO-639 code
# for example: de, fr, ja, ko, zh-hans
LANGUAGE_CODE = 'en'

# e.g. EUR, GBP, CNY, JPY
REAL_WORLD_CURRENCY_CODE = 'EUR'
USE_POINTS = True

ADMIN_USERNAME = 'admin'
# for security, best to set admin password in an environment variable
ADMIN_PASSWORD = environ.get('OTREE_ADMIN_PASSWORD')

DEMO_PAGE_INTRO_HTML = """ """

ROOMS = [
    dict(
        name='panel_lab_room',
        display_name='Panel Lab Experiment',
        participant_label_file='_rooms/panel_lab_labels.txt',
        use_secure_urls=True,
    ),
]

SECRET_KEY = '4102785174378'

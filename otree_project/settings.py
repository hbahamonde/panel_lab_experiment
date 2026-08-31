from os import environ

SESSION_CONFIGS = [
    dict(
        name='panel_lab_experiment',
        display_name='Group decisions and public services',
        num_demo_participants=10,
        app_sequence=['intro_consent', 'block1_crisis', 'block2_reversal'],
        allow_optional_responses=False,
        flexible_matching_pools=True,
    ),
    dict(
        name='panel_lab_demo',
        display_name='Group decisions and public services (full-group testing)',
        num_demo_participants=10,
        app_sequence=['intro_consent', 'block1_crisis', 'block2_reversal'],
        allow_optional_responses=True,
        flexible_matching_pools=True,
    ),
    dict(
        name='panel_lab_solo_recovery',
        display_name='Solo test: conditions improve',
        num_demo_participants=1,
        app_sequence=['intro_consent', 'block1_crisis', 'block2_reversal'],
        allow_optional_responses=True,
        matching_pool_size=1,
        solo_testing=True,
        solo_treatment='recovery',
    ),
    dict(
        name='panel_lab_solo_persistence',
        display_name='Solo test: conditions remain unchanged',
        num_demo_participants=1,
        app_sequence=['intro_consent', 'block1_crisis', 'block2_reversal'],
        allow_optional_responses=True,
        matching_pool_size=1,
        solo_testing=True,
        solo_treatment='persistence',
    )
]

# if you set a property in SESSION_CONFIG_DEFAULTS, it will be inherited by all configs
# in SESSION_CONFIGS, except those that explicitly override it.
# the session config can be accessed from methods in your apps as self.session.config,
# e.g. self.session.config['participation_fee']

SESSION_CONFIG_DEFAULTS = dict(
    # Two selected payoff rounds can yield at most 120 points in total.
    # This linear conversion therefore keeps the performance bonus at EUR 5 or less.
    real_world_currency_per_point=5.00 / 120,
    participation_fee=10.00,
    performance_bonus_cap=5.00,
    doc=(
        'One synchronized laboratory session with two ten-round blocks, '
        'anonymous rematching in 10- or 15-person pools, leader proposals with or '
        'without group approval, post-Block-1 pool randomization, and one '
        'randomly selected payoff round per block.'
    ),
)

PARTICIPANT_FIELDS = []
SESSION_FIELDS = []

# ISO-639 code
# for example: de, fr, ja, ko, zh-hans
LANGUAGE_CODE = 'en'

# e.g. EUR, GBP, CNY, JPY
REAL_WORLD_CURRENCY_CODE = 'EUR'
USE_POINTS = True
POINTS_DECIMAL_PLACES = 2

ADMIN_USERNAME = 'admin'
# for security, best to set admin password in an environment variable
ADMIN_PASSWORD = environ.get('OTREE_ADMIN_PASSWORD')

DEMO_PAGE_INTRO_HTML = """ """

ROOMS = [
    dict(
        name='panel_lab_room',
        display_name='Group Decisions Study',
        participant_label_file='_rooms/panel_lab_labels.txt',
        use_secure_urls=True,
    ),
]

SECRET_KEY = '4102785174378'

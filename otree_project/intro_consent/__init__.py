import time

from otree.api import *


doc = """
Consent and instructions for the one-session interactive laboratory experiment.
"""


def study_details(session):
    return dict(
        participation_fee=f"{session.config['participation_fee']:.2f} €".replace('.', ','),
        bonus_cap=f"{session.config['performance_bonus_cap']:.2f} €".replace('.', ','),
        pretest_feedback_enabled=session.config.get('pretest_feedback_enabled', False),
    )


def creating_session(subsession):
    if (
        subsession.session.config.get('pretest_feedback_enabled', False)
        and not subsession.session.config.get('solo_testing', False)
        and len(subsession.get_players()) != 10
    ):
        raise RuntimeError(
            'The pre-test feedback option requires a ten-person session. '
            'Turn it off for subsequent production sessions.'
        )


class C(BaseConstants):
    NAME_IN_URL = 'study_start'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 1

    CONSENT_FORM_VERSION = '2026-10-27-v9-fi'
    CONSENT_CHOICES = [[
        'accept',
        'Olen lukenut yllä olevat tiedot ja suostun osallistumaan tähän tutkimukseen.',
    ]]


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    consent = models.StringField(
        choices=C.CONSENT_CHOICES,
        widget=widgets.RadioSelect,
        label='Vahvista osallistumisesi:',
    )
    consent_form_version = models.StringField(blank=True)
    consent_recorded_at = models.FloatField()
    lab_site = models.StringField(blank=True)


class Consent(Page):
    form_model = 'player'
    form_fields = ['consent']

    @staticmethod
    def vars_for_template(player: Player):
        return study_details(player.session)

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        player.consent_form_version = C.CONSENT_FORM_VERSION
        player.consent_recorded_at = time.time()
        player.lab_site = player.session.config.get('lab_site', 'unspecified')
        player.participant.vars['consent'] = player.consent
        player.participant.vars['consent_form_version'] = player.consent_form_version
        player.participant.vars['consent_recorded_at'] = player.consent_recorded_at
        player.participant.vars['lab_site'] = player.lab_site


class Instructions(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.consent == 'accept'

    @staticmethod
    def vars_for_template(player: Player):
        return study_details(player.session)


page_sequence = [Consent, Instructions]

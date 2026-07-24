import random

from otree.api import *


doc = """
Block 1 of the one-session experiment: a common public-service crisis, ten
repeated institutional-choice/public-good rounds and mechanism measurement.
Participants are anonymously rematched within ten-person pools.
"""


def development_mode(player):
    """Allow researchers to move through the demo without completing every field."""
    return player.session.config.get('allow_optional_responses', False)


def require_all(player, values, field_names):
    if development_mode(player):
        return
    if any(values.get(field_name) in (None, '') for field_name in field_names):
        return 'Please answer all questions before continuing.'


def solo_testing(obj):
    return obj.session.config.get('solo_testing', False)


def assign_matching_pools(subsession):
    players = subsession.get_players()
    pool_size = subsession.session.config.get('matching_pool_size', C.MATCHING_POOL_SIZE)

    if solo_testing(subsession):
        if len(players) != 1:
            raise RuntimeError('Solo testing sessions require exactly one participant.')
        player = players[0]
        if subsession.round_number == 1:
            player.participant.vars['matching_pool_id'] = 1
            player.participant.vars['matching_pool_uid'] = f'{subsession.session.code}-pool-1'
            player.participant.vars['times_executive'] = 0
            subsession.session.vars['wave1_paying_round'] = random.randint(1, C.NUM_ROUNDS)
        subsession.set_group_matrix([[player]])
        player.matching_pool_id = 1
        player.matching_pool_uid = player.participant.vars['matching_pool_uid']
        return

    if subsession.round_number == 1:
        if pool_size % C.GROUP_SIZE != 0:
            raise RuntimeError('The matching-pool size must be divisible by five.')
        if len(players) % pool_size != 0:
            raise RuntimeError(
                f'The session size must be divisible by the {pool_size}-person matching-pool size.'
            )

        shuffled = random.sample(players, len(players))
        for index, player in enumerate(shuffled):
            pool_id = index // pool_size + 1
            player.participant.vars['matching_pool_id'] = pool_id
            player.participant.vars['matching_pool_uid'] = (
                f'{subsession.session.code}-pool-{pool_id}'
            )
            player.participant.vars['times_executive'] = 0

        subsession.session.vars['wave1_paying_round'] = random.randint(1, C.NUM_ROUNDS)

    groups = []
    pool_ids = sorted({p.participant.vars['matching_pool_id'] for p in players})
    for pool_id in pool_ids:
        pool_players = [p for p in players if p.participant.vars['matching_pool_id'] == pool_id]
        random.shuffle(pool_players)
        if len(pool_players) % C.GROUP_SIZE != 0:
            raise RuntimeError(
                f'Matching pool {pool_id} contains {len(pool_players)} participants; '
                'each pool must be divisible into five-person groups.'
            )
        groups.extend(
            pool_players[index:index + C.GROUP_SIZE]
            for index in range(0, len(pool_players), C.GROUP_SIZE)
        )

    subsession.set_group_matrix(groups)
    for player in players:
        player.matching_pool_id = player.participant.vars['matching_pool_id']
        player.matching_pool_uid = player.participant.vars['matching_pool_uid']


def choose_institution(group):
    players = group.get_players()
    if solo_testing(group):
        player = players[0]
        other_leader_votes = player.field_maybe_none('solo_other_leader_votes')
        undemocratic_votes = int(player.institution_vote == C.EXECUTIVE) + (
            other_leader_votes if other_leader_votes is not None else 2
        )
    else:
        undemocratic_votes = sum(p.institution_vote == C.EXECUTIVE for p in players)
    group.executive_votes = undemocratic_votes
    group.selected_institution = C.EXECUTIVE if undemocratic_votes >= 3 else C.CONSTRAINED

    if group.selected_institution == C.EXECUTIVE:
        if solo_testing(group):
            executive = players[0]
            executive.is_executive = True
            executive.participant.vars['times_executive'] = (
                executive.participant.vars.get('times_executive', 0) + 1
            )
            group.executive_id = executive.id_in_group
            return
        minimum_count = min(p.participant.vars.get('times_executive', 0) for p in players)
        eligible = [p for p in players if p.participant.vars.get('times_executive', 0) == minimum_count]
        executive = random.choice(eligible)
        executive.is_executive = True
        executive.participant.vars['times_executive'] = minimum_count + 1
        group.executive_id = executive.id_in_group


def calculate_round(group):
    players = group.get_players()
    if group.selected_institution == C.CONSTRAINED:
        if solo_testing(group):
            total = (players[0].contribution or 0) + C.SOLO_OTHER_CITIZENS * C.SOLO_OTHER_CONTRIBUTION
        else:
            total = sum(p.contribution or 0 for p in players)
        group.total_contribution = total
        group.executive_tax = 0
        group.executive_rent = 0
        group.public_account = total
        group.per_capita_return = C.CONSTRAINED_MULTIPLIER_CRISIS * total / C.GROUP_SIZE
        for player in players:
            player.round_payoff = C.ENDOWMENT - (player.contribution or 0) + group.per_capita_return
    else:
        executive = group.get_player_by_id(group.executive_id)
        tax = executive.executive_tax or 0
        rent = executive.executive_rent or 0
        public_account = C.GROUP_SIZE * tax - rent
        group.total_contribution = C.GROUP_SIZE * tax
        group.executive_tax = tax
        group.executive_rent = rent
        group.public_account = public_account
        group.per_capita_return = C.EXECUTIVE_MULTIPLIER * public_account / C.GROUP_SIZE
        for player in players:
            player.round_payoff = C.ENDOWMENT - tax + group.per_capita_return
            if player.id_in_group == group.executive_id:
                player.round_payoff += rent


class C(BaseConstants):
    NAME_IN_URL = 'wave1_threat'
    PLAYERS_PER_GROUP = None
    GROUP_SIZE = 5
    MATCHING_POOL_SIZE = 10
    NUM_ROUNDS = 10

    ENDOWMENT = 20
    CONSTRAINED_MULTIPLIER_CRISIS = 1.50
    CONSTRAINED_MULTIPLIER_RECOVERY = 2.50
    EXECUTIVE_MULTIPLIER = 2.50
    MAX_EXECUTIVE_RENT = 20
    SOLO_OTHER_CITIZENS = 4
    SOLO_OTHER_CONTRIBUTION = 10

    CONSTRAINED = 'constrained'
    EXECUTIVE = 'executive'
    TREATMENT_RECOVERY = 'recovery'
    TREATMENT_PERSISTENCE = 'persistence'
    DEFAULT_CONTRIBUTION = 10
    DEFAULT_EXECUTIVE_TAX = 10
    DEFAULT_EXECUTIVE_RENT = 0
    INSTITUTION_CHOICES = [
        [CONSTRAINED, 'Each person chooses'],
        [EXECUTIVE, 'One person chooses for the group'],
    ]

class Subsession(BaseSubsession):
    pass


def creating_session(subsession: Subsession):
    assign_matching_pools(subsession)


class Group(BaseGroup):
    selected_institution = models.StringField()
    executive_votes = models.IntegerField(initial=0)
    executive_id = models.IntegerField(initial=0)
    total_contribution = models.IntegerField(initial=0)
    executive_tax = models.IntegerField(initial=0)
    executive_rent = models.IntegerField(initial=0)
    public_account = models.IntegerField(initial=0)
    per_capita_return = models.FloatField(initial=0)


class Player(BasePlayer):
    matching_pool_id = models.IntegerField()
    matching_pool_uid = models.StringField()
    institution_vote = models.StringField(
        choices=C.INSTITUTION_CHOICES,
        widget=widgets.RadioSelect,
        label='How should the fund decision be made this round?',
        blank=True,
    )
    solo_other_leader_votes = models.IntegerField(min=0, max=4, blank=True)
    contribution = models.IntegerField(
        min=0, max=C.ENDOWMENT,
        label='How many of your 20 points do you put in the public-services fund?',
        blank=True,
    )
    executive_tax = models.IntegerField(
        min=0, max=C.ENDOWMENT,
        label='How many points must each group member put in the public-services fund?',
        blank=True,
    )
    executive_rent = models.IntegerField(
        min=0, max=C.MAX_EXECUTIVE_RENT,
        label='How many fund points do you move to your own payoff?',
        blank=True,
    )
    is_executive = models.BooleanField(initial=False)
    timed_out = models.BooleanField(initial=False)
    institution_vote_timed_out = models.BooleanField(initial=False)
    round_payoff = models.FloatField(initial=0)
    expected_payoff_citizens = models.IntegerField(
        min=0, max=60,
        label='If Each person chooses is used in this round, how many points do you expect to earn?',
        blank=True,
    )
    expected_payoff_leader = models.IntegerField(
        min=0, max=60,
        label='If One person chooses for the group is used, how many points do you expect to earn?',
        blank=True,
    )
    expected_leader_transfer = models.IntegerField(
        min=0, max=C.MAX_EXECUTIVE_RENT,
        label='If one person chooses for the group, how many fund points do you expect the selected person to move to their own payoff?',
        blank=True,
    )

    practice_contribution = models.IntegerField(min=0, max=20, label='How many of your 20 points do you put in the public-services fund?', blank=True)
    practice_tax = models.IntegerField(min=0, max=20, label='How many of each member\'s 20 points must go into the public-services fund?', blank=True)
    practice_rent = models.IntegerField(min=0, max=20, label='How many fund points do you move to your own payoff?', blank=True)
    comprehension_1 = models.StringField(
        choices=[['individual', 'Each member chooses how many of their own points to put in the fund'], ['executive', 'One selected person chooses the amount for every member']],
        widget=widgets.RadioSelect,
        label='With Each person chooses, who decides how many points each member puts in the public-services fund?',
        blank=True,
    )
    comprehension_2 = models.StringField(
        choices=[['yes', 'Yes'], ['no', 'No']], widget=widgets.RadioSelect,
        label='With One person chooses for the group, can the selected person move fund points to their own payoff?',
        blank=True,
    )
    comprehension_3 = models.StringField(
        choices=[['all', 'Every round'], ['selected', 'Only the randomly selected round'], ['last', 'Only Round 10']],
        widget=widgets.RadioSelect,
        label='Which paid round determines your game earnings from Block 1?',
        blank=True,
    )

class Wave1Intro(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def vars_for_template(player):
        return dict(
            rounds=C.NUM_ROUNDS,
            group_size=C.GROUP_SIZE,
        )


class PracticeIntro(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1


class PracticeDemocratic(Page):
    form_model = 'player'
    form_fields = ['practice_contribution']
    template_name = 'wave1_threat/PracticeDemocratic.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, PracticeDemocratic.form_fields)


class PracticeExecutive(Page):
    form_model = 'player'
    form_fields = ['practice_tax', 'practice_rent']
    template_name = 'wave1_threat/PracticeVote.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def error_message(player, values):
        missing = require_all(player, values, PracticeExecutive.form_fields)
        if missing:
            return missing
        if values.get('practice_rent') is not None and values.get('practice_tax') is not None:
            if values['practice_rent'] > C.GROUP_SIZE * values['practice_tax']:
                return 'The decision-maker cannot move more points than the group has put in the public-services fund.'


class Comprehension(Page):
    form_model = 'player'
    form_fields = ['comprehension_1', 'comprehension_2', 'comprehension_3']
    template_name = 'wave1_threat/PracticeComplete.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def error_message(player, values):
        if development_mode(player):
            return
        errors = []
        if values['comprehension_1'] != 'individual':
            errors.append('With Each person chooses, every member chooses how many of their own points to put in the public-services fund.')
        if values['comprehension_2'] != 'yes':
            errors.append('With One person chooses for the group, the selected person can move fund points to their own payoff.')
        if values['comprehension_3'] != 'selected':
            errors.append('One randomly selected round determines your Block-1 game earnings.')
        if errors:
            return 'Please review: ' + ' '.join(errors)


class StrategicExpectations(Page):
    form_model = 'player'
    form_fields = [
        'expected_payoff_citizens',
        'expected_payoff_leader',
        'expected_leader_transfer',
    ]
    template_name = 'wave1_threat/QuestionPage.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='What do you expect in this round?',
            explanation=(
                'Before choosing, estimate what you would earn under each method and '
                'what the selected decision-maker would do. Enter your best estimates; these answers do not '
                'change your payoff.'
            ),
            slider_prefix='',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, StrategicExpectations.form_fields)


class InstitutionVote(Page):
    form_model = 'player'
    form_fields = ['institution_vote', 'solo_other_leader_votes']
    template_name = 'wave1_threat/BeginMainStudy.html'
    timeout_seconds = 90

    @staticmethod
    def vars_for_template(player):
        return dict(
            round_number=player.round_number,
            total_rounds=C.NUM_ROUNDS,
            constrained_multiplier=f'{C.CONSTRAINED_MULTIPLIER_CRISIS:.2f}',
            executive_multiplier=f'{C.EXECUTIVE_MULTIPLIER:.2f}',
            optional_responses=development_mode(player),
            selected_vote=player.field_maybe_none('institution_vote'),
            solo_testing=solo_testing(player),
            solo_other_leader_votes=(
                player.field_maybe_none('solo_other_leader_votes')
                if player.field_maybe_none('solo_other_leader_votes') is not None else 2
            ),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, ['institution_vote'])

    @staticmethod
    def before_next_page(player, timeout_happened):
        if solo_testing(player) and player.field_maybe_none('solo_other_leader_votes') is None:
            player.solo_other_leader_votes = 2
        if timeout_happened or not player.field_maybe_none('institution_vote'):
            player.institution_vote = random.choice([C.CONSTRAINED, C.EXECUTIVE])
            player.timed_out = True
            player.institution_vote_timed_out = True


class VoteWaitPage(WaitPage):
    body_text = 'Waiting for the other members of this round\'s anonymous group.'
    after_all_players_arrive = choose_institution


class DemocraticContribution(Page):
    form_model = 'player'
    form_fields = ['contribution']
    template_name = 'wave1_threat/QuestionPage.html'
    timeout_seconds = 90

    @staticmethod
    def is_displayed(player):
        return player.group.selected_institution == C.CONSTRAINED

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='Each person chooses',
            explanation=(
                f'Points you do not put in the public-services fund remain yours. Each point you put '
                f'in the fund creates {C.CONSTRAINED_MULTIPLIER_CRISIS:.2f} group points. '
                f'These points are shared equally among all five members.'
            ),
            slider_prefix='',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, DemocraticContribution.form_fields)

    @staticmethod
    def before_next_page(player, timeout_happened):
        if timeout_happened or player.field_maybe_none('contribution') is None:
            player.contribution = C.DEFAULT_CONTRIBUTION
            player.timed_out = True


class ExecutiveDecision(Page):
    form_model = 'player'
    form_fields = ['executive_tax', 'executive_rent']
    template_name = 'wave1_threat/QuestionPage.html'
    timeout_seconds = 90

    @staticmethod
    def is_displayed(player):
        return player.group.selected_institution == C.EXECUTIVE and player.is_executive

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='You are the decision-maker for this round',
            explanation=(
                f'Choose how many points every group member must put in the public-services fund. You may '
                f'move at most {C.MAX_EXECUTIVE_RENT} fund points to your own payoff. '
                f'Each point left in the fund creates {C.EXECUTIVE_MULTIPLIER:.2f} group points.'
            ),
            slider_prefix='',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        missing = require_all(player, values, ExecutiveDecision.form_fields)
        if missing:
            return missing
        if values.get('executive_rent') is not None and values.get('executive_tax') is not None:
            if values['executive_rent'] > C.GROUP_SIZE * values['executive_tax']:
                return 'You cannot move more points than the group has put in the public-services fund.'

    @staticmethod
    def before_next_page(player, timeout_happened):
        if timeout_happened or player.field_maybe_none('executive_tax') is None:
            player.executive_tax = C.DEFAULT_EXECUTIVE_TAX
            player.executive_rent = C.DEFAULT_EXECUTIVE_RENT
            player.timed_out = True


class DecisionWaitPage(WaitPage):
    body_text = 'Waiting for all decisions in this round.'
    after_all_players_arrive = calculate_round


class RoundResults(Page):
    template_name = 'wave1_threat/Results.html'

    @staticmethod
    def vars_for_template(player):
        group = player.group
        return dict(
            round_number=player.round_number,
            total_rounds=C.NUM_ROUNDS,
            institution_label=dict(C.INSTITUTION_CHOICES)[group.selected_institution],
            citizen_votes=C.GROUP_SIZE - group.executive_votes,
            leader_votes=group.executive_votes,
            solo_testing=solo_testing(player),
            executive_selected=group.selected_institution == C.EXECUTIVE,
            is_executive=player.id_in_group == group.executive_id,
            total_contribution=group.total_contribution,
            executive_tax=group.executive_tax,
            executive_rent=group.executive_rent,
            public_account=group.public_account,
            per_capita_return=group.per_capita_return,
            round_payoff=player.round_payoff,
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        if player.round_number != C.NUM_ROUNDS:
            return
        player.participant.vars['w1_final_vote'] = player.institution_vote
        player.participant.vars['w1_final_vote_observed'] = not player.institution_vote_timed_out
        late_votes = [p.institution_vote for p in player.in_rounds(8, 10)]
        player.participant.vars['w1_late_executive_share'] = sum(v == C.EXECUTIVE for v in late_votes) / 3
        player.participant.vars['expected_payoff_citizens_b1'] = (
            player.field_maybe_none('expected_payoff_citizens')
        )
        player.participant.vars['expected_payoff_leader_b1'] = (
            player.field_maybe_none('expected_payoff_leader')
        )
        player.participant.vars['expected_leader_transfer_b1'] = (
            player.field_maybe_none('expected_leader_transfer')
        )

        paying_round = player.session.vars['wave1_paying_round']
        selected_payoff = player.in_round(paying_round).round_payoff
        player.payoff = cu(selected_payoff)
        player.participant.vars['wave1_paying_round'] = paying_round
        player.participant.vars['wave1_selected_payoff'] = selected_payoff


class Wave1Complete(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS

    @staticmethod
    def vars_for_template(player):
        return dict(
            paying_round=player.participant.vars['wave1_paying_round'],
            selected_payoff=player.participant.vars['wave1_selected_payoff'],
        )


page_sequence = [
    Wave1Intro,
    PracticeIntro,
    PracticeDemocratic,
    PracticeExecutive,
    Comprehension,
    StrategicExpectations,
    InstitutionVote,
    VoteWaitPage,
    DemocraticContribution,
    ExecutiveDecision,
    DecisionWaitPage,
    RoundResults,
    Wave1Complete,
]

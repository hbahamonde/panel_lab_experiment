import random

from otree.api import *


doc = """
Block 1 of the one-session experiment: a common low-capacity environment, ten
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
            player.participant.vars['times_executive'] = 0
            player.participant.vars['treatment'] = subsession.session.config.get(
                'solo_treatment', 'reversal'
            )
            subsession.session.vars['wave1_paying_round'] = random.randint(1, C.NUM_ROUNDS)
        subsession.set_group_matrix([[player]])
        player.matching_pool_id = 1
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
            player.participant.vars['times_executive'] = 0

        pool_ids = sorted({p.participant.vars['matching_pool_id'] for p in shuffled})
        randomized_pool_ids = random.sample(pool_ids, len(pool_ids))
        midpoint = (len(randomized_pool_ids) + 1) // 2
        reversal_ids = set(randomized_pool_ids[:midpoint])
        for player in shuffled:
            treatment = 'reversal' if player.participant.vars['matching_pool_id'] in reversal_ids else 'control'
            player.participant.vars['treatment'] = treatment

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
    INSTITUTION_CHOICES = [
        [CONSTRAINED, 'Citizens decide'],
        [EXECUTIVE, 'A leader decides'],
    ]

    AGREEMENT_CHOICES = [[i, str(i)] for i in range(1, 8)]
    FIVE_POINT_CHOICES = [
        [1, 'Very low'], [2, 'Low'], [3, 'Moderate'], [4, 'High'], [5, 'Very high']
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
    institution_vote = models.StringField(
        choices=C.INSTITUTION_CHOICES,
        widget=widgets.RadioSelect,
        label='Who should make the public-service decision this round?',
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
        label='How many points must each citizen put in the public-services fund?',
        blank=True,
    )
    executive_rent = models.IntegerField(
        min=0, max=C.MAX_EXECUTIVE_RENT,
        label='How many points do you move from the public-services fund to your personal account?',
        blank=True,
    )
    is_executive = models.BooleanField(initial=False)
    timed_out = models.BooleanField(initial=False)
    round_payoff = models.FloatField(initial=0)

    inst_capacity_pre = models.IntegerField(
        choices=C.FIVE_POINT_CHOICES, widget=widgets.RadioSelect,
        label='At this point, how well can the group support public services when each citizen chooses how many points to put in the fund?',
        blank=True,
    )
    collapse_risk_pre = models.IntegerField(
        choices=C.FIVE_POINT_CHOICES, widget=widgets.RadioSelect,
        label='At this point, how high is the risk that the usual limits on a leader\'s power will be seriously weakened?',
        blank=True,
    )

    constraint_pre_1 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='A crisis can justify giving one leader temporary power to act without asking the group first.', blank=True)
    constraint_pre_2 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Faster public services can be worth reducing checks on a leader\'s power.', blank=True)
    constraint_pre_3 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Citizens should keep control over major public decisions, even if decisions take longer.', blank=True)
    constraint_pre_4 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='A leader should be allowed to require every citizen to put the same number of points in the public-services fund.', blank=True)
    constraint_pre_5 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='I prefer slower decisions by citizens to faster decisions by a leader who may move public-service points to a personal account.', blank=True)
    constraint_pre_6 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Weak limits on a leader\'s power create risks that outweigh short-term gains.', blank=True)
    constraint_pre_7 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='When public services work poorly, a leader should have more freedom from the usual limits.', blank=True)

    practice_contribution = models.IntegerField(min=0, max=10, label='How many of your 10 points do you put in the public-services fund?', blank=True)
    practice_tax = models.IntegerField(min=0, max=10, label='How many points must each citizen put in the public-services fund?', blank=True)
    practice_rent = models.IntegerField(min=0, max=10, label='How many points do you move from the fund to your personal account?', blank=True)
    comprehension_1 = models.StringField(
        choices=[['individual', 'Each citizen chooses how many of their own points to put in the fund'], ['executive', 'One leader chooses the amount for every citizen']],
        widget=widgets.RadioSelect,
        label='When citizens decide, who chooses how many points each person puts in the public-services fund?',
        blank=True,
    )
    comprehension_2 = models.StringField(
        choices=[['yes', 'Yes'], ['no', 'No']], widget=widgets.RadioSelect,
        label='Can the leader move points from the public-services fund to their personal account?',
        blank=True,
    )
    comprehension_3 = models.StringField(
        choices=[['all', 'Every round'], ['selected', 'Only the randomly selected round'], ['last', 'Only Round 10']],
        widget=widgets.RadioSelect,
        label='Which paid round determines your game earnings from Block 1?',
        blank=True,
    )

    inst_capacity_w1 = models.IntegerField(
        choices=C.FIVE_POINT_CHOICES, widget=widgets.RadioSelect,
        label='After these rounds, how well can the group support public services when each citizen chooses how many points to put in the fund?',
        blank=True,
    )
    collapse_risk_w1 = models.IntegerField(
        choices=C.FIVE_POINT_CHOICES, widget=widgets.RadioSelect,
        label='After these rounds, how high is the risk that the usual limits on a leader\'s power will be seriously weakened?',
        blank=True,
    )
    constraint_w1_1 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='The current crisis justifies giving one leader temporary power to act without asking the group first.', blank=True)
    constraint_w1_2 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Faster public services are worth reducing checks on a leader\'s power in the current situation.', blank=True)
    constraint_w1_3 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Citizens should keep control over major public decisions, even if decisions take longer.', blank=True)
    constraint_w1_4 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='The leader should be allowed to require every citizen to put the same number of points in the public-services fund.', blank=True)
    constraint_w1_5 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='I prefer slower decisions by citizens to faster decisions by a leader who may move public-service points to a personal account.', blank=True)
    constraint_w1_6 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Weak limits on a leader\'s power create risks that outweigh the current gains.', blank=True)
    constraint_w1_7 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Because public services are working poorly, a leader needs more freedom from the usual limits.', blank=True)


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


class BaselineSurvey(Page):
    form_model = 'player'
    form_fields = [
        'inst_capacity_pre', 'collapse_risk_pre',
        'constraint_pre_1', 'constraint_pre_2', 'constraint_pre_3', 'constraint_pre_4',
        'constraint_pre_5', 'constraint_pre_6', 'constraint_pre_7',
    ]
    template_name = 'wave1_threat/QuestionPage.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='Your first impressions',
            explanation='Please answer the two questions about public services first.',
            slider_prefix='constraint_pre_',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, BaselineSurvey.form_fields)


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
                return 'The leader cannot move more points than the group has put in the public-services fund.'


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
            errors.append('When citizens decide, each citizen chooses how many of their own points to put in the public-services fund.')
        if values['comprehension_2'] != 'yes':
            errors.append('The leader can move points from the public-services fund to their personal account.')
        if values['comprehension_3'] != 'selected':
            errors.append('One randomly selected round determines your Block-1 game earnings.')
        if errors:
            return 'Please review: ' + ' '.join(errors)


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
            player.institution_vote = C.CONSTRAINED
            player.timed_out = True


class VoteWaitPage(WaitPage):
    body_text = 'Waiting for the other citizens in this round\'s anonymous group.'
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
            page_title='Citizens decide',
            explanation=(
                f'Points you do not put in the public-services fund remain yours. Each point you put '
                f'in the fund creates {C.CONSTRAINED_MULTIPLIER_CRISIS:.2f} points for the group. '
                f'The resulting return is divided equally among all five citizens.'
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
            player.contribution = 0
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
            page_title='You are the leader for this round',
            explanation=(
                f'Choose how many points every citizen must put in the public-services fund. You may '
                f'move at most {C.MAX_EXECUTIVE_RENT} points from that fund to your personal account. '
                f'Each point left in the fund creates {C.EXECUTIVE_MULTIPLIER:.2f} points for the group.'
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
            player.executive_tax = 0
            player.executive_rent = 0
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


class Wave1Mechanism(Page):
    form_model = 'player'
    form_fields = [
        'inst_capacity_w1', 'collapse_risk_w1',
        'constraint_w1_1', 'constraint_w1_2', 'constraint_w1_3', 'constraint_w1_4',
        'constraint_w1_5', 'constraint_w1_6', 'constraint_w1_7',
    ]
    template_name = 'wave1_threat/QuestionPage.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='Your views after Block 1',
            explanation='Please answer after considering the first ten rounds.',
            slider_prefix='constraint_w1_',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, Wave1Mechanism.form_fields)

    @staticmethod
    def before_next_page(player, timeout_happened):
        player.participant.vars['w1_final_vote'] = player.institution_vote
        late_votes = [p.institution_vote for p in player.in_rounds(8, 10)]
        player.participant.vars['w1_late_executive_share'] = sum(v == C.EXECUTIVE for v in late_votes) / 3
        player.participant.vars['inst_capacity_w1'] = player.field_maybe_none('inst_capacity_w1')
        player.participant.vars['collapse_risk_w1'] = player.field_maybe_none('collapse_risk_w1')

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
    BaselineSurvey,
    PracticeIntro,
    PracticeDemocratic,
    PracticeExecutive,
    Comprehension,
    InstitutionVote,
    VoteWaitPage,
    DemocraticContribution,
    ExecutiveDecision,
    DecisionWaitPage,
    RoundResults,
    Wave1Mechanism,
    Wave1Complete,
]

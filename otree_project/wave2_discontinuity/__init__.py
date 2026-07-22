import random
from datetime import date, datetime, timedelta

from otree.api import *


doc = """
Wave 2: pre-refresh memory measurement, a pool-randomized structural recovery
or persistence condition, ten repeated institutional-choice rounds, and the
final two-wave democratic-reversal outcome.
"""


def wave_status(player):
    if not player.session.config.get('enable_wave_gates', False):
        return 'open'
    wave_date = datetime.fromisoformat(player.session.config['wave2_date']).date()
    deadline = wave_date + timedelta(days=player.session.config['wave_window_days'] - 1)
    if date.today() < wave_date:
        return 'early'
    if date.today() > deadline:
        return 'late'
    return 'open'


def study_schedule(session):
    wave2 = datetime.fromisoformat(session.config['wave2_date']).date()
    deadline = wave2 + timedelta(days=session.config['wave_window_days'] - 1)
    return dict(
        wave2_date_display=wave2.strftime('%B %d, %Y'),
        wave2_deadline_display=deadline.strftime('%B %d, %Y'),
    )


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


def group_within_matching_pools(subsession):
    players = subsession.get_players()

    if solo_testing(subsession):
        if len(players) != 1:
            raise RuntimeError('Solo testing sessions require exactly one participant.')
        player = players[0]
        subsession.set_group_matrix([[player]])
        player.matching_pool_id = player.participant.vars['matching_pool_id']
        player.treatment = player.participant.vars['treatment']
        if subsession.round_number == 1:
            subsession.session.vars['wave2_paying_round'] = random.randint(1, C.NUM_ROUNDS)
        return

    groups = []
    pool_ids = sorted({p.participant.vars['matching_pool_id'] for p in players})
    for pool_id in pool_ids:
        pool_players = [p for p in players if p.participant.vars['matching_pool_id'] == pool_id]
        random.shuffle(pool_players)
        if len(pool_players) % C.GROUP_SIZE != 0:
            raise RuntimeError(
                f'Matching pool {pool_id} contains {len(pool_players)} participants; '
                'Wave 2 requires complete five-person groups.'
            )
        groups.extend(
            pool_players[index:index + C.GROUP_SIZE]
            for index in range(0, len(pool_players), C.GROUP_SIZE)
        )
    subsession.set_group_matrix(groups)
    for player in players:
        player.matching_pool_id = player.participant.vars['matching_pool_id']
        player.treatment = player.participant.vars['treatment']

    if subsession.round_number == 1:
        subsession.session.vars['wave2_paying_round'] = random.randint(1, C.NUM_ROUNDS)


def constrained_multiplier(player):
    if player.treatment == C.TREATMENT_REVERSAL:
        return C.CONSTRAINED_MULTIPLIER_RECOVERY
    return C.CONSTRAINED_MULTIPLIER_CRISIS


def choose_institution(group):
    players = group.get_players()
    if solo_testing(group):
        player = players[0]
        other_leader_votes = player.field_maybe_none('solo_other_leader_votes')
        executive_votes = int(player.institution_vote == C.EXECUTIVE) + (
            other_leader_votes if other_leader_votes is not None else 2
        )
    else:
        executive_votes = sum(p.institution_vote == C.EXECUTIVE for p in players)
    group.executive_votes = executive_votes
    group.selected_institution = C.EXECUTIVE if executive_votes >= 3 else C.CONSTRAINED
    group.realized_constrained_multiplier = constrained_multiplier(players[0])

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
        group.per_capita_return = group.realized_constrained_multiplier * total / C.GROUP_SIZE
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
    NAME_IN_URL = 'wave2_discontinuity'
    PLAYERS_PER_GROUP = None
    GROUP_SIZE = 5
    NUM_ROUNDS = 10

    ENDOWMENT = 20
    CONSTRAINED_MULTIPLIER_CRISIS = 1.50
    CONSTRAINED_MULTIPLIER_RECOVERY = 2.50
    EXECUTIVE_MULTIPLIER = 2.50
    MAX_EXECUTIVE_RENT = 20
    COMPLETION_BONUS = 25
    SOLO_OTHER_CITIZENS = 4
    SOLO_OTHER_CONTRIBUTION = 10

    CONSTRAINED = 'constrained'
    EXECUTIVE = 'executive'
    TREATMENT_REVERSAL = 'reversal'
    TREATMENT_CONTROL = 'control'

    INSTITUTION_CHOICES = [
        [CONSTRAINED, 'Citizens decide'],
        [EXECUTIVE, 'A leader decides'],
    ]
    AGREEMENT_CHOICES = [[i, str(i)] for i in range(1, 8)]
    FIVE_POINT_CHOICES = [
        [1, 'Very low'], [2, 'Low'], [3, 'Moderate'], [4, 'High'], [5, 'Very high']
    ]
    MEMORY_CAPACITY_CHOICES = [
        ['low', 'They were working poorly'], ['moderate', 'They were working moderately well'],
        ['high', 'They were working well'], ['unsure', 'I do not remember'],
    ]
    MEMORY_VOTE_CHOICES = [
        [CONSTRAINED, 'Citizens decide'],
        [EXECUTIVE, 'A leader decides'],
        ['unsure', 'I do not remember'],
    ]

class Subsession(BaseSubsession):
    pass


def creating_session(subsession: Subsession):
    group_within_matching_pools(subsession)


class Group(BaseGroup):
    selected_institution = models.StringField()
    executive_votes = models.IntegerField(initial=0)
    executive_id = models.IntegerField(initial=0)
    total_contribution = models.IntegerField(initial=0)
    executive_tax = models.IntegerField(initial=0)
    executive_rent = models.IntegerField(initial=0)
    public_account = models.IntegerField(initial=0)
    per_capita_return = models.FloatField(initial=0)
    realized_constrained_multiplier = models.FloatField(initial=0)


class Player(BasePlayer):
    matching_pool_id = models.IntegerField()
    treatment = models.StringField()
    institution_vote = models.StringField(
        choices=C.INSTITUTION_CHOICES, widget=widgets.RadioSelect,
        label='Who should make the public-service decision this round?',
        blank=True,
    )
    solo_other_leader_votes = models.IntegerField(min=0, max=4, blank=True)
    contribution = models.IntegerField(
        min=0, max=C.ENDOWMENT, blank=True,
        label='How many of your 20 points do you place in the public-service account?',
    )
    executive_tax = models.IntegerField(
        min=0, max=C.ENDOWMENT, blank=True,
        label='How many points must each citizen contribute?',
    )
    executive_rent = models.IntegerField(
        min=0, max=C.MAX_EXECUTIVE_RENT, blank=True,
        label='How many collected points do you keep for yourself?',
    )
    is_executive = models.BooleanField(initial=False)
    timed_out = models.BooleanField(initial=False)
    round_payoff = models.FloatField(initial=0)

    memory_free_recall = models.LongStringField(
        label='Without reopening earlier material, what do you remember about the society and the group task in Session 1?',
        blank=True,
    )
    memory_w1_capacity = models.StringField(
        choices=C.MEMORY_CAPACITY_CHOICES, widget=widgets.RadioSelect,
        label='How well were public services working in Session 1?',
        blank=True,
    )
    memory_w1_vote = models.StringField(
        choices=C.MEMORY_VOTE_CHOICES, widget=widgets.RadioSelect,
        label='Which option did you choose in the final round of Session 1?',
        blank=True,
    )
    belief_recovery_pre = models.IntegerField(
        min=0, max=100,
        label='At the start of Session 2, what is the probability (0--100) that public services have recovered since Session 1?',
        blank=True,
    )

    inst_capacity_w2 = models.IntegerField(
        choices=C.FIVE_POINT_CHOICES, widget=widgets.RadioSelect,
        label='After these rounds, how well can citizens provide public services when each citizen chooses their own contribution?',
        blank=True,
    )
    collapse_risk_w2 = models.IntegerField(
        choices=C.FIVE_POINT_CHOICES, widget=widgets.RadioSelect,
        label='After these rounds, how high is the risk that the usual limits on a leader\'s power will be seriously weakened?',
        blank=True,
    )
    belief_recovery_final = models.IntegerField(
        min=0, max=100,
        label='After all ten rounds, what is the probability (0--100) that public services recovered before Session 2?',
        blank=True,
    )
    constraint_w2_1 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='The current situation justifies giving one leader temporary power to act without asking the group first.', blank=True)
    constraint_w2_2 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Faster public services are worth reducing checks on a leader\'s power in the current situation.', blank=True)
    constraint_w2_3 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Citizens should keep control over major public decisions, even if decisions take longer.', blank=True)
    constraint_w2_4 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='The leader should be allowed to require equal contributions in the current situation.', blank=True)
    constraint_w2_5 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='I prefer slower decisions by citizens to faster decisions by a leader who may keep some collected points.', blank=True)
    constraint_w2_6 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Weak limits on a leader\'s power create risks that outweigh the current gains.', blank=True)
    constraint_w2_7 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='When public services work poorly, a leader needs more freedom from the usual limits.', blank=True)

    democratic_reversal = models.BooleanField(initial=False)


class Wave2LockedEarly(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1 and wave_status(player) == 'early'

    @staticmethod
    def vars_for_template(player):
        return study_schedule(player.session)


class Wave2LockedLate(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1 and wave_status(player) == 'late'

    @staticmethod
    def vars_for_template(player):
        return study_schedule(player.session)


class Wave2Intro(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1 and wave_status(player) == 'open'

    @staticmethod
    def vars_for_template(player):
        return dict(
            rounds=C.NUM_ROUNDS,
        )


class MemoryAndPrior(Page):
    form_model = 'player'
    form_fields = ['memory_free_recall', 'memory_w1_capacity', 'memory_w1_vote', 'belief_recovery_pre']
    template_name = 'wave2_discontinuity/TreatmentReveal.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1 and wave_status(player) == 'open'

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, MemoryAndPrior.form_fields)


class InstitutionVote(Page):
    form_model = 'player'
    form_fields = ['institution_vote', 'solo_other_leader_votes']
    template_name = 'wave2_discontinuity/QuestionPage.html'
    timeout_seconds = 90

    @staticmethod
    def is_displayed(player):
        return wave_status(player) == 'open'

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title=f'Session 2 — Round {player.round_number} of {C.NUM_ROUNDS}',
            explanation=(
                'Vote privately. Public services may have recovered or may still be under strain. The leader '
                'option has not changed. This round may be selected for payment.'
            ),
            institution_vote_page=True,
            constrained_multiplier='1.50 or 2.50',
            executive_multiplier=f'{C.EXECUTIVE_MULTIPLIER:.2f}',
            optional_responses=development_mode(player),
            selected_vote=player.field_maybe_none('institution_vote'),
            slider_prefix='',
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

    @staticmethod
    def is_displayed(player):
        return wave_status(player) == 'open'


class DemocraticContribution(Page):
    form_model = 'player'
    form_fields = ['contribution']
    template_name = 'wave2_discontinuity/QuestionPage.html'
    timeout_seconds = 90

    @staticmethod
    def is_displayed(player):
        return wave_status(player) == 'open' and player.group.selected_institution == C.CONSTRAINED

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='Citizens decide',
            explanation=(
                'Each point kept returns 1 point to you. Depending on how well public services now work, each '
                'point contributed produces either 1.50 or 2.50 points for the group in total. The return is '
                'divided equally among all five citizens.'
            ),
            institution_vote_page=False,
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
    template_name = 'wave2_discontinuity/QuestionPage.html'
    timeout_seconds = 90

    @staticmethod
    def is_displayed(player):
        return wave_status(player) == 'open' and player.group.selected_institution == C.EXECUTIVE and player.is_executive

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='You are the leader for this round',
            explanation=(
                f'Choose the contribution required from all five citizens. You may keep at most '
                f'{C.MAX_EXECUTIVE_RENT} collected points for yourself. Each remaining point produces '
                f'{C.EXECUTIVE_MULTIPLIER:.2f} points for the group in total.'
            ),
            institution_vote_page=False,
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
                return 'You cannot keep more points than the group contributes.'

    @staticmethod
    def before_next_page(player, timeout_happened):
        if timeout_happened or player.field_maybe_none('executive_tax') is None:
            player.executive_tax = 0
            player.executive_rent = 0
            player.timed_out = True


class DecisionWaitPage(WaitPage):
    body_text = 'Waiting for all decisions in this round.'
    after_all_players_arrive = calculate_round

    @staticmethod
    def is_displayed(player):
        return wave_status(player) == 'open'


class RoundResults(Page):
    template_name = 'wave2_discontinuity/Results.html'

    @staticmethod
    def is_displayed(player):
        return wave_status(player) == 'open'

    @staticmethod
    def vars_for_template(player):
        group = player.group
        return dict(
            round_number=player.round_number,
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
            constrained_multiplier=group.realized_constrained_multiplier,
        )


class Wave2Mechanism(Page):
    form_model = 'player'
    form_fields = [
        'inst_capacity_w2', 'collapse_risk_w2', 'belief_recovery_final',
        'constraint_w2_1', 'constraint_w2_2', 'constraint_w2_3', 'constraint_w2_4',
        'constraint_w2_5', 'constraint_w2_6', 'constraint_w2_7',
    ]
    template_name = 'wave2_discontinuity/QuestionPage.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS and wave_status(player) == 'open'

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='Your final views',
            explanation='Please answer after considering all ten rounds in Session 2.',
            institution_vote_page=False,
            slider_prefix='constraint_w2_',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, Wave2Mechanism.form_fields)

    @staticmethod
    def before_next_page(player, timeout_happened):
        w1_vote = player.participant.vars.get('w1_final_vote')
        w2_vote = player.institution_vote
        player.democratic_reversal = w1_vote == C.EXECUTIVE and w2_vote == C.CONSTRAINED
        player.participant.vars['w2_final_vote'] = w2_vote
        player.participant.vars['democratic_reversal'] = player.democratic_reversal
        late_votes = [p.institution_vote for p in player.in_rounds(8, 10)]
        player.participant.vars['w2_late_executive_share'] = sum(v == C.EXECUTIVE for v in late_votes) / 3

        paying_round = player.session.vars['wave2_paying_round']
        selected_payoff = player.in_round(paying_round).round_payoff
        player.payoff = cu(selected_payoff + C.COMPLETION_BONUS)

        player.participant.vars['wave2_paying_round'] = paying_round
        player.participant.vars['wave2_selected_payoff'] = selected_payoff


class Wave2Complete(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS and wave_status(player) == 'open'

    @staticmethod
    def vars_for_template(player):
        return dict(
            paying_round=player.participant.vars['wave2_paying_round'],
            selected_payoff=player.participant.vars['wave2_selected_payoff'],
            wave1_selected_payoff=player.participant.vars.get('wave1_selected_payoff', 0),
            completion_bonus=C.COMPLETION_BONUS,
            total_payoff=player.participant.payoff,
            performance_payment=player.participant.payoff.to_real_world_currency(player.session),
            participation_fee=player.session.config['participation_fee'],
            total_payment=player.participant.payoff_plus_participation_fee(),
        )


page_sequence = [
    Wave2LockedEarly,
    Wave2LockedLate,
    Wave2Intro,
    MemoryAndPrior,
    InstitutionVote,
    VoteWaitPage,
    DemocraticContribution,
    ExecutiveDecision,
    DecisionWaitPage,
    RoundResults,
    Wave2Mechanism,
    Wave2Complete,
]

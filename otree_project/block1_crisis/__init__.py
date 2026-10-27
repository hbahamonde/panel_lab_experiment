import random
import time

from otree.api import *


doc = """
Block 1 of the one-session experiment: a common public-service crisis, ten
repeated institutional-choice/public-good rounds and process measurement.
Participants play within stable pools of 5, 10, or 15. Larger pools are
anonymously rematched into five-person groups before each round.
"""


def development_mode(player):
    """Allow researchers to move through the demo without completing every field."""
    return player.session.config.get('allow_optional_responses', False)


def require_all(player, values, field_names):
    if development_mode(player):
        return
    if any(values.get(field_name) in (None, '') for field_name in field_names):
        return 'Vastaa kaikkiin kysymyksiin ennen kuin jatkat.'


def solo_testing(obj):
    return obj.session.config.get('solo_testing', False)


def format_rate(value):
    """Format a displayed rate without changing the numerical value used in play."""
    return f'{value:.2f}'.replace('.', ',')


def flexible_pool_sizes(player_count):
    """Return the approved matching-pool structure for a production roster."""
    approved_rosters = {
        5: [5],
        10: [10],
        15: [15],
        20: [10, 10],
    }
    try:
        return approved_rosters[player_count]
    except KeyError as exc:
        raise RuntimeError(
            'Production sessions require exactly 5, 10, 15, or 20 participants. '
            f'This session was created with {player_count}.'
        ) from exc


def start_decision_timer(player, decision_name):
    key = f'block1_round_{player.round_number}_{decision_name}_started_at'
    started_at = player.participant.vars.setdefault(key, time.time())
    return dict(decision_reminder=dict(
        remaining_seconds=max(
            0, C.DECISION_DELAY_THRESHOLD_SECONDS - (time.time() - started_at)
        ),
        guide_seconds=C.DECISION_DELAY_THRESHOLD_SECONDS,
    ))


def record_decision_time(player, decision_name, seconds_field, flag_field):
    key = f'block1_round_{player.round_number}_{decision_name}_started_at'
    started_at = player.participant.vars.pop(key, time.time())
    elapsed = max(0, time.time() - started_at)
    setattr(player, seconds_field, elapsed)
    setattr(player, flag_field, elapsed > C.DECISION_DELAY_THRESHOLD_SECONDS)


def assign_matching_pools(subsession):
    players = subsession.get_players()

    if solo_testing(subsession):
        if len(players) != 1:
            raise RuntimeError('Solo testing sessions require exactly one participant.')
        player = players[0]
        if subsession.round_number == 1:
            player.participant.vars['matching_pool_id'] = 1
            player.participant.vars['matching_pool_uid'] = f'{subsession.session.code}-pool-1'
            player.participant.vars['matching_pool_size'] = 1
            subsession.session.vars['block1_paying_round'] = random.randint(1, C.NUM_ROUNDS)
        subsession.set_group_matrix([[player]])
        player.matching_pool_id = 1
        player.matching_pool_uid = player.participant.vars['matching_pool_uid']
        player.matching_pool_size = 1
        return

    if subsession.round_number == 1:
        pool_sizes = flexible_pool_sizes(len(players))
        subsession.session.vars['matching_pool_sizes'] = pool_sizes
        shuffled = random.sample(players, len(players))
        position = 0
        for pool_id, pool_size in enumerate(pool_sizes, start=1):
            pool_members = shuffled[position:position + pool_size]
            position += pool_size
            for player in pool_members:
                player.participant.vars['matching_pool_id'] = pool_id
                player.participant.vars['matching_pool_uid'] = (
                    f'{subsession.session.code}-pool-{pool_id}'
                )
                player.participant.vars['matching_pool_size'] = pool_size

        subsession.session.vars['block1_paying_round'] = random.randint(1, C.NUM_ROUNDS)

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
        player.matching_pool_size = player.participant.vars['matching_pool_size']


def choose_institution_and_leader(group):
    players = group.get_players()
    if solo_testing(group):
        player = players[0]
        other_automatic_votes = player.field_maybe_none('solo_other_automatic_votes')
        automatic_votes = int(player.field_maybe_none('institution_vote') == C.AUTOMATIC) + (
            other_automatic_votes if other_automatic_votes is not None else 2
        )
    else:
        if len(players) != C.GROUP_SIZE:
            raise RuntimeError(
                f'Paid groups must contain exactly {C.GROUP_SIZE} participants.'
            )
        if any(p.field_maybe_none('institution_vote') is None for p in players):
            raise RuntimeError(
                'An institutional ballot is missing. No institutional choice was imputed.'
            )
        automatic_votes = sum(
            p.field_maybe_none('institution_vote') == C.AUTOMATIC for p in players
        )
    group.automatic_votes = automatic_votes
    group.selected_institution = C.AUTOMATIC if automatic_votes >= 3 else C.APPROVAL

    if solo_testing(group):
        player = players[0]
        if player.round_number % 2:
            player.is_leader = True
            group.leader_id = player.id_in_group
        else:
            group.leader_id = 0  # simulated leader; lets one-browser tests show approval
        return

    leader = random.choice(players)
    leader.is_leader = True
    group.leader_id = leader.id_in_group


def record_proposal(group):
    if solo_testing(group) and group.leader_id == 0:
        group.proposed_allocation = 10
        group.proposed_transfer = 5
        return
    leader = group.get_player_by_id(group.leader_id)
    allocation = leader.field_maybe_none('proposed_allocation')
    transfer = leader.field_maybe_none('proposed_transfer')
    if allocation is None or transfer is None:
        raise RuntimeError('The selected person must submit a complete proposal.')
    if not 0 <= allocation <= C.ENDOWMENT:
        raise RuntimeError('The proposed allocation is outside the permitted range.')
    if not 0 <= transfer <= min(C.MAX_PERSONAL_TRANSFER, C.GROUP_SIZE * allocation):
        raise RuntimeError('The proposed transfer is outside the permitted range.')
    group.proposed_allocation = allocation
    group.proposed_transfer = transfer


def decide_approval(group):
    if group.selected_institution != C.APPROVAL:
        group.proposal_approved = False
        return

    if solo_testing(group):
        if group.leader_id == 0:
            participant_approval = (
                group.get_players()[0].field_maybe_none('approval_vote') == C.APPROVE
            )
            group.approval_votes = 2 + int(participant_approval)
        else:
            leader = group.get_player_by_id(group.leader_id)
            simulated_approvals = leader.field_maybe_none('solo_other_approval_votes')
            group.approval_votes = simulated_approvals if simulated_approvals is not None else 3
    else:
        nonleaders = [
            p for p in group.get_players() if p.id_in_group != group.leader_id
        ]
        if len(nonleaders) != C.GROUP_SIZE - 1:
            raise RuntimeError('The group does not have exactly four approval voters.')
        if any(p.field_maybe_none('approval_vote') is None for p in nonleaders):
            raise RuntimeError('An approval vote is missing. No approval was imputed.')
        group.approval_votes = sum(
            p.field_maybe_none('approval_vote') == C.APPROVE for p in nonleaders
        )
    group.proposal_approved = group.approval_votes >= C.APPROVAL_THRESHOLD


def calculate_round(group):
    players = group.get_players()
    proposal_implemented = (
        group.selected_institution == C.AUTOMATIC or group.proposal_approved
    )
    group.proposal_implemented = proposal_implemented
    group.fallback_used = not proposal_implemented

    if group.fallback_used:
        if solo_testing(group):
            total = (players[0].field_maybe_none('contribution') or 0) + C.SOLO_OTHER_CITIZENS * C.SOLO_OTHER_CONTRIBUTION
        else:
            contributions = [p.field_maybe_none('contribution') for p in players]
            if any(contribution is None for contribution in contributions):
                raise RuntimeError(
                    'An individual fund allocation is missing. No allocation was imputed.'
                )
            total = sum(contributions)
        group.total_contribution = total
        group.implemented_transfer = 0
        group.public_account = total
        group.per_capita_return = C.APPROVAL_MULTIPLIER_CRISIS * total / C.GROUP_SIZE
        for player in players:
            player.round_payoff = C.ENDOWMENT - (player.field_maybe_none('contribution') or 0) + group.per_capita_return
    else:
        allocation = group.proposed_allocation
        transfer = group.proposed_transfer
        public_account = C.GROUP_SIZE * allocation - transfer
        multiplier = (
            C.AUTOMATIC_MULTIPLIER
            if group.selected_institution == C.AUTOMATIC
            else C.APPROVAL_MULTIPLIER_CRISIS
        )
        group.total_contribution = C.GROUP_SIZE * allocation
        group.implemented_transfer = transfer
        group.public_account = public_account
        group.per_capita_return = multiplier * public_account / C.GROUP_SIZE
        for player in players:
            player.round_payoff = C.ENDOWMENT - allocation + group.per_capita_return
            if player.id_in_group == group.leader_id:
                player.round_payoff += transfer

    if any(not 0 <= player.round_payoff <= C.MAX_ROUND_PAYOFF for player in players):
        raise RuntimeError('A calculated round payoff is outside the permitted range.')


class C(BaseConstants):
    NAME_IN_URL = 'group_decisions_1'
    PLAYERS_PER_GROUP = None
    GROUP_SIZE = 5
    NUM_ROUNDS = 10

    ENDOWMENT = 20
    APPROVAL_MULTIPLIER_CRISIS = 1.50
    APPROVAL_MULTIPLIER_RECOVERY = 2.50
    AUTOMATIC_MULTIPLIER = 2.50
    MAX_PERSONAL_TRANSFER = 20
    MAX_ROUND_PAYOFF = 60
    APPROVAL_THRESHOLD = 3
    SOLO_OTHER_CITIZENS = 4
    SOLO_OTHER_CONTRIBUTION = 10

    APPROVAL = 'approval'
    AUTOMATIC = 'automatic'
    APPROVE = 'approve'
    REJECT = 'reject'
    TREATMENT_RECOVERY = 'recovery'
    TREATMENT_PERSISTENCE = 'persistence'
    DECISION_DELAY_THRESHOLD_SECONDS = 90
    INSTITUTION_CHOICES = [
        [APPROVAL, 'Ryhmän hyväksyntä vaaditaan'],
        [AUTOMATIC, 'Päätös tulee voimaan suoraan'],
    ]
    APPROVAL_CHOICES = [
        [APPROVE, 'Hyväksyn ehdotuksen'],
        [REJECT, 'Hylkään ehdotuksen'],
    ]

class Subsession(BaseSubsession):
    pass


def creating_session(subsession: Subsession):
    assign_matching_pools(subsession)


class Group(BaseGroup):
    selected_institution = models.StringField()
    automatic_votes = models.IntegerField(initial=0)
    leader_id = models.IntegerField(initial=0)
    proposed_allocation = models.IntegerField(initial=0)
    proposed_transfer = models.IntegerField(initial=0)
    approval_votes = models.IntegerField(initial=0)
    proposal_approved = models.BooleanField(initial=False)
    proposal_implemented = models.BooleanField(initial=False)
    fallback_used = models.BooleanField(initial=False)
    total_contribution = models.IntegerField(initial=0)
    implemented_transfer = models.IntegerField(initial=0)
    public_account = models.IntegerField(initial=0)
    per_capita_return = models.FloatField(initial=0)


class Player(BasePlayer):
    matching_pool_id = models.IntegerField()
    matching_pool_uid = models.StringField()
    matching_pool_size = models.IntegerField()
    institution_vote = models.StringField(
        choices=C.INSTITUTION_CHOICES,
        widget=widgets.RadioSelect,
        label='Pitäisikö valitun henkilön ehdotuksen vaatia ryhmän hyväksyntä?',
        blank=True,
    )
    solo_other_automatic_votes = models.IntegerField(min=0, max=4, blank=True)
    solo_other_approval_votes = models.IntegerField(
        min=0, max=4, blank=True,
        label='Yhden henkilön testi: kuinka moni neljästä simuloidusta kansalaisesta hyväksyy ehdotuksen?',
    )
    contribution = models.IntegerField(
        min=0, max=C.ENDOWMENT,
        label='Kuinka monta 20 pisteestäsi laitat julkisten palvelujen rahastoon?',
        blank=True,
    )
    proposed_allocation = models.IntegerField(
        min=0, max=C.ENDOWMENT,
        label='Kuinka monta pistettä jokaisen kansalaisen pitäisi laittaa julkisten palvelujen rahastoon?',
        blank=True,
    )
    proposed_transfer = models.IntegerField(
        min=0, max=C.MAX_PERSONAL_TRANSFER,
        label='Kuinka monta rahastopistettä pitäisi siirtää omaan ansioosi?',
        blank=True,
    )
    approval_vote = models.StringField(
        choices=C.APPROVAL_CHOICES,
        widget=widgets.RadioSelect,
        label='Hyväksytkö vai hylkäätkö valitun henkilön ehdotuksen?',
        blank=True,
    )
    is_leader = models.BooleanField(initial=False)
    institution_vote_time_seconds = models.FloatField(initial=0)
    institution_vote_over_90 = models.BooleanField(initial=False)
    proposal_time_seconds = models.FloatField(initial=0)
    proposal_over_90 = models.BooleanField(initial=False)
    approval_time_seconds = models.FloatField(initial=0)
    approval_over_90 = models.BooleanField(initial=False)
    fallback_time_seconds = models.FloatField(initial=0)
    fallback_over_90 = models.BooleanField(initial=False)
    round_payoff = models.FloatField(initial=0)
    expected_payoff_citizens = models.IntegerField(
        min=0, max=60,
        label='Jos ryhmän hyväksyntä vaaditaan, kuinka monta pistettä odotat ansaitsevasi?',
        blank=True,
    )
    expected_payoff_leader = models.IntegerField(
        min=0, max=60,
        label='Jos valitun henkilön päätös tulee voimaan suoraan, kuinka monta pistettä odotat ansaitsevasi?',
        blank=True,
    )
    expected_leader_transfer = models.IntegerField(
        min=0, max=C.MAX_PERSONAL_TRANSFER,
        label='Kuinka monta rahastopistettä odotat valitun henkilön ehdottavan siirrettäväksi omaan ansioonsa?',
        blank=True,
    )

    practice_contribution = models.IntegerField(min=0, max=20, label='Kuinka monta 20 pisteestäsi laitat julkisten palvelujen rahastoon?', blank=True)
    practice_allocation = models.IntegerField(min=0, max=20, label='Kuinka monta pistettä jokaisen kansalaisen pitäisi laittaa julkisten palvelujen rahastoon?', blank=True)
    practice_transfer = models.IntegerField(min=0, max=20, label='Kuinka monta rahastopistettä pitäisi siirtää omaan ansioosi?', blank=True)
    practice_approval = models.StringField(
        choices=C.APPROVAL_CHOICES, widget=widgets.RadioSelect,
        label='Hyväksyisitkö vai hylkäisitkö tämän ehdotuksen?', blank=True,
    )
    comprehension_1 = models.StringField(
        choices=[['same', 'Satunnaisesti valittu henkilö ehdottaa pistemäärää molemmissa menettelyissä'], ['different', 'Valittua henkilöä käytetään vain, kun päätös tulee voimaan suoraan']],
        widget=widgets.RadioSelect,
        label='Kuka ehdottaa kaikille samaa pistemäärää näissä kahdessa menettelyssä?',
        blank=True,
    )
    comprehension_2 = models.StringField(
        choices=[['three', 'Vähintään kolmen neljästä muusta kansalaisesta'], ['two', 'Vähintään kahden neljästä muusta kansalaisesta'], ['all', 'Kaikkien neljän muun kansalaisen']], widget=widgets.RadioSelect,
        label='Kun ryhmän hyväksyntä vaaditaan, kuinka monen neljästä muusta kansalaisesta on hyväksyttävä ehdotus?',
        blank=True,
    )
    comprehension_3 = models.StringField(
        choices=[['fallback', 'Jokainen valitsee itse rahastoon laittamansa pistemäärän'], ['automatic', 'Ehdotus tulee silti voimaan']],
        widget=widgets.RadioSelect,
        label='Mitä tapahtuu, jos ryhmän hyväksyntää vaativa ehdotus hylätään?',
        blank=True,
    )
    comprehension_4 = models.StringField(
        choices=[['yes', 'Kyllä'], ['no', 'Eivät']], widget=widgets.RadioSelect,
        label='Kun päätös tulee voimaan suoraan, voivatko muut kansalaiset hylätä ehdotuksen ennen sen toteuttamista?',
        blank=True,
    )
    comprehension_5 = models.StringField(
        choices=[['all', 'Kaikki kierrokset'], ['selected', 'Vain satunnaisesti valittu kierros'], ['last', 'Vain kierros 10']],
        widget=widgets.RadioSelect,
        label='Mikä kierros määrää ensimmäisen osion peliansiosi?',
        blank=True,
    )

class Block1Intro(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def vars_for_template(player):
        return dict(
            rounds=C.NUM_ROUNDS,
            group_size=C.GROUP_SIZE,
            fixed_five_person_pool=player.matching_pool_size == C.GROUP_SIZE,
        )


class PracticeIntro(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1


class PracticeIndividualChoice(Page):
    form_model = 'player'
    form_fields = ['practice_contribution']
    template_name = 'block1_crisis/PracticeIndividualChoice.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, PracticeIndividualChoice.form_fields)


class PracticeGroupChoice(Page):
    form_model = 'player'
    form_fields = ['practice_allocation', 'practice_transfer']
    template_name = 'block1_crisis/PracticeGroupChoice.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def error_message(player, values):
        missing = require_all(player, values, PracticeGroupChoice.form_fields)
        if missing:
            return missing
        if values.get('practice_transfer') is not None and values.get('practice_allocation') is not None:
            if values['practice_transfer'] > C.GROUP_SIZE * values['practice_allocation']:
                return 'Valittu henkilö ei voi siirtää enempää pisteitä kuin ryhmä laittaisi julkisten palvelujen rahastoon.'


class PracticeApproval(Page):
    form_model = 'player'
    form_fields = ['practice_approval']
    template_name = 'block1_crisis/QuestionPage.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='Harjoittele: ryhmän hyväksyntä',
            explanation=(
                'Oletetaan, että valittu henkilö ehdottaa jokaisen kansalaisen laittavan '
                'rahastoon 10 pistettä ja 5 rahastopisteen siirtämistä omaan ansioonsa. '
                'Kun ryhmän hyväksyntä vaaditaan, muut neljä kansalaista näkevät koko '
                'ehdotuksen ja päättävät, hyväksyvätkö vai hylkäävätkö he sen.'
            ),
            slider_prefix='',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, PracticeApproval.form_fields)


class Comprehension(Page):
    form_model = 'player'
    form_fields = [
        'comprehension_1', 'comprehension_2', 'comprehension_3',
        'comprehension_4', 'comprehension_5',
    ]
    template_name = 'block1_crisis/Comprehension.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def error_message(player, values):
        if development_mode(player):
            return
        errors = []
        if values['comprehension_1'] != 'same':
            errors.append('Ohjelmisto valitsee ehdotuksen tekijän molemmissa menettelyissä.')
        if values['comprehension_2'] != 'three':
            errors.append('Vähintään kolmen neljästä muusta kansalaisesta on hyväksyttävä ehdotus.')
        if values['comprehension_3'] != 'fallback':
            errors.append('Hylkäyksen jälkeen jokainen kansalainen valitsee itse rahastoon laittamansa pistemäärän.')
        if values['comprehension_4'] != 'no':
            errors.append('Suoraan voimaan tulevaa ehdotusta ei voi hylätä ennen sen toteuttamista.')
        if values['comprehension_5'] != 'selected':
            errors.append('Yksi satunnaisesti valittu kierros määrää ensimmäisen osion peliansiosi.')
        if errors:
            return 'Kertaa nämä säännöt: ' + ' '.join(errors)


class StrategicExpectations(Page):
    form_model = 'player'
    form_fields = [
        'expected_payoff_citizens',
        'expected_payoff_leader',
        'expected_leader_transfer',
    ]
    template_name = 'block1_crisis/QuestionPage.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='Mitä odotat tältä kierrokselta?',
            explanation=(
                'Arvioi ennen valintaasi, kuinka monta pistettä ansaitsisit kummassakin '
                'menettelyssä ja mitä valittu henkilö tekisi. Anna paras arviosi. '
                'Nämä vastaukset eivät vaikuta ansioosi.'
            ),
            slider_prefix='',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, StrategicExpectations.form_fields)


class InstitutionVote(Page):
    form_model = 'player'
    form_fields = ['institution_vote', 'solo_other_automatic_votes']
    template_name = 'block1_crisis/InstitutionChoice.html'

    @staticmethod
    def js_vars(player):
        return start_decision_timer(player, 'institution_vote')

    @staticmethod
    def vars_for_template(player):
        start_decision_timer(player, 'institution_vote')
        return dict(
            round_number=player.round_number,
            total_rounds=C.NUM_ROUNDS,
            approval_multiplier=format_rate(C.APPROVAL_MULTIPLIER_CRISIS),
            automatic_multiplier=format_rate(C.AUTOMATIC_MULTIPLIER),
            optional_responses=development_mode(player),
            selected_vote=player.field_maybe_none('institution_vote'),
            solo_testing=solo_testing(player),
            solo_other_automatic_votes=(
                player.field_maybe_none('solo_other_automatic_votes')
                if player.field_maybe_none('solo_other_automatic_votes') is not None else 2
            ),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, ['institution_vote'])

    @staticmethod
    def before_next_page(player, timeout_happened):
        record_decision_time(
            player,
            'institution_vote',
            'institution_vote_time_seconds',
            'institution_vote_over_90',
        )
        if solo_testing(player) and player.field_maybe_none('solo_other_automatic_votes') is None:
            player.solo_other_automatic_votes = 2


class VoteWaitPage(WaitPage):
    body_text = 'Odotetaan tämän kierroksen ryhmän muiden kansalaisten päätöksiä.'
    after_all_players_arrive = choose_institution_and_leader


class LeaderProposal(Page):
    form_model = 'player'
    template_name = 'block1_crisis/QuestionPage.html'

    @staticmethod
    def js_vars(player):
        return start_decision_timer(player, 'proposal')

    @staticmethod
    def get_form_fields(player):
        fields = ['proposed_allocation', 'proposed_transfer']
        if solo_testing(player) and player.group.selected_institution == C.APPROVAL:
            fields.append('solo_other_approval_votes')
        return fields
    @staticmethod
    def is_displayed(player):
        return player.is_leader

    @staticmethod
    def vars_for_template(player):
        start_decision_timer(player, 'proposal')
        return dict(
            page_title='Sinut on arvottu tekemään tämän kierroksen ehdotus',
            explanation=(
                'Ehdota, kuinka monta pistettä jokaisen kansalaisen pitäisi laittaa julkisten '
                f'palvelujen rahastoon ja siirretäänkö enintään {C.MAX_PERSONAL_TRANSFER} '
                'rahastopistettä omaan ansioosi. '
                + (
                    'Jos vähintään kolme neljästä muusta kansalaisesta hyväksyy ehdotuksen, '
                    'jokainen rahastoon jäävä piste tuottaa ryhmälle '
                    f'{format_rate(C.APPROVAL_MULTIPLIER_CRISIS)} pistettä. Jos ehdotus '
                    'hylätään, jokainen valitsee itse rahastoon laittamansa pistemäärän.'
                    if player.group.selected_institution == C.APPROVAL
                    else 'Ehdotuksesi tulee voimaan suoraan. Jokainen rahastoon jäävä piste '
                         f'tuottaa ryhmälle {format_rate(C.AUTOMATIC_MULTIPLIER)} pistettä.'
                )
            ),
            slider_prefix='',
            optional_responses=development_mode(player),
            solo_testing=solo_testing(player),
        )

    @staticmethod
    def error_message(player, values):
        required = ['proposed_allocation', 'proposed_transfer']
        missing = require_all(player, values, required)
        if missing:
            return missing
        if values.get('proposed_transfer') is not None and values.get('proposed_allocation') is not None:
            if values['proposed_transfer'] > C.GROUP_SIZE * values['proposed_allocation']:
                return 'Et voi siirtää enempää pisteitä kuin ryhmä laittaisi julkisten palvelujen rahastoon.'

    @staticmethod
    def before_next_page(player, timeout_happened):
        record_decision_time(
            player,
            'proposal',
            'proposal_time_seconds',
            'proposal_over_90',
        )
        if (
            solo_testing(player)
            and player.group.selected_institution == C.APPROVAL
            and player.field_maybe_none('solo_other_approval_votes') is None
        ):
            player.solo_other_approval_votes = 3


class ProposalWaitPage(WaitPage):
    body_text = 'Odotetaan valitun henkilön ehdotusta.'
    after_all_players_arrive = record_proposal


class ApprovalVote(Page):
    form_model = 'player'
    form_fields = ['approval_vote']
    template_name = 'block1_crisis/QuestionPage.html'

    @staticmethod
    def js_vars(player):
        return start_decision_timer(player, 'approval')

    @staticmethod
    def is_displayed(player):
        return (
            player.group.selected_institution == C.APPROVAL
            and not player.is_leader
        )

    @staticmethod
    def vars_for_template(player):
        start_decision_timer(player, 'approval')
        return dict(
            page_title='Hyväksy tai hylkää ehdotus',
            explanation=(
                'Valittu henkilö ehdottaa jokaisen kansalaisen laittavan rahastoon '
                f'{player.group.proposed_allocation} pistettä ja '
                f'{player.group.proposed_transfer} rahastopisteen siirtämistä omaan ansioonsa. '
                'Vähintään kolmen neljästä muusta kansalaisesta on hyväksyttävä ehdotus. '
                'Jos ehdotus hylätään, jokainen kansalainen valitsee itse rahastoon '
                'laittamansa pistemäärän.'
            ),
            slider_prefix='',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, ApprovalVote.form_fields)

    @staticmethod
    def before_next_page(player, timeout_happened):
        record_decision_time(
            player,
            'approval',
            'approval_time_seconds',
            'approval_over_90',
        )


class ApprovalWaitPage(WaitPage):
    body_text = 'Odotetaan ryhmän hyväksyntä-äänestyksen vastauksia.'

    @staticmethod
    def is_displayed(player):
        return player.group.selected_institution == C.APPROVAL

    after_all_players_arrive = decide_approval


class FallbackAllocation(Page):
    form_model = 'player'
    form_fields = ['contribution']
    template_name = 'block1_crisis/QuestionPage.html'

    @staticmethod
    def js_vars(player):
        return start_decision_timer(player, 'fallback')

    @staticmethod
    def is_displayed(player):
        return (
            player.group.selected_institution == C.APPROVAL
            and not player.group.proposal_approved
        )

    @staticmethod
    def vars_for_template(player):
        start_decision_timer(player, 'fallback')
        return dict(
            page_title='Ehdotusta ei hyväksytty',
            explanation=(
                'Jokainen kansalainen valitsee nyt, kuinka monta omasta 20 pisteestään '
                'laittaa julkisten palvelujen rahastoon. Jokainen rahastopiste tuottaa '
                f'{format_rate(C.APPROVAL_MULTIPLIER_CRISIS)} ryhmäpistettä, jotka '
                'jaetaan tasan. Pisteet, joita et laita rahastoon, jäävät sinulle.'
            ),
            slider_prefix='',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, FallbackAllocation.form_fields)

    @staticmethod
    def before_next_page(player, timeout_happened):
        record_decision_time(
            player,
            'fallback',
            'fallback_time_seconds',
            'fallback_over_90',
        )


class DecisionWaitPage(WaitPage):
    body_text = 'Odotetaan kaikkia tämän kierroksen päätöksiä.'
    after_all_players_arrive = calculate_round


class RoundResults(Page):
    template_name = 'block1_crisis/RoundResults.html'

    @staticmethod
    def vars_for_template(player):
        group = player.group
        return dict(
            round_number=player.round_number,
            total_rounds=C.NUM_ROUNDS,
            institution_label=dict(C.INSTITUTION_CHOICES)[group.selected_institution],
            approval_rule_votes=C.GROUP_SIZE - group.automatic_votes,
            automatic_rule_votes=group.automatic_votes,
            solo_testing=solo_testing(player),
            approval_required=group.selected_institution == C.APPROVAL,
            is_leader=player.id_in_group == group.leader_id,
            proposed_allocation=group.proposed_allocation,
            proposed_transfer=group.proposed_transfer,
            approval_votes=group.approval_votes,
            proposal_approved=group.proposal_approved,
            proposal_implemented=group.proposal_implemented,
            fallback_used=group.fallback_used,
            total_contribution=group.total_contribution,
            implemented_transfer=group.implemented_transfer,
            public_account=group.public_account,
            per_capita_return=group.per_capita_return,
            round_payoff=player.round_payoff,
            fixed_five_person_pool=player.matching_pool_size == C.GROUP_SIZE,
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        if player.round_number != C.NUM_ROUNDS:
            return
        player.participant.vars['block1_final_vote'] = player.field_maybe_none('institution_vote')
        player.participant.vars['block1_final_vote_observed'] = (
            player.field_maybe_none('institution_vote') is not None
        )
        late_votes = [p.field_maybe_none('institution_vote') for p in player.in_rounds(8, 10)]
        player.participant.vars['block1_late_automatic_share'] = sum(v == C.AUTOMATIC for v in late_votes) / 3
        player.participant.vars['expected_payoff_citizens_b1'] = (
            player.field_maybe_none('expected_payoff_citizens')
        )
        player.participant.vars['expected_payoff_leader_b1'] = (
            player.field_maybe_none('expected_payoff_leader')
        )
        player.participant.vars['expected_leader_transfer_b1'] = (
            player.field_maybe_none('expected_leader_transfer')
        )

        paying_round = player.session.vars['block1_paying_round']
        selected_payoff = player.in_round(paying_round).round_payoff
        player.payoff = cu(selected_payoff)
        player.participant.vars['block1_paying_round'] = paying_round
        player.participant.vars['block1_selected_payoff'] = selected_payoff


class Block1Complete(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS

    @staticmethod
    def vars_for_template(player):
        return dict(
            paying_round=player.participant.vars['block1_paying_round'],
            selected_payoff=player.participant.vars['block1_selected_payoff'],
        )


page_sequence = [
    Block1Intro,
    PracticeIntro,
    PracticeGroupChoice,
    PracticeApproval,
    PracticeIndividualChoice,
    Comprehension,
    StrategicExpectations,
    InstitutionVote,
    VoteWaitPage,
    LeaderProposal,
    ProposalWaitPage,
    ApprovalVote,
    ApprovalWaitPage,
    FallbackAllocation,
    DecisionWaitPage,
    RoundResults,
    Block1Complete,
]

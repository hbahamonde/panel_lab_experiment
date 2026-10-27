import random
import time

from otree.api import *
from treatment_allocation import AllocationStore


doc = """
Block 2: a pool-randomized structural recovery or persistence condition, five
repeated institutional-choice rounds, and individual ballots for immediate
and short-run democratic reversal.
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


def start_decision_timer(player, decision_name):
    key = f'block2_round_{player.round_number}_{decision_name}_started_at'
    started_at = player.participant.vars.setdefault(key, time.time())
    return dict(decision_reminder=dict(
        remaining_seconds=max(
            0, C.DECISION_DELAY_THRESHOLD_SECONDS - (time.time() - started_at)
        ),
        guide_seconds=C.DECISION_DELAY_THRESHOLD_SECONDS,
    ))


def record_decision_time(player, decision_name, seconds_field, flag_field):
    key = f'block2_round_{player.round_number}_{decision_name}_started_at'
    started_at = player.participant.vars.pop(key, time.time())
    elapsed = max(0, time.time() - started_at)
    setattr(player, seconds_field, elapsed)
    setattr(player, flag_field, elapsed > C.DECISION_DELAY_THRESHOLD_SECONDS)


def restore_allocation_metadata(subsession, players):
    """Reconcile metadata copies without consuming another allocation."""
    metadata_by_pool = dict(subsession.session.vars.get('treatment_allocation_by_pool', {}))
    for player in players:
        pool_id = player.participant.vars['matching_pool_id']
        metadata = player.participant.vars.get('treatment_allocation')
        if metadata:
            if pool_id in metadata_by_pool and metadata_by_pool[pool_id] != metadata:
                raise RuntimeError('Stored allocation metadata conflict within a pool.')
            metadata_by_pool[pool_id] = metadata
    for player in players:
        metadata = metadata_by_pool.get(player.participant.vars['matching_pool_id'])
        if metadata:
            if (metadata['treatment'] != player.participant.vars['treatment']
                    or metadata['block_number'] != player.participant.vars['randomization_stratum']
                    or metadata['pool_size'] != player.participant.vars['matching_pool_size']):
                raise RuntimeError('Stored treatment and allocation metadata conflict.')
            player.participant.vars['treatment_allocation'] = metadata
    if metadata_by_pool:
        subsession.session.vars['treatment_allocation_by_pool'] = metadata_by_pool


def assign_treatments_after_block1(subsession):
    """Consume size-stratified four-pool blocks only after all Block-1 ballots."""
    players = subsession.get_players()

    if solo_testing(subsession):
        treatment = subsession.session.config.get(
            'solo_treatment', C.TREATMENT_RECOVERY
        )
        player = players[0]
        player.participant.vars['treatment'] = treatment
        player.participant.vars['randomization_stratum'] = 1
        for round_player in player.in_all_rounds():
            round_player.treatment = treatment
            round_player.randomization_stratum = 1
        subsession.session.vars['treatment_by_pool'] = {1: treatment}
        subsession.session.vars['treatment_randomization_pairs'] = []
        subsession.session.vars['treatment_unmatched_pools'] = [1]
        subsession.session.vars['randomization_stratum_by_pool'] = {1: 1}
        return

    # Participant-level copies are the durable source during recovery from an
    # interrupted session. Once stored, treatment must never be redrawn.
    stored_assignment_available = all(
        'treatment' in player.participant.vars
        and 'randomization_stratum' in player.participant.vars
        for player in players
    )
    if stored_assignment_available:
        treatment_by_pool = {}
        stratum_by_pool = {}
        for player in players:
            pool_id = player.participant.vars['matching_pool_id']
            treatment = player.participant.vars['treatment']
            stratum = player.participant.vars['randomization_stratum']
            if (
                pool_id in treatment_by_pool
                and treatment_by_pool[pool_id] != treatment
            ):
                raise RuntimeError('Stored treatments conflict within a matching pool.')
            if pool_id in stratum_by_pool and stratum_by_pool[pool_id] != stratum:
                raise RuntimeError('Stored randomization strata conflict within a pool.')
            treatment_by_pool[pool_id] = treatment
            stratum_by_pool[pool_id] = stratum
            for round_player in player.in_all_rounds():
                round_player.treatment = treatment
                round_player.randomization_stratum = stratum
        subsession.session.vars['treatment_by_pool'] = treatment_by_pool
        subsession.session.vars['randomization_stratum_by_pool'] = stratum_by_pool
        restore_allocation_metadata(subsession, players)
        return

    # Also reuse a session-level draw if assignment was stored before every
    # participant-level copy was written.
    existing_assignments = subsession.session.vars.get('treatment_by_pool')
    if existing_assignments:
        stratum_by_pool = subsession.session.vars['randomization_stratum_by_pool']
        for player in players:
            pool_id = player.participant.vars['matching_pool_id']
            treatment = existing_assignments[pool_id]
            stratum = stratum_by_pool[pool_id]
            player.participant.vars['treatment'] = treatment
            player.participant.vars['randomization_stratum'] = stratum
            for round_player in player.in_all_rounds():
                round_player.treatment = treatment
                round_player.randomization_stratum = stratum
        restore_allocation_metadata(subsession, players)
        return

    pool_definitions = []
    pool_ids = sorted({p.participant.vars['matching_pool_id'] for p in players})
    for pool_id in pool_ids:
        pool_players = [
            p for p in players
            if p.participant.vars['matching_pool_id'] == pool_id
        ]
        expected_pool_size = pool_players[0].participant.vars['matching_pool_size']
        if len(pool_players) != expected_pool_size or expected_pool_size not in (5, 10, 15):
            raise RuntimeError(
                f'Matching pool {pool_id} has an invalid production size.'
            )
        if any(
            not p.participant.vars.get('block1_final_vote_observed', False)
            for p in pool_players
        ):
            raise RuntimeError(
                'A final Block-1 ballot is missing. Treatment assignment was not run.'
            )
        pool_definitions.append((
            pool_players[0].participant.vars['matching_pool_uid'], expected_pool_size,
        ))

    namespace = subsession.session.config['treatment_allocation_namespace']
    allocations = AllocationStore.from_environment().assign_pools(namespace, pool_definitions)
    metadata_by_pool = {
        pool_id: allocations[f'{subsession.session.code}-pool-{pool_id}']
        for pool_id in pool_ids
    }
    treatment_by_pool = {
        pool_id: metadata['treatment'] for pool_id, metadata in metadata_by_pool.items()
    }
    stratum_by_pool = {
        pool_id: metadata['block_number'] for pool_id, metadata in metadata_by_pool.items()
    }

    # The independent ledger is committed first. A crash before oTree commits
    # can therefore replay these exact UID assignments, never redraw them.
    subsession.session.vars['treatment_allocation_by_pool'] = metadata_by_pool
    subsession.session.vars['treatment_allocation_namespace'] = namespace
    subsession.session.vars['treatment_by_pool'] = treatment_by_pool
    subsession.session.vars['randomization_stratum_by_pool'] = stratum_by_pool

    for player in players:
        pool_id = player.participant.vars['matching_pool_id']
        treatment = treatment_by_pool[pool_id]
        stratum = stratum_by_pool[pool_id]
        player.participant.vars['treatment'] = treatment
        player.participant.vars['randomization_stratum'] = stratum
        player.participant.vars['treatment_allocation'] = metadata_by_pool[pool_id]
        for round_player in player.in_all_rounds():
            round_player.treatment = treatment
            round_player.randomization_stratum = stratum

    subsession.session.vars['treatment_by_pool'] = treatment_by_pool
    subsession.session.vars['treatment_randomization_pairs'] = []
    subsession.session.vars['treatment_unmatched_pools'] = []


def group_within_matching_pools(subsession):
    players = subsession.get_players()

    if solo_testing(subsession):
        if len(players) != 1:
            raise RuntimeError('Solo testing sessions require exactly one participant.')
        player = players[0]
        subsession.set_group_matrix([[player]])
        player.matching_pool_id = player.participant.vars['matching_pool_id']
        player.matching_pool_uid = player.participant.vars['matching_pool_uid']
        player.matching_pool_size = player.participant.vars['matching_pool_size']
        if subsession.round_number == 1:
            subsession.session.vars['block2_paying_round'] = random.randint(1, C.NUM_ROUNDS)
        return

    groups = []
    pool_ids = sorted({p.participant.vars['matching_pool_id'] for p in players})
    for pool_id in pool_ids:
        pool_players = [p for p in players if p.participant.vars['matching_pool_id'] == pool_id]
        random.shuffle(pool_players)
        if len(pool_players) % C.GROUP_SIZE != 0:
            raise RuntimeError(
                f'Matching pool {pool_id} contains {len(pool_players)} participants; '
                'Block 2 requires complete five-person groups.'
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

    if subsession.round_number == 1:
        subsession.session.vars['block2_paying_round'] = random.randint(1, C.NUM_ROUNDS)


def approval_multiplier(player):
    treatment = player.field_maybe_none('treatment')
    if treatment is None:
        treatment = player.participant.vars['treatment']
        player.treatment = treatment
        player.randomization_stratum = player.participant.vars['randomization_stratum']
    if treatment == C.TREATMENT_RECOVERY:
        return C.APPROVAL_MULTIPLIER_RECOVERY
    return C.APPROVAL_MULTIPLIER_CRISIS


def format_rate(value):
    """Format a displayed fund rate without changing its numerical value."""
    return f'{value:.2f}'.replace('.', ',')


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
    group.realized_approval_multiplier = approval_multiplier(players[0])

    if solo_testing(group):
        player = players[0]
        if player.round_number % 2:
            player.is_leader = True
            group.leader_id = player.id_in_group
        else:
            group.leader_id = 0
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
        group.per_capita_return = group.realized_approval_multiplier * total / C.GROUP_SIZE
        for player in players:
            player.round_payoff = C.ENDOWMENT - (player.field_maybe_none('contribution') or 0) + group.per_capita_return
    else:
        allocation = group.proposed_allocation
        transfer = group.proposed_transfer
        public_account = C.GROUP_SIZE * allocation - transfer
        multiplier = (
            C.AUTOMATIC_MULTIPLIER
            if group.selected_institution == C.AUTOMATIC
            else group.realized_approval_multiplier
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
    NAME_IN_URL = 'group_decisions_2'
    PLAYERS_PER_GROUP = None
    GROUP_SIZE = 5
    NUM_ROUNDS = 5

    ENDOWMENT = 20
    APPROVAL_MULTIPLIER_CRISIS = 1.50
    APPROVAL_MULTIPLIER_RECOVERY = 2.50
    AUTOMATIC_MULTIPLIER = 2.50
    MAX_PERSONAL_TRANSFER = 20
    MAX_ROUND_PAYOFF = 60
    MAX_TOTAL_POINTS = 2 * MAX_ROUND_PAYOFF
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
    AGREEMENT_CHOICES = [[i, str(i)] for i in range(1, 8)]
    FIVE_POINT_CHOICES = [
        [1, 'Erittäin heikosti'], [2, 'Heikosti'], [3, 'Kohtalaisesti'],
        [4, 'Hyvin'], [5, 'Erittäin hyvin']
    ]
    RISK_LEVEL_CHOICES = [
        [1, 'Erittäin pieni'], [2, 'Pieni'], [3, 'Kohtalainen'],
        [4, 'Suuri'], [5, 'Erittäin suuri']
    ]
    CRISIS_SERIOUSNESS_CHOICES = [
        [1, 'Ei vakavalta'], [2, 'Hieman vakavalta'], [3, 'Kohtalaisen vakavalta'],
        [4, 'Vakavalta'], [5, 'Erittäin vakavalta'],
    ]
    CONDITION_CHANGE_CHOICES = [
        [1, 'Paljon huonommalta'], [2, 'Hieman huonommalta'], [3, 'Samalta'],
        [4, 'Hieman paremmalta'], [5, 'Paljon paremmalta'],
    ]
    AGE_GROUP_CHOICES = [
        ['18-24', '18–24'], ['25-34', '25–34'], ['35-44', '35–44'],
        ['45-54', '45–54'], ['55-64', '55–64'], ['65+', '65 vuotta tai enemmän'],
        ['prefer_not', 'En halua vastata'],
    ]
    GENDER_CHOICES = [
        ['woman', 'Nainen'], ['man', 'Mies'], ['another', 'Muu sukupuoli'],
        ['prefer_not', 'En halua vastata'],
    ]
    EDUCATION_CHOICES = [
        ['basic', 'Perusaste'],
        ['upper_general', 'Lukio'],
        ['vocational', 'Ammatillinen tutkinto'],
        ['bachelor', 'Alempi korkeakoulututkinto tai ammattikorkeakoulututkinto'],
        ['master', 'Ylempi korkeakoulututkinto'], ['doctorate', 'Tohtorintutkinto'],
        ['other', 'Muu'], ['prefer_not', 'En halua vastata'],
    ]
    FINANCIAL_STRAIN_CHOICES = [
        [1, 'Erittäin vaikeaa'], [2, 'Vaikeaa'], [3, 'Ei vaikeaa eikä helppoa'],
        [4, 'Helppoa'], [5, 'Erittäin helppoa'], [-99, 'En halua vastata'],
    ]
    PARTY_VOTE_2023_CHOICES = [
        ['ncp', 'Kansallinen Kokoomus'],
        ['finns', 'Perussuomalaiset'],
        ['sdp', 'Suomen Sosialidemokraattinen Puolue'],
        ['centre', 'Suomen Keskusta'],
        ['greens', 'Vihreä liitto'],
        ['left', 'Vasemmistoliitto'],
        ['sfp', 'Suomen ruotsalainen kansanpuolue'],
        ['kd', 'Suomen Kristillisdemokraatit'],
        ['movement_now', 'Liike Nyt'],
        ['other_party', 'Muu puolue'], ['did_not_vote', 'En äänestänyt'],
        ['not_eligible', 'Minulla ei ollut äänioikeutta'],
        ['prefer_not', 'En halua vastata'],
    ]
    LEFT_RIGHT_CHOICES = (
        [[0, '0 — Vasemmisto']] + [[i, str(i)] for i in range(1, 10)]
        + [[10, '10 — Oikeisto'], [-99, 'En halua vastata']]
    )
    DEMOCRACY_PREFERABLE_CHOICES = [
        [1, 'Täysin eri mieltä'], [2, 'Jokseenkin eri mieltä'],
        [3, 'Jokseenkin samaa mieltä'], [4, 'Täysin samaa mieltä'],
        [-99, 'En halua vastata'],
    ]
    SATISFACTION_CHOICES = (
        [[0, '0 — Täysin tyytymätön']] + [[i, str(i)] for i in range(1, 10)]
        + [[10, '10 — Täysin tyytyväinen'], [-99, 'En halua vastata']]
    )
    STRONG_LEADER_CHOICES = [
        [1, 'Erittäin huono'], [2, 'Melko huono'], [3, 'Melko hyvä'], [4, 'Erittäin hyvä'],
        [-99, 'En halua vastata'],
    ]
    EXTERNAL_EFFICACY_CHOICES = [
        [1, 'Täysin eri mieltä'], [2, 'Eri mieltä'], [3, 'Ei samaa eikä eri mieltä'],
        [4, 'Samaa mieltä'], [5, 'Täysin samaa mieltä'], [-99, 'En halua vastata'],
    ]
    TRUST_CHOICES = (
        [[0, '0 — Ei voi olla liian varovainen']] + [[i, str(i)] for i in range(1, 10)]
        + [[10, '10 — Useimpiin ihmisiin voi luottaa'], [-99, 'En halua vastata']]
    )
    RISK_CHOICES = (
        [[0, '0 — En lainkaan halukas']] + [[i, str(i)] for i in range(1, 10)]
        + [[10, '10 — Erittäin halukas'], [-99, 'En halua vastata']]
    )
class Subsession(BaseSubsession):
    pass


def creating_session(subsession: Subsession):
    group_within_matching_pools(subsession)


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
    realized_approval_multiplier = models.FloatField(initial=0)


class Player(BasePlayer):
    matching_pool_id = models.IntegerField()
    matching_pool_uid = models.StringField()
    matching_pool_size = models.IntegerField()
    treatment = models.StringField()
    randomization_stratum = models.IntegerField(initial=0)
    institution_vote = models.StringField(
        choices=C.INSTITUTION_CHOICES, widget=widgets.RadioSelect,
        label='Pitäisikö valitun henkilön ehdotuksen vaatia ryhmän hyväksyntä?',
        blank=True,
    )
    solo_other_automatic_votes = models.IntegerField(min=0, max=4, blank=True)
    solo_other_approval_votes = models.IntegerField(
        min=0, max=4, blank=True,
        label='Yhden henkilön testi: kuinka moni neljästä simuloidusta kansalaisesta hyväksyy ehdotuksen?',
    )
    contribution = models.IntegerField(
        min=0, max=C.ENDOWMENT, blank=True,
        label='Kuinka monta 20 pisteestäsi laitat julkisten palvelujen rahastoon?',
    )
    proposed_allocation = models.IntegerField(
        min=0, max=C.ENDOWMENT, blank=True,
        label='Kuinka monta pistettä jokaisen kansalaisen pitäisi laittaa julkisten palvelujen rahastoon?',
    )
    proposed_transfer = models.IntegerField(
        min=0, max=C.MAX_PERSONAL_TRANSFER, blank=True,
        label='Kuinka monta rahastopistettä pitäisi siirtää omaan ansioosi?',
    )
    approval_vote = models.StringField(
        choices=C.APPROVAL_CHOICES, widget=widgets.RadioSelect,
        label='Hyväksytkö vai hylkäätkö valitun henkilön ehdotuksen?', blank=True,
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

    block1_crisis_seriousness = models.IntegerField(
        choices=C.CRISIS_SERIOUSNESS_CHOICES, widget=widgets.RadioSelect,
        label='Kuinka vakavalta ensimmäisen osion julkisten palvelujen tilanne vaikutti?',
        blank=True,
    )
    block2_condition_change = models.IntegerField(
        choices=C.CONDITION_CHANGE_CHOICES, widget=widgets.RadioSelect,
        label='Miltä toisen osion julkisten palvelujen tilanne vaikutti ensimmäiseen osioon verrattuna?',
        blank=True,
    )
    individual_method_effectiveness = models.IntegerField(
        choices=C.FIVE_POINT_CHOICES, widget=widgets.RadioSelect,
        label='Kuinka hyvin ryhmä pystyy näiden kierrosten perusteella tukemaan julkisia palveluja, kun valitun henkilön ehdotus vaatii ryhmän hyväksynnän?',
        blank=True,
    )
    constraint_risk = models.IntegerField(
        choices=C.RISK_LEVEL_CHOICES, widget=widgets.RadioSelect,
        label='Näiden kierrosten perusteella, kuinka suuri on riski, että johtajan vallan tavanomaiset rajat heikkenevät vakavasti?',
        blank=True,
    )
    constraint_1 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Nykyinen tilanne oikeuttaa antamaan valitun henkilön toimia ilman ryhmän hyväksyntää.', blank=True)
    constraint_2 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Tehokkaammat julkiset palvelut ovat sen arvoisia, että hyväksyntä-äänestä luovutaan nykyisessä tilanteessa.', blank=True)
    constraint_3 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Kansalaisten tulisi säilyttää hyväksyntä-ääni sitoviin ryhmäpäätöksiin, vaikka yhteisymmärrys voi jäädä syntymättä.', blank=True)
    constraint_4 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Johtajan pitäisi voida vaatia jokaista kansalaista laittamaan sama pistemäärä julkisten palvelujen rahastoon.', blank=True)
    constraint_5 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Vaadin mieluummin hyväksynnän kuin annan valitun henkilön toteuttaa siirron, jota en halua.', blank=True)
    constraint_6 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Hyväksyntä-äänen poistaminen aiheuttaa riskejä, jotka ovat nykyisiä hyötyjä suurempia.', blank=True)
    constraint_7 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Kun julkiset palvelut toimivat huonosti, valittujen päätöksentekijöiden on voitava toimia vapaammin ilman uutta hyväksyntää.', blank=True)

    background_age_group = models.StringField(
        choices=C.AGE_GROUP_CHOICES, label='Mikä on ikäsi?', blank=True,
    )
    background_gender = models.StringField(
        choices=C.GENDER_CHOICES, label='Mikä on sukupuolesi?', blank=True,
    )
    background_education = models.StringField(
        choices=C.EDUCATION_CHOICES,
        label='Mikä on korkein suorittamasi koulutus?', blank=True,
    )
    background_financial_strain = models.IntegerField(
        choices=C.FINANCIAL_STRAIN_CHOICES,
        label='Kuinka helppoa tai vaikeaa kotitaloutesi on saada tulot riittämään menoihin?', blank=True,
    )
    background_party_vote_2023 = models.StringField(
        choices=C.PARTY_VOTE_2023_CHOICES,
        label='Mitä puoluetta äänestit vuoden 2023 eduskuntavaaleissa?',
        blank=True,
    )
    background_left_right = models.IntegerField(
        choices=C.LEFT_RIGHT_CHOICES,
        label='Mihin sijoittaisit itsesi politiikassa asteikolla 0 (vasemmisto) – 10 (oikeisto)?',
        blank=True,
    )
    background_democracy_preferable = models.IntegerField(
        choices=C.DEMOCRACY_PREFERABLE_CHOICES,
        label='Demokratialla voi olla ongelmia, mutta se on parempi kuin mikään muu hallitusmuoto.',
        blank=True,
    )
    background_democracy_satisfaction = models.IntegerField(
        choices=C.SATISFACTION_CHOICES,
        label='Kuinka tyytyväinen olet kaiken kaikkiaan demokratian toimintaan Suomessa?',
        blank=True,
    )
    background_strong_leader = models.IntegerField(
        choices=C.STRONG_LEADER_CHOICES,
        label='Olisiko vahva johtaja, jonka ei tarvitse välittää parlamentista ja vaaleista, hyvä vai huono tapa hallita Suomea?',
        blank=True,
    )
    background_external_efficacy = models.IntegerField(
        choices=C.EXTERNAL_EFFICACY_CHOICES,
        label='Kansalaisten mielipiteet otetaan huomioon poliittisessa päätöksenteossa Suomessa.',
        blank=True,
    )
    background_generalized_trust = models.IntegerField(
        choices=C.TRUST_CHOICES,
        label='Voiko mielestäsi useimpiin ihmisiin luottaa, vai eikö ihmisten suhteen voi olla liian varovainen?',
        blank=True,
    )
    background_risk_willingness = models.IntegerField(
        choices=C.RISK_CHOICES,
        label='Kuinka halukas olet yleensä ottamaan riskejä?', blank=True,
    )

    democratic_reversal = models.BooleanField(initial=False)
    immediate_democratic_reversal = models.BooleanField(initial=False)


class TreatmentAssignmentWaitPage(WaitPage):
    wait_for_all_groups = True
    title_text = 'Odota hetki'
    body_text = 'Odotetaan, että kaikki osallistujat suorittavat ensimmäisen osion loppuun.'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    after_all_players_arrive = assign_treatments_after_block1


class Block2Intro(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def vars_for_template(player):
        return dict(
            rounds=C.NUM_ROUNDS,
            recovery=player.treatment == C.TREATMENT_RECOVERY,
            approval_multiplier=format_rate(approval_multiplier(player)),
            automatic_multiplier=format_rate(C.AUTOMATIC_MULTIPLIER),
            fixed_five_person_pool=player.matching_pool_size == C.GROUP_SIZE,
        )


class StrategicExpectations(Page):
    form_model = 'player'
    form_fields = [
        'expected_payoff_citizens',
        'expected_payoff_leader',
        'expected_leader_transfer',
    ]
    template_name = 'block2_reversal/QuestionPage.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number in [1, C.NUM_ROUNDS]

    @staticmethod
    def vars_for_template(player):
        timing = 'ensimmäistä' if player.round_number == 1 else 'viimeistä'
        return dict(
            page_title='Mitä odotat tältä kierrokselta?',
            explanation=(
                f'Ennen toisen osion {timing} valintaa arvioi, kuinka paljon ansaitsisit '
                'kummassakin menettelyssä ja mitä valittu henkilö tekisi. Anna paras '
                'arviosi. Nämä vastaukset eivät vaikuta ansioosi.'
            ),
            institution_vote_page=False,
            slider_prefix='',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, StrategicExpectations.form_fields)


class InstitutionVote(Page):
    form_model = 'player'
    form_fields = ['institution_vote', 'solo_other_automatic_votes']
    template_name = 'block2_reversal/QuestionPage.html'

    @staticmethod
    def js_vars(player):
        return start_decision_timer(player, 'institution_vote')

    @staticmethod
    def vars_for_template(player):
        start_decision_timer(player, 'institution_vote')
        return dict(
            page_title=f'Osio 2 — Kierros {player.round_number} / {C.NUM_ROUNDS}',
            explanation=(
                'Julkisten palvelujen rahastossa käytetään toisen osion alussa esitettyjä kertoimia. '
                'Molemmissa menettelyissä valittu henkilö voi ehdottaa enintään 20 rahastopisteen '
                'siirtämistä omaan ansioonsa. Tämä kierros voidaan valita palkkion laskentaan.'
            ),
            institution_vote_page=True,
            approval_multiplier=format_rate(approval_multiplier(player)),
            automatic_multiplier=format_rate(C.AUTOMATIC_MULTIPLIER),
            optional_responses=development_mode(player),
            selected_vote=player.field_maybe_none('institution_vote'),
            slider_prefix='',
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
        if player.round_number == 1:
            current_vote = player.field_maybe_none('institution_vote')
            first_votes_observed = (
                player.participant.vars.get('block1_final_vote_observed', False)
                and current_vote is not None
            )
            player.immediate_democratic_reversal = (
                first_votes_observed
                and player.participant.vars.get('block1_final_vote') == C.AUTOMATIC
                and current_vote == C.APPROVAL
            )
            player.participant.vars['block2_first_vote'] = current_vote
            player.participant.vars['block2_first_vote_observed'] = (
                current_vote is not None
            )
            player.participant.vars['immediate_democratic_reversal_observed'] = (
                first_votes_observed
            )
            player.participant.vars['immediate_democratic_reversal'] = (
                player.immediate_democratic_reversal
            )


class VoteWaitPage(WaitPage):
    title_text = 'Odota hetki'
    body_text = 'Odotetaan tämän kierroksen muiden ryhmän jäsenten päätöksiä.'
    after_all_players_arrive = choose_institution_and_leader

class LeaderProposal(Page):
    form_model = 'player'
    template_name = 'block2_reversal/QuestionPage.html'

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
                    f'{format_rate(approval_multiplier(player))} pistettä. Jos ehdotus '
                    'hylätään, jokainen valitsee itse rahastoon laittamansa pistemäärän.'
                    if player.group.selected_institution == C.APPROVAL
                    else 'Ehdotuksesi tulee voimaan suoraan. Jokainen rahastoon jäävä piste '
                         f'tuottaa ryhmälle {format_rate(C.AUTOMATIC_MULTIPLIER)} pistettä.'
                )
            ),
            institution_vote_page=False,
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
    title_text = 'Odota hetki'
    body_text = 'Odotetaan valitun henkilön ehdotusta.'
    after_all_players_arrive = record_proposal


class ApprovalVote(Page):
    form_model = 'player'
    form_fields = ['approval_vote']
    template_name = 'block2_reversal/QuestionPage.html'

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
                f'Valittu henkilö ehdottaa, että jokainen kansalainen laittaa '
                f'{player.group.proposed_allocation} pistettä rahastoon ja että '
                f'{player.group.proposed_transfer} rahastopistettä siirretään hänen omaan ansioonsa. '
                f'Vähintään kolmen neljästä muusta kansalaisesta on hyväksyttävä ehdotus. '
                'Jos ehdotus hylätään, jokainen kansalainen valitsee oman rahastoon laittamansa pistemäärän.'
            ),
            institution_vote_page=False,
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
    title_text = 'Odota hetki'
    body_text = 'Odotetaan ryhmän hyväksyntäpäätöksiä.'

    @staticmethod
    def is_displayed(player):
        return player.group.selected_institution == C.APPROVAL

    after_all_players_arrive = decide_approval


class FallbackAllocation(Page):
    form_model = 'player'
    form_fields = ['contribution']
    template_name = 'block2_reversal/QuestionPage.html'

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
                'Jokainen kansalainen valitsee nyt, kuinka monta omista 20 pisteestään laittaa '
                f'julkisten palvelujen rahastoon. Jokainen rahastopiste tuottaa '
                f'{format_rate(approval_multiplier(player))} ryhmäpistettä, jotka jaetaan tasan. '
                'Pisteet, joita et laita rahastoon, jäävät sinulle.'
            ),
            institution_vote_page=False,
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
    title_text = 'Odota hetki'
    body_text = 'Odotetaan kaikkia tämän kierroksen päätöksiä.'
    after_all_players_arrive = calculate_round

class RoundResults(Page):
    template_name = 'block2_reversal/RoundResults.html'

    @staticmethod
    def vars_for_template(player):
        group = player.group
        return dict(
            round_number=player.round_number,
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
            approval_multiplier=group.realized_approval_multiplier,
            implemented_multiplier=(
                C.AUTOMATIC_MULTIPLIER
                if group.selected_institution == C.AUTOMATIC
                else group.realized_approval_multiplier
            ),
            fixed_five_person_pool=player.matching_pool_size == C.GROUP_SIZE,
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        if player.round_number != C.NUM_ROUNDS:
            return
        block1_vote = player.participant.vars.get('block1_final_vote')
        block2_vote = player.field_maybe_none('institution_vote')
        final_votes_observed = (
            player.participant.vars.get('block1_final_vote_observed', False)
            and player.field_maybe_none('institution_vote') is not None
        )
        player.democratic_reversal = (
            final_votes_observed
            and block1_vote == C.AUTOMATIC
            and block2_vote == C.APPROVAL
        )
        player.participant.vars['block2_final_vote'] = block2_vote
        player.participant.vars['block2_final_vote_observed'] = (
            player.field_maybe_none('institution_vote') is not None
        )
        player.participant.vars['democratic_reversal_observed'] = final_votes_observed
        player.participant.vars['democratic_reversal'] = player.democratic_reversal
        late_votes = [
            p.field_maybe_none('institution_vote')
            for p in player.in_rounds(C.NUM_ROUNDS - 2, C.NUM_ROUNDS)
        ]
        player.participant.vars['block2_late_automatic_share'] = sum(
            vote == C.AUTOMATIC for vote in late_votes
        ) / 3
        player.participant.vars['expected_payoff_citizens_b2_final'] = (
            player.field_maybe_none('expected_payoff_citizens')
        )
        player.participant.vars['expected_payoff_leader_b2_final'] = (
            player.field_maybe_none('expected_payoff_leader')
        )
        player.participant.vars['expected_leader_transfer_b2_final'] = (
            player.field_maybe_none('expected_leader_transfer')
        )
        first_round = player.in_round(1)
        player.participant.vars['expected_payoff_citizens_b2_initial'] = (
            first_round.field_maybe_none('expected_payoff_citizens')
        )
        player.participant.vars['expected_payoff_leader_b2_initial'] = (
            first_round.field_maybe_none('expected_payoff_leader')
        )
        player.participant.vars['expected_leader_transfer_b2_initial'] = (
            first_round.field_maybe_none('expected_leader_transfer')
        )

        paying_round = player.session.vars['block2_paying_round']
        selected_payoff = player.in_round(paying_round).round_payoff
        player.payoff = cu(selected_payoff)
        player.participant.vars['block2_paying_round'] = paying_round
        player.participant.vars['block2_selected_payoff'] = selected_payoff


class FinalQuestions(Page):
    form_model = 'player'
    form_fields = [
        'block1_crisis_seriousness', 'block2_condition_change',
        'individual_method_effectiveness', 'constraint_risk',
        'constraint_1', 'constraint_2', 'constraint_3', 'constraint_4',
        'constraint_5', 'constraint_6', 'constraint_7',
    ]
    template_name = 'block2_reversal/QuestionPage.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='Loppukysymykset',
            explanation=(
                'Kaikki palkkiolliset päätökset on tehty. Vastaa seuraaviin kysymyksiin '
                'kokemastasi tilanteesta.'
            ),
            institution_vote_page=False,
            slider_prefix='constraint_',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, FinalQuestions.form_fields)


class BackgroundQuestions1(Page):
    form_model = 'player'
    form_fields = [
        'background_age_group', 'background_gender', 'background_education',
        'background_financial_strain', 'background_party_vote_2023',
        'background_left_right',
    ]
    template_name = 'block2_reversal/QuestionPage.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='Taustakysymykset (1/2)',
            explanation=(
                'Kaikki palkkiolliset päätökset on tehty. Nämä kysymykset auttavat ymmärtämään, '
                'miten kokeelliset valinnat vaihtelevat osallistujien välillä. Jokainen kysymys '
                'on vapaaehtoinen, ja voit jatkaa vastaamatta siihen.'
            ),
            institution_vote_page=False,
            slider_prefix='',
            optional_responses=True,
        )


class BackgroundQuestions2(Page):
    form_model = 'player'
    form_fields = [
        'background_democracy_preferable', 'background_democracy_satisfaction',
        'background_strong_leader', 'background_external_efficacy',
        'background_generalized_trust', 'background_risk_willingness',
    ]
    template_name = 'block2_reversal/QuestionPage.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='Taustakysymykset (2/2)',
            explanation=(
                'Loput vapaaehtoiset kysymykset koskevat poliittisia asenteita, luottamusta '
                'ja riskinottohalukkuutta. Voit jatkaa vastaamatta yhteenkään kysymykseen.'
            ),
            institution_vote_page=False,
            slider_prefix='',
            optional_responses=True,
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        player.participant.finished = True


def pretest_feedback_enabled(player):
    return player.session.config.get('pretest_feedback_enabled', False)


class PretestFeedbackReady(WaitPage):
    wait_for_all_groups = True
    title_text = 'Odota hetki'
    body_text = 'Odota, kunnes kaikki ovat vastanneet loppukysymyksiin.'

    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS and pretest_feedback_enabled(player)


class PretestFeedbackInvite(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS and pretest_feedback_enabled(player)


class StudyComplete(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS

    @staticmethod
    def vars_for_template(player):
        if not 0 <= float(player.participant.payoff) <= C.MAX_TOTAL_POINTS:
            raise RuntimeError('The calculated performance payment is outside its cap.')
        return dict(
            paying_round=player.participant.vars['block2_paying_round'],
            selected_payoff=player.participant.vars['block2_selected_payoff'],
            block1_paying_round=player.participant.vars['block1_paying_round'],
            block1_selected_payoff=player.participant.vars.get('block1_selected_payoff', 0),
            total_payoff=player.participant.payoff,
            performance_payment=player.participant.payoff.to_real_world_currency(player.session),
            participation_fee=f"{format_rate(player.session.config['participation_fee'])} €",
            total_payment=player.participant.payoff_plus_participation_fee(),
            participant_code=player.participant.code,
        )


def custom_export(players):
    """Export only the temporary code and amount needed to make payment."""
    yield ['participant_code', 'total_payment_eur']
    for player in players:
        if player.round_number != C.NUM_ROUNDS:
            continue
        participant = player.participant
        if not {
            'block1_selected_payoff', 'block2_selected_payoff'
        }.issubset(participant.vars):
            continue
        if not 0 <= float(participant.payoff) <= C.MAX_TOTAL_POINTS:
            raise RuntimeError('The calculated performance payment is outside its cap.')
        total_payment = participant.payoff_plus_participation_fee()
        yield [participant.code, f'{float(total_payment):.2f}']


page_sequence = [
    TreatmentAssignmentWaitPage,
    Block2Intro,
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
    FinalQuestions,
    BackgroundQuestions1,
    BackgroundQuestions2,
    PretestFeedbackReady,
    PretestFeedbackInvite,
    StudyComplete,
]

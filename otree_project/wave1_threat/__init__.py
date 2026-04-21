from otree.api import *
import json
import random


doc = """
Wave 1: baseline preferences, mechanism measures, practice round, and news board
"""


def shuffled_items_once(player, field_name, items):
    stored_order = player.field_maybe_none(field_name)

    if stored_order:
        stored_ids = [x for x in stored_order.split(',') if x]
        item_map = {item['id']: item for item in items}
        return [item_map[item_id] for item_id in stored_ids if item_id in item_map]

    shuffled = random.sample(items, len(items))
    setattr(player, field_name, ','.join(item['id'] for item in shuffled))
    return shuffled


def weighted_match_score(player, profile):
    return -(
        player.weight_redistribution * abs(player.pref_redistribution - profile['redistribution'])
        + player.weight_crime * abs(player.pref_crime - profile['crime'])
        + player.weight_immigration * abs(player.pref_immigration - profile['immigration'])
    )


def candidate_label(candidate_code):
    labels = {
        'candidate_1': 'Candidate 1',
        'candidate_2': 'Candidate 2',
        'tie': 'Tie',
    }
    return labels.get(candidate_code, candidate_code)

def issue_label(issue_name):
    labels = {
        'redistribution': 'Redistribution',
        'crime': 'Crime policy',
        'immigration': 'Immigration policy',
    }
    return labels.get(issue_name, issue_name)


def issue_preference_text(value):
    texts = {
        1: 'strongly favored option A',
        2: 'moderately favored option A',
        3: 'preferred a middle position',
        4: 'moderately favored option B',
        5: 'strongly favored option B',
    }
    return texts.get(value, str(value))


def issue_importance_text(value):
    texts = {
        1: 'not important',
        2: 'slightly important',
        3: 'moderately important',
        4: 'very important',
        5: 'extremely important',
    }
    return texts.get(value, str(value))


def candidate_issue_fit(player, profile):
    issues = [
        ('redistribution', player.pref_redistribution, player.weight_redistribution),
        ('crime', player.pref_crime, player.weight_crime),
        ('immigration', player.pref_immigration, player.weight_immigration),
    ]

    rows = []
    for issue_name, pref_value, weight_value in issues:
        candidate_value = profile[issue_name]
        distance = abs(pref_value - candidate_value)

        if distance == 0:
            fit_text = 'very close match'
        elif distance == 1:
            fit_text = 'fairly close match'
        elif distance == 2:
            fit_text = 'moderate mismatch'
        else:
            fit_text = 'clear mismatch'

        rows.append(
            dict(
                issue_label=issue_label(issue_name),
                preference_text=issue_preference_text(pref_value),
                importance_text=issue_importance_text(weight_value),
                candidate_position=candidate_value,
                distance=distance,
                fit_text=fit_text,
                weighted_distance=weight_value * distance,
            )
        )
    return rows


def participant_priority_summary(player):
    return [
        dict(
            issue_label='Redistribution',
            preference_text=issue_preference_text(player.pref_redistribution),
            importance_text=issue_importance_text(player.weight_redistribution),
        ),
        dict(
            issue_label='Crime policy',
            preference_text=issue_preference_text(player.pref_crime),
            importance_text=issue_importance_text(player.weight_crime),
        ),
        dict(
            issue_label='Immigration policy',
            preference_text=issue_preference_text(player.pref_immigration),
            importance_text=issue_importance_text(player.weight_immigration),
        ),
    ]


def study_schedule(session):
    return dict(
        wave1_date_display=session.config['wave1_date'],
        wave2_date_display=session.config['wave2_date'],
        wave3_date_display=session.config['wave3_date'],
        gates_enabled=session.config.get('enable_wave_gates', False),
    )


class C(BaseConstants):
    NAME_IN_URL = 'wave1_threat'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 1

    TOTAL_NEWS_BUDGET = 50
    NEWS_CLICK_COST = 5

    PRACTICE_CLICK_COST = 5
    PRACTICE_BUDGET = 15
    PRACTICE_VOTE_BONUS = 10


    PRACTICE_VOTE_CHOICES = [
        ['candidate_1', 'Candidate 1'],
        ['candidate_2', 'Candidate 2'],
    ]

    PRACTICE_CANDIDATE_PROFILES = {
        'candidate_1': dict(
            redistribution=4,
            crime=2,
            immigration=4,
        ),
        'candidate_2': dict(
            redistribution=2,
            crime=4,
            immigration=2,
        ),
    }

    PRACTICE_NEWS_ITEMS = [
        dict(
            id='p1',
            title_excerpt='Economic pressures remain high',
            full_title='Economic pressures remain high',
            full_text='Recent reports suggest that economic pressures remain high and continue to affect public opinion.',
        ),
        dict(
            id='p2',
            title_excerpt='Candidate 1 supports rule-based reform',
            full_title='Candidate 1 supports rule-based reform',
            full_text='Candidate 1 argues that reform should proceed within democratic rules and institutional checks.',
        ),
        dict(
            id='p3',
            title_excerpt='Candidate 2 supports faster executive action',
            full_title='Candidate 2 supports faster executive action',
            full_text='Candidate 2 argues that faster executive action is needed to deliver targeted benefits quickly.',
        ),
    ]

    POLICY_CHOICES = [
        [1, 'Strongly favor option A'],
        [2, 'Moderately favor option A'],
        [3, 'Balanced / middle position'],
        [4, 'Moderately favor option B'],
        [5, 'Strongly favor option B'],
    ]

    WEIGHT_CHOICES = [
        [1, 'Not important at all'],
        [2, 'Slightly important'],
        [3, 'Moderately important'],
        [4, 'Very important'],
        [5, 'Extremely important'],
    ]

    CAPACITY_CHOICES = [
        [1, 'Very low'],
        [2, 'Low'],
        [3, 'Moderate'],
        [4, 'High'],
        [5, 'Very high'],
    ]

    RISK_CHOICES = [
        [1, 'Very low'],
        [2, 'Low'],
        [3, 'Moderate'],
        [4, 'High'],
        [5, 'Very high'],
    ]

    NEWS_ITEMS = [
        dict(
            id='w1_n1',
            title_excerpt='Crime rates remain high across major urban areas',
            full_title='Crime rates remain high across major urban areas',
            full_text=(
                'Recent reports indicate that violent crime and property crime remain elevated. '
                'Public frustration has increased, and many voters now doubt whether ordinary '
                'institutional procedures are capable of restoring order quickly.'
            ),
            category='environment',
        ),
        dict(
            id='w1_n2',
            title_excerpt='Institutions criticized as slow and ineffective',
            full_title='Institutions criticized as slow and ineffective',
            full_text=(
                'Judicial backlogs, administrative delays, and weak enforcement have intensified the '
                'sense that institutions are not delivering. Commentators disagree on whether the '
                'problem is temporary or a deeper sign of institutional fragility.'
            ),
            category='institutions',
        ),
        dict(
            id='w1_n3',
            title_excerpt='Economic inequality becomes central campaign issue',
            full_title='Economic inequality becomes central campaign issue',
            full_text=(
                'A widening gap between high- and low-income households has become one of the central '
                'issues of the campaign. Citizens report growing concern that existing policy tools are '
                'not sufficient to address the problem.'
            ),
            category='economy',
        ),
        dict(
            id='w1_n4',
            title_excerpt='Candidate 1 promises reform within democratic constraints',
            full_title='Candidate 1 promises reform within democratic constraints',
            full_text=(
                'Candidate 1 argues that major reforms are still possible within democratic rules and '
                'institutional checks. The candidate emphasizes legality, oversight, and procedural restraint, '
                'even if policy change takes more time.'
            ),
            category='candidate',
        ),
        dict(
            id='w1_n5',
            title_excerpt='Candidate 2 promises fast targeted benefits through executive shortcuts',
            full_title='Candidate 2 promises fast targeted benefits through executive shortcuts',
            full_text=(
                'Candidate 2 argues that exceptional times require exceptional action. The candidate promises '
                'faster and more targeted benefits, but signals willingness to bypass some institutional constraints '
                'and weaken oversight in order to act decisively.'
            ),
            category='candidate',
        ),
    ]


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    pref_redistribution = models.IntegerField(
        label='What is your preferred position on redistribution policy?',
        choices=C.POLICY_CHOICES,
        widget=widgets.RadioSelect,
    )

    pref_crime = models.IntegerField(
        label='What is your preferred position on crime policy?',
        choices=C.POLICY_CHOICES,
        widget=widgets.RadioSelect,
    )

    pref_immigration = models.IntegerField(
        label='What is your preferred position on immigration policy?',
        choices=C.POLICY_CHOICES,
        widget=widgets.RadioSelect,
    )

    weight_redistribution = models.IntegerField(
        label='How important is redistribution policy to you when evaluating candidates?',
        choices=C.WEIGHT_CHOICES,
        widget=widgets.RadioSelect,
    )

    weight_crime = models.IntegerField(
        label='How important is crime policy to you when evaluating candidates?',
        choices=C.WEIGHT_CHOICES,
        widget=widgets.RadioSelect,
    )

    weight_immigration = models.IntegerField(
        label='How important is immigration policy to you when evaluating candidates?',
        choices=C.WEIGHT_CHOICES,
        widget=widgets.RadioSelect,
    )

    inst_capacity_pre = models.IntegerField(
        label='How capable are institutions of solving major problems without breaking democratic rules?',
        choices=C.CAPACITY_CHOICES,
        widget=widgets.RadioSelect,
    )

    collapse_risk_pre = models.IntegerField(
        label='How high is the risk of democratic collapse under current conditions?',
        choices=C.RISK_CHOICES,
        widget=widgets.RadioSelect,
    )

    practice_display_order = models.LongStringField(blank=True)
    practice_opened_ids = models.LongStringField(blank=True)
    practice_spent = models.IntegerField(initial=0)
    practice_click_order = models.LongStringField(blank=True)
    practice_time_seconds = models.FloatField(initial=0)

    practice_vote = models.StringField(
        choices=C.PRACTICE_VOTE_CHOICES,
        widget=widgets.RadioSelect,
        label='Practice vote: which candidate would you choose?',
        blank=True,
    )

    practice_best_candidate = models.StringField(blank=True)
    practice_vote_correct = models.BooleanField(initial=False)
    practice_score_candidate_1 = models.FloatField(initial=0)
    practice_score_candidate_2 = models.FloatField(initial=0)
    practice_vote_bonus_earned = models.IntegerField(initial=0)

    wave1_news_display_order = models.LongStringField(blank=True)
    wave1_news_opened_ids = models.LongStringField(blank=True)
    wave1_news_spent = models.IntegerField(initial=0)
    wave1_news_click_order = models.LongStringField(blank=True)
    wave1_news_time_seconds = models.FloatField(initial=0)


class Wave1Intro(Page):
    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        if 'news_budget_total' not in player.participant.vars:
            player.participant.vars['news_budget_total'] = C.TOTAL_NEWS_BUDGET
            player.participant.vars['news_budget_remaining'] = C.TOTAL_NEWS_BUDGET
            player.participant.vars['news_spent_total'] = 0
            player.participant.vars['all_opened_news_ids'] = []


class PrefRedistribution(Page):
    form_model = 'player'
    form_fields = ['pref_redistribution']
    template_name = 'wave1_threat/QuestionPage.html'

    @staticmethod
    def vars_for_template(player: Player):
        return dict(progress_label='Question 1 of 8')


class PrefCrime(Page):
    form_model = 'player'
    form_fields = ['pref_crime']
    template_name = 'wave1_threat/QuestionPage.html'

    @staticmethod
    def vars_for_template(player: Player):
        return dict(progress_label='Question 2 of 8')


class PrefImmigration(Page):
    form_model = 'player'
    form_fields = ['pref_immigration']
    template_name = 'wave1_threat/QuestionPage.html'

    @staticmethod
    def vars_for_template(player: Player):
        return dict(progress_label='Question 3 of 8')


class WeightRedistribution(Page):
    form_model = 'player'
    form_fields = ['weight_redistribution']
    template_name = 'wave1_threat/QuestionPage.html'

    @staticmethod
    def vars_for_template(player: Player):
        return dict(progress_label='Question 4 of 8')


class WeightCrime(Page):
    form_model = 'player'
    form_fields = ['weight_crime']
    template_name = 'wave1_threat/QuestionPage.html'

    @staticmethod
    def vars_for_template(player: Player):
        return dict(progress_label='Question 5 of 8')


class WeightImmigration(Page):
    form_model = 'player'
    form_fields = ['weight_immigration']
    template_name = 'wave1_threat/QuestionPage.html'

    @staticmethod
    def vars_for_template(player: Player):
        return dict(progress_label='Question 6 of 8')


class InstCapacityPre(Page):
    form_model = 'player'
    form_fields = ['inst_capacity_pre']
    template_name = 'wave1_threat/QuestionPage.html'

    @staticmethod
    def vars_for_template(player: Player):
        return dict(progress_label='Question 7 of 8')


class CollapseRiskPre(Page):
    form_model = 'player'
    form_fields = ['collapse_risk_pre']
    template_name = 'wave1_threat/QuestionPage.html'

    @staticmethod
    def vars_for_template(player: Player):
        return dict(progress_label='Question 8 of 8')

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        player.participant.vars['pref_redistribution'] = player.pref_redistribution
        player.participant.vars['pref_crime'] = player.pref_crime
        player.participant.vars['pref_immigration'] = player.pref_immigration
        player.participant.vars['weight_redistribution'] = player.weight_redistribution
        player.participant.vars['weight_crime'] = player.weight_crime
        player.participant.vars['weight_immigration'] = player.weight_immigration
        player.participant.vars['inst_capacity_pre'] = player.inst_capacity_pre
        player.participant.vars['collapse_risk_pre'] = player.collapse_risk_pre


class PracticeIntro(Page):
    pass


class PracticeNewsBoard(Page):
    form_model = 'player'
    form_fields = [
        'practice_opened_ids',
        'practice_spent',
        'practice_click_order',
        'practice_time_seconds',
    ]

    @staticmethod
    def vars_for_template(player: Player):
        ordered_items = shuffled_items_once(player, 'practice_display_order', C.PRACTICE_NEWS_ITEMS)
        return dict(
            news_items=ordered_items,
            click_cost=C.PRACTICE_CLICK_COST,
            budget_remaining=C.PRACTICE_BUDGET,
        )


class PracticeVote(Page):
    form_model = 'player'
    form_fields = ['practice_vote']

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        score_1 = weighted_match_score(player, C.PRACTICE_CANDIDATE_PROFILES['candidate_1'])
        score_2 = weighted_match_score(player, C.PRACTICE_CANDIDATE_PROFILES['candidate_2'])

        player.practice_score_candidate_1 = score_1
        player.practice_score_candidate_2 = score_2

        if score_1 > score_2:
            best_candidate = 'candidate_1'
        elif score_2 > score_1:
            best_candidate = 'candidate_2'
        else:
            best_candidate = 'tie'

        player.practice_best_candidate = best_candidate
        player.practice_vote_correct = (
            best_candidate != 'tie' and player.practice_vote == best_candidate
        )

        if player.practice_vote_correct:
            player.practice_vote_bonus_earned = C.PRACTICE_VOTE_BONUS
        else:
            player.practice_vote_bonus_earned = 0


class PracticeComplete(Page):
    @staticmethod
    def vars_for_template(player: Player):
        best_candidate = player.practice_best_candidate
        voted_candidate = player.practice_vote

        candidate_1_rows = candidate_issue_fit(player, C.PRACTICE_CANDIDATE_PROFILES['candidate_1'])
        candidate_2_rows = candidate_issue_fit(player, C.PRACTICE_CANDIDATE_PROFILES['candidate_2'])

        if best_candidate == 'tie':
            feedback_title = 'No single best practice vote'
            feedback_text = (
                'In this practice example, both candidates matched your earlier answers equally well overall. '
                'That means there was no single better vote in this practice round.'
            )
        elif player.practice_vote_correct:
            feedback_title = 'Your practice vote matched your earlier answers'
            feedback_text = (
                f'In this practice example, {candidate_label(best_candidate)} was the closer overall match '
                f'to the priorities you reported earlier. You voted for {candidate_label(voted_candidate)}, '
                f'so your practice vote was consistent with those earlier answers.'
            )
        else:
            feedback_title = 'Your practice vote did not match your earlier answers'
            feedback_text = (
                f'In this practice example, {candidate_label(best_candidate)} was the closer overall match '
                f'to the priorities you reported earlier. You voted for {candidate_label(voted_candidate)} instead.'
            )

        practice_budget_start = C.PRACTICE_BUDGET
        practice_spent_on_news = player.practice_spent or 0
        practice_budget_remaining = practice_budget_start - practice_spent_on_news
        practice_vote_bonus = player.practice_vote_bonus_earned or 0
        practice_net_points = practice_budget_remaining + practice_vote_bonus

        return dict(
            feedback_title=feedback_title,
            feedback_text=feedback_text,
            voted_candidate_label=candidate_label(voted_candidate),
            best_candidate_label=candidate_label(best_candidate),
            priority_summary=participant_priority_summary(player),
            candidate_1_rows=candidate_1_rows,
            candidate_2_rows=candidate_2_rows,
            candidate_1_score=player.practice_score_candidate_1,
            candidate_2_score=player.practice_score_candidate_2,
            practice_budget_start=practice_budget_start,
            practice_spent_on_news=practice_spent_on_news,
            practice_budget_remaining=practice_budget_remaining,
            practice_vote_bonus=practice_vote_bonus,
            practice_net_points=practice_net_points,
            practice_vote_correct=player.practice_vote_correct,
        )

class BeginMainStudy(Page):
    pass

class Wave1NewsBoard(Page):
    form_model = 'player'
    form_fields = [
        'wave1_news_opened_ids',
        'wave1_news_spent',
        'wave1_news_click_order',
        'wave1_news_time_seconds',
    ]

    @staticmethod
    def vars_for_template(player: Player):
        ordered_items = shuffled_items_once(player, 'wave1_news_display_order', C.NEWS_ITEMS)
        return dict(
            news_items=ordered_items,
            news_items_json=json.dumps(ordered_items),
            click_cost=C.NEWS_CLICK_COST,
            budget_remaining=player.participant.vars.get('news_budget_remaining', C.TOTAL_NEWS_BUDGET),
        )

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        opened_ids_raw = player.wave1_news_opened_ids or ''
        opened_ids = [x for x in opened_ids_raw.split(',') if x]

        previous_all = player.participant.vars.get('all_opened_news_ids', [])
        merged = previous_all.copy()
        for item_id in opened_ids:
            if item_id not in merged:
                merged.append(item_id)

        player.participant.vars['all_opened_news_ids'] = merged
        player.participant.vars['wave1_news_opened_ids'] = opened_ids
        player.participant.vars['wave1_news_click_order'] = player.wave1_news_click_order
        player.participant.vars['wave1_news_time_seconds'] = player.wave1_news_time_seconds
        player.participant.vars['news_spent_total'] = player.participant.vars.get('news_spent_total', 0) + player.wave1_news_spent
        player.participant.vars['news_budget_remaining'] = player.participant.vars.get('news_budget_remaining', C.TOTAL_NEWS_BUDGET) - player.wave1_news_spent

class Wave1Complete(Page):
    @staticmethod
    def vars_for_template(player: Player):
        return study_schedule(player.session)

        
page_sequence = [
    Wave1Intro,
    PrefRedistribution,
    PrefCrime,
    PrefImmigration,
    WeightRedistribution,
    WeightCrime,
    WeightImmigration,
    InstCapacityPre,
    CollapseRiskPre,
    PracticeIntro,
    PracticeNewsBoard,
    PracticeVote,
    PracticeComplete,
    BeginMainStudy,
    Wave1NewsBoard,
    Wave1Complete,
]
from __future__ import annotations
import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / 'novelai-prompt-studio'
sys.path.insert(0, str(SKILL / 'scripts'))
from studio import diff_sessions, inspect_atoms, lint_session, load_json, validate_session


def sample(**kw):
    v = {'schema_version': 1, 'model': 'v4.5-full', 'quality_tags': 'off',
         'uc_preset': 'none', 'base_prompt': 'portrait, pink hair'}
    v.update(kw)
    return v


def codes(v):
    return {x['code'] for x in lint_session(v)['issues']}


class SessionValidationTests(unittest.TestCase):
    def test_minimal_record_has_explicit_defaults(self):
        v = validate_session(sample())
        self.assertEqual(v['characters'], [])
        self.assertIsNone(v['generation']['seed'])
        self.assertFalse(v['intent']['text'])

    def test_input_not_mutated(self):
        v = sample(); old = copy.deepcopy(v)
        validate_session(v)
        self.assertEqual(v, old)

    def test_unknown_fields_rejected(self):
        with self.assertRaises(ValueError): validate_session(sample(qualty_tags='on'))

    def test_boolean_is_not_schema_version(self):
        with self.assertRaises(ValueError): validate_session(sample(schema_version=True))

    def test_missing_required_fields(self):
        v = sample(); del v['model']
        with self.assertRaises(ValueError): validate_session(v)

    def test_prompt_must_be_string(self):
        with self.assertRaises(ValueError): validate_session(sample(base_prompt=[]))

    def test_bad_switch_rejected(self):
        for value in (True, None, [], 'enabled'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_session(sample(quality_tags=value))

    def test_disabled_expansion_rejected(self):
        with self.assertRaises(ValueError): validate_session(sample(quality_tags_text='no text'))
        with self.assertRaises(ValueError): validate_session(sample(uc_preset_text='film grain'))

    def test_character_ids_unique(self):
        c = {'id':'a','prompt':'girl'}
        with self.assertRaises(ValueError): validate_session(sample(characters=[c,c]))

    def test_character_shape_checked(self):
        with self.assertRaises(ValueError): validate_session(sample(characters=[{'id':'a'}]))

    def test_intent_must_be_boolean(self):
        with self.assertRaises(ValueError): validate_session(sample(intent={'text':'yes'}))

    def test_intent_unknown_key_rejected(self):
        with self.assertRaises(ValueError): validate_session(sample(intent={'txet':True}))

    def test_spec_types_checked(self):
        with self.assertRaises(ValueError): validate_session(sample(spec={'must_keep':'hair'}))

    def test_generation_nan_rejected(self):
        with self.assertRaises(ValueError): validate_session(sample(generation={'guidance':math.nan}))

    def test_boolean_seed_rejected(self):
        with self.assertRaises(ValueError): validate_session(sample(generation={'seed':False}))

    def test_zero_seed_retained(self):
        self.assertEqual(validate_session(sample(generation={'seed':0}))['generation']['seed'], 0)

    def test_invalid_dimensions_rejected(self):
        with self.assertRaises(ValueError): validate_session(sample(generation={'width':0}))

    def test_unknown_lock_rejected(self):
        with self.assertRaises(ValueError): validate_session(sample(locked_paths=['characters.99.prompt']))

    def test_lock_path_syntax_rejected(self):
        with self.assertRaises(ValueError): validate_session(sample(locked_paths=['__import__("os")']))

    def test_nonfinite_json_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.json'; p.write_text('{"number": NaN}',encoding='utf-8')
            with self.assertRaises(ValueError): load_json(p)


class PromptLintTests(unittest.TestCase):
    def test_clean_example(self):
        result=lint_session(load_json(SKILL/'examples/portrait.json'))
        self.assertTrue(result['ok']); self.assertEqual(result['issues'], [])

    def test_v3_rejects_numeric_emphasis(self):
        self.assertIn('numeric_unsupported',codes(sample(model='v3-anime',base_prompt='1.2::rain::')))

    def test_v4_accepts_positive_numeric(self):
        self.assertEqual(codes(sample(model='v4-full',base_prompt='1.2::rain::')),set())

    def test_v4_rejects_negative_numeric(self):
        self.assertIn('negative_unsupported',codes(sample(model='v4-full',base_prompt='-1::hat::')))

    def test_v45_accepts_negative_numeric(self):
        self.assertNotIn('negative_unsupported',codes(sample(base_prompt='-1::hat::')))

    def test_reset_marker_closes_brackets(self):
        self.assertNotIn('open_emphasis_scope',codes(sample(base_prompt='{{rain::, night')))

    def test_unclosed_scope_is_warning_not_parse_error(self):
        r=lint_session(sample(base_prompt='1.2::rain'))
        self.assertTrue(r['ok']); self.assertIn('open_emphasis_scope',{i['code'] for i in r['issues']})

    def test_nonfinite_emphasis_is_error(self):
        self.assertFalse(lint_session(sample(base_prompt='9'*1000+'::rain::'))['ok'])

    def test_unconventional_brackets_are_not_declared_invalid(self):
        r=lint_session(sample(base_prompt='}rain{'))
        self.assertTrue(r['ok']); self.assertIn('unconventional_brackets',{i['code'] for i in r['issues']})

    def test_escaped_brackets_not_emphasis(self):
        self.assertNotIn('open_emphasis_scope',codes(sample(base_prompt=r'\{rain\}')))

    def test_foreign_weight_format(self):
        self.assertIn('foreign_weight_syntax',codes(sample(base_prompt='(rain:1.2)')))

    def test_character_parentheses_not_misread_as_weight(self):
        self.assertNotIn('foreign_weight_syntax',codes(sample(base_prompt=r'character \(series\)')))

    def test_negative_prompt_term_not_false_positive(self):
        self.assertNotIn('positive_uc_conflict',codes(sample(base_prompt='-1::hat::, portrait',uc='hat')))

    def test_zero_weight_not_positive_request(self):
        self.assertNotIn('positive_uc_conflict',codes(sample(base_prompt='0::hat::',uc='hat')))

    def test_real_uc_contradiction(self):
        self.assertIn('positive_uc_conflict',codes(sample(base_prompt='{hat}, portrait',uc='hat')))

    def test_simple_hair_phrase_alias_is_scope_aware(self):
        self.assertIn('positive_uc_conflict',codes(sample(base_prompt='long blue hair',uc='blue hair')))

    def test_alias_matching_is_not_arbitrary_substring_matching(self):
        self.assertNotIn('positive_uc_conflict',codes(sample(base_prompt='a blue hair ribbon',uc='blue hair')))

    def test_same_scope_duplicate(self):
        self.assertIn('duplicate_term',codes(sample(base_prompt='pink_hair, pink hair')))

    def test_cross_character_scopes_not_merged(self):
        self.assertEqual(codes(load_json(SKILL/'examples/two-characters.json')),set())

    def test_global_uc_applies_to_each_character(self):
        v=load_json(SKILL/'examples/two-characters.json');v['uc']='blue hair'
        issues=lint_session(v)['issues']
        paths={i['path'] for i in issues if i['code']=='positive_uc_conflict'}
        self.assertEqual(paths,{'characters.1.prompt'})

    def test_character_count_tag_location(self):
        v=sample(base_prompt='1girl',characters=[{'id':'a','prompt':'1girl, pink hair'}])
        self.assertIn('count_in_character',codes(v))

    def test_character_count_mismatch(self):
        v=sample(base_prompt='2girls',characters=[{'id':'a','prompt':'girl'}])
        self.assertIn('character_count_mismatch',codes(v))

    def test_mixed_pipe_and_boxes_rejected(self):
        v=sample(base_prompt='1girl | girl, pink hair',characters=[{'id':'a','prompt':'girl'}])
        self.assertIn('mixed_character_input',codes(v));self.assertFalse(lint_session(v)['ok'])

    def test_legacy_model_character_boxes(self):
        v=sample(model='v3-anime',characters=[{'id':'a','prompt':'girl'}])
        self.assertIn('character_boxes_unsupported',codes(v))

    def test_v45_character_limit(self):
        v=sample(base_prompt='7girls',characters=[{'id':str(i),'prompt':'girl'} for i in range(7)])
        self.assertIn('too_many_characters',codes(v))

    def test_v5_limit_not_inherited_from_old_page(self):
        v=sample(model='v5-full',base_prompt='7girls',characters=[{'id':str(i),'prompt':'girl'} for i in range(7)])
        self.assertNotIn('too_many_characters',codes(v))

    def test_unknown_model_remains_unknown(self):
        r=lint_session(sample(model='future-model',base_prompt='1.2::rain::'))
        self.assertIn('model_unknown',{i['code'] for i in r['issues']})
        self.assertIsNone(r['token_count']['approx_documented_limit'])

    def test_unknown_switches_report_incomplete(self):
        r=lint_session(sample(quality_tags='unknown',uc_preset='unknown'))
        self.assertEqual(len([i for i in r['issues'] if i['code']=='coverage_incomplete']),2)

    def test_known_quality_text_conflict(self):
        v=sample(quality_tags='on',base_prompt='text, english text. Text: HELLO')
        self.assertIn('intent_quality_conflict',codes(v))

    def test_quality_duplicate_explicit_expansion(self):
        v=sample(quality_tags='on',quality_tags_text='masterpiece',base_prompt='masterpiece, portrait')
        self.assertIn('duplicate_quality_term',codes(v))

    def test_v5_quality_expansion_not_guessed(self):
        r=lint_session(sample(model='v5-full',quality_tags='on'))
        self.assertEqual(r['coverage']['quality_tags'],'unknown_expansion')

    def test_v5_user_quality_expansion_used(self):
        v=sample(model='v5-full',quality_tags='on',quality_tags_text='no text',intent={'text':True})
        self.assertIn('intent_quality_conflict',codes(v))
        self.assertEqual(lint_session(v)['coverage']['quality_tags'],'explicit_user_expansion')

    def test_curated_feet_suppression(self):
        v=sample(model='v4.5-curated',quality_tags='on',intent={'feet':True})
        self.assertIn('intent_quality_conflict',codes(v))

    def test_negative_space_preset_conflict(self):
        v=sample(uc_preset='light',intent={'negative_space':True})
        self.assertIn('intent_uc_conflict',codes(v))
        self.assertEqual(lint_session(v)['coverage']['uc_preset'],'known_risk_subset')

    def test_film_grain_preset_conflict(self):
        self.assertIn('intent_uc_conflict',codes(sample(uc_preset='heavy',intent={'film_grain':True})))

    def test_explicit_uc_expansion_not_overridden_by_snapshot(self):
        v=sample(uc_preset='heavy',uc_preset_text='jpeg artifacts',intent={'film_grain':True})
        self.assertNotIn('intent_uc_conflict',codes(v))

    def test_explicit_uc_detects_actual_conflict(self):
        v=sample(uc_preset='custom-current-ui',uc_preset_text='film grain',intent={'film_grain':True})
        self.assertIn('intent_uc_conflict',codes(v))

    def test_text_tail_is_literal_not_tags(self):
        v=sample(model='v4-full',base_prompt='text, english text. Text: Hello, {world}, -1::caption::')
        r=lint_session(v)
        self.assertNotIn('negative_unsupported',{i['code'] for i in r['issues']})
        self.assertEqual(r['text_segments']['base_prompt'],'Hello, {world}, -1::caption::')

    def test_v3_structured_text_unsupported(self):
        self.assertIn('text_rendering_unsupported',codes(sample(model='v3-anime',base_prompt='Text: HELLO')))

    def test_v4_cjk_language_warning(self):
        self.assertIn('language_support_check',codes(sample(base_prompt='粉色头发')))

    def test_v5_cjk_not_incorrectly_rejected(self):
        self.assertNotIn('language_support_check',codes(sample(model='v5-full',base_prompt='粉色头发')))

    def test_token_count_not_claimed_measured(self):
        self.assertEqual(lint_session(sample())['token_count']['status'],'not_measured')


class DiffTests(unittest.TestCase):
    def test_background_revision_preserves_locks(self):
        r=diff_sessions(load_json(SKILL/'examples/portrait.json'),load_json(SKILL/'examples/portrait-refined.json'))
        self.assertTrue(r['ok']);self.assertEqual([c['path'] for c in r['changes']],['base_prompt'])

    def test_locked_character_change_fails(self):
        old=load_json(SKILL/'examples/portrait.json');new=copy.deepcopy(old)
        new['characters'][0]['prompt']='girl, blue hair'
        self.assertEqual(diff_sessions(old,new)['lock_violations'],['characters'])

    def test_removing_lock_list_does_not_bypass_previous_locks(self):
        old=sample(locked_paths=['base_prompt']);new=sample(base_prompt='different',locked_paths=[])
        self.assertFalse(diff_sessions(old,new)['ok'])

    def test_removed_locked_index_fails(self):
        old=sample(characters=[{'id':'a','prompt':'girl'}],locked_paths=['characters.0.prompt'])
        new=sample(characters=[])
        self.assertFalse(diff_sessions(old,new)['ok'])

    def test_no_change(self):
        self.assertEqual(diff_sessions(sample(),sample())['changes'],[])

    def test_unlocked_change_reported(self):
        self.assertTrue(diff_sessions(sample(),sample(base_prompt='new'))['ok'])

    def test_record_generation_lock(self):
        old=sample(generation={'seed':0},locked_paths=['generation.seed'])
        new=sample(generation={'seed':1})
        self.assertEqual(diff_sessions(old,new)['lock_violations'],['generation.seed'])


if __name__ == '__main__':
    unittest.main()

"""SurveyJS Schema 校验接缝（自我介绍问卷与调研共用）。"""
from django.test import SimpleTestCase

from common.survey_schema import InvalidSurveySchema, validate_schema_dict


class ValidateSchemaDictTest(SimpleTestCase):
    def test_accepts_dict_with_pages(self):
        schema = {"title": "T", "pages": [{"name": "page1", "elements": []}]}
        self.assertIs(validate_schema_dict(schema), schema)

    def test_rejects_non_dict(self):
        with self.assertRaises(InvalidSurveySchema) as ctx:
            validate_schema_dict(["pages"])
        self.assertEqual(str(ctx.exception), "问卷 Schema 须为 JSON 对象")

    def test_rejects_missing_pages(self):
        with self.assertRaises(InvalidSurveySchema) as ctx:
            validate_schema_dict({"title": "无 pages"})
        self.assertEqual(str(ctx.exception), "Schema 须包含 pages")

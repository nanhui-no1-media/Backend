"""门户 SurveyJS Schema 校验。自我介绍问卷与调研共用同一规则（ADR 0011 / 0014）。"""


class InvalidSurveySchema(ValueError):
    """``validate_schema_dict`` 拒绝；``str(self)`` 给序列化器当校验文案。"""


def validate_schema_dict(value):
    """Schema 须为含 ``pages`` 的 JSON 对象。非法则 raise ``InvalidSurveySchema``。"""
    if not isinstance(value, dict):
        raise InvalidSurveySchema("问卷 Schema 须为 JSON 对象")
    if "pages" not in value:
        raise InvalidSurveySchema("Schema 须包含 pages")
    return value
